"""
دامنه‌ی حمایت مستقیم از یک Alpha Caller مشخص (بند ۱۳ نیازمندی‌ها) — کاملاً جدا از
Prize Pool عمومی (handlers/payments.py). دونیت اینجا مستقیماً برای یک کاربر خاص
(recipient) ثبت می‌شه، نه برای استخر مشترک.

پترن ثبت‌نام: ^(support_.*|csupport_.*|checkcsupport_.*)$
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from signal_bot.config.settings import SEP, ADMIN_IDS
from signal_bot.db import users_repo, caller_donations_repo
from signal_bot.services import payments as payments_service
from signal_bot.services.notify import safe_send_message
from signal_bot.keyboards.keyboards import caller_support_amount_kb, caller_support_payment_link_kb, back_main_kb
from signal_bot.handlers.common import guard_callback
from signal_bot.handlers.payments import STATUS_MAP, _ipn_url
from signal_bot.utils import esc


async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guard = await guard_callback(update, context)
    if guard is None:
        return
    q, user, is_admin, is_vip_helper = guard
    data = q.data

    if data.startswith("support_"):
        recipient_id = int(data.split("_")[1])
        if recipient_id == user.id:
            await q.answer("😅 نمی‌تونی از خودت حمایت کنی!", show_alert=True)
            return
        recipient = users_repo.find_by_id(recipient_id)
        recipient_name = esc(recipient[1]) if recipient else f"کاربر {recipient_id}"
        await q.answer()
        await context.bot.send_message(
            chat_id=q.from_user.id,
            text=(
                f"<b>💝  حمایت از {recipient_name}</b>\n{SEP}\n\n"
                f"مبلغی که می‌خوای مستقیم به این تحلیلگر برسه رو انتخاب کن:"
            ),
            reply_markup=caller_support_amount_kb(recipient_id), parse_mode=ParseMode.HTML
        )

    elif data.startswith("csupport_"):
        parts = data.split("_")
        recipient_id = int(parts[1])
        amt_part = parts[2]
        if amt_part == "custom":
            context.chat_data.clear()
            context.chat_data["step"] = "support_custom"
            context.chat_data["support_recipient_id"] = recipient_id
            await q.edit_message_text(
                f"<b>✏️  مبلغ دلخواه حمایت (دلار)</b>\n{SEP}\n\nمبلغ رو بنویس:\nمثال: <code>15</code>",
                reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
            )
        else:
            await _make_support_invoice(q, context, user, recipient_id, float(amt_part))

    elif data.startswith("checkcsupport_"):
        donate_id = int(data.split("_")[1])
        row = caller_donations_repo.get_donation(donate_id)
        if not row:
            await q.answer("رکوردی پیدا نشد!", show_alert=True)
            return
        donor_id, recipient_id, payment_id, amount, current_status = row
        if donor_id != user.id:  # SEC-03: IDOR — این حمایت رو کاربر دیگه‌ای ثبت کرده
            await q.answer("⛔️ این پرداخت متعلق به تو نیست.", show_alert=True)
            return
        if current_status == "paid":
            await q.answer("✅ پرداخت قبلاً تأیید شده!", show_alert=True)
            return
        if not payment_id:
            await q.answer("⏳ هنوز اطلاعی از پرداخت دریافت نکردیم. چند دقیقه صبر کن و دوباره چک کن.",
                           show_alert=True)
            return
        status = await payments_service.check_payment(payment_id)
        new_status = STATUS_MAP.get(status, "pending")
        if new_status == "paid":
            await _finalize_support_payment(context, donate_id, donor_id, recipient_id, amount)
            await q.edit_message_text(
                f"✅  <b>حمایت {amount}$ تأیید شد!</b>\n\nممنون از حمایتت 🙏",
                parse_mode=ParseMode.HTML, reply_markup=back_main_kb()
            )
        elif new_status == "failed":
            await q.answer("❌ پرداخت ناموفق یا منقضی شده.", show_alert=True)
        else:
            await q.answer("⏳ هنوز در انتظاره. چند دقیقه صبر کن.", show_alert=True)


async def _make_support_invoice(q, context, user, recipient_id: int, amount: float):
    await q.edit_message_text(f"⏳  <b>در حال ساخت فاکتور {amount}$ ...</b>", parse_mode=ParseMode.HTML)
    order_id = payments_service.make_order_id(f"support_{user.id}_{recipient_id}")
    invoice  = await payments_service.create_invoice(amount, order_id, user.full_name or str(user.id), _ipn_url())
    if not invoice or "id" not in invoice:
        await q.edit_message_text("❌  خطا در ساخت فاکتور. دوباره امتحان کن.", reply_markup=back_main_kb())
        return
    invoice_url = invoice.get("invoice_url", "")
    invoice_id  = str(invoice.get("id", ""))
    donate_id = caller_donations_repo.insert_donation(
        user.id, recipient_id, amount, order_id, invoice_id, invoice_url
    )
    await q.edit_message_text(
        f"<b>💳  فاکتور آماده‌ست!</b>\n{SEP}\n\n"
        f"💰  مبلغ: <b>{amount}$</b>\n\n👇  روی دکمه پرداخت بزن:",
        reply_markup=caller_support_payment_link_kb(invoice_url, donate_id), parse_mode=ParseMode.HTML
    )


async def _finalize_support_payment(context, donate_id, donor_id, recipient_id, amount):
    """مشترک بین چک دستی و وب‌هوک — ثبت پرداخت + اطلاع به حامی و تحلیلگر."""
    caller_donations_repo.set_donation_paid(donate_id)
    donor = users_repo.find_by_id(donor_id)
    donor_name = esc(donor[1]) if donor else str(donor_id)
    await safe_send_message(context.bot, chat_id=recipient_id,
        text=f"💝  <b>یه نفر ازت حمایت کرد!</b>\n{SEP}\n\n👤 {donor_name}\n💵 {amount}$\n\nبه امیدت باش، همینطوری ادامه بده! 🚀",
        parse_mode=ParseMode.HTML)
    for admin_id in ADMIN_IDS:
        await safe_send_message(context.bot, chat_id=admin_id,
            text=f"💝  <b>حمایت مستقیم جدید!</b>\n👤 {donor_name} → {recipient_id}\n💵 {amount}$",
            parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════════════
#  مرحله ورودی متنی: مبلغ دلخواه حمایت (صدا زده می‌شه از handlers/text_router.py)
# ══════════════════════════════════════════════════════════
async def handle_step_support_custom(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    recipient_id = context.chat_data.get("support_recipient_id")
    if not recipient_id:
        await update.message.reply_text("⚠️  یه مشکلی پیش اومد، از اول امتحان کن.")
        context.chat_data.clear()
        return
    try:
        amount = float(text.replace(",", ""))
        if amount <= 0:
            raise ValueError
        context.chat_data.clear()
        await update.message.reply_html(f"⏳  <b>در حال ساخت فاکتور {amount}$ ...</b>")
        order_id = payments_service.make_order_id(f"support_{user.id}_{recipient_id}")
        invoice  = await payments_service.create_invoice(amount, order_id, user.full_name or str(user.id), _ipn_url())
        if not invoice or "id" not in invoice:
            await update.message.reply_html("❌  خطا در ساخت فاکتور.", reply_markup=back_main_kb())
            return
        invoice_url = invoice.get("invoice_url", "")
        invoice_id  = str(invoice.get("id", ""))
        donate_id = caller_donations_repo.insert_donation(
            user.id, recipient_id, amount, order_id, invoice_id, invoice_url
        )
        await update.message.reply_html(
            f"<b>💳  فاکتور آماده‌ست!</b>\n{SEP}\n\n💰  مبلغ: <b>{amount}$</b>\n\n👇  روی دکمه پرداخت بزن:",
            reply_markup=caller_support_payment_link_kb(invoice_url, donate_id)
        )
    except ValueError:
        await update.message.reply_text("⚠️  مبلغ معتبر وارد کن!")
