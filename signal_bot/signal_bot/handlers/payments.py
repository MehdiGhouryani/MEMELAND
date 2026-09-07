"""
دامنه پرداخت: نمایش استخر جایزه، واریز به استخر (مبلغ ثابت/دلخواه)، ساخت فاکتور NOWPayments و چک وضعیت.

پترن ثبت‌نام: ^(menu_prize|menu_donate|donate_.*|checkpay_.*)$

⚠️ فاز ۵: باگ قدیمی رفع شد — order_id (که برای مچ‌کردن با IPN لازمه) قبلاً تولید
می‌شد ولی هیچ‌جا ذخیره نمی‌شد. الان ذخیره می‌شه، و اگه NOWPAYMENTS_IPN_SECRET
تنظیم شده باشه، یک ipn_callback_url هم به فاکتور اضافه می‌شه تا تأیید خودکار
(نه فقط کلیک دستی) هم کار کنه.
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from signal_bot.config.settings import SEP, ADMIN_IDS, NOWPAYMENTS_IPN_SECRET, IPN_CALLBACK_URL
from signal_bot.db import prize_repo
from signal_bot.formatters.texts import prize_pool_text
from signal_bot.keyboards.keyboards import donate_amount_kb, back_main_kb, payment_link_kb, ranking_hub_kb
from signal_bot.services import payments as payments_service
from signal_bot.services.notify import safe_send_message
from signal_bot.handlers.common import guard_callback
from signal_bot.utils import esc

STATUS_MAP = {"finished": "paid", "confirmed": "paid", "sending": "paid",
              "expired": "failed", "failed": "failed"}


def _ipn_url() -> str:
    """اگه IPN تنظیم نشده باشه، رشته خالی برمی‌گرده و NOWPayments بدون وب‌هوک کار می‌کنه
    (فقط چک دستی) — یعنی نبود این تنظیم کرش نمی‌کنه، فقط یه قابلیت غیرفعال می‌مونه."""
    return IPN_CALLBACK_URL if (NOWPAYMENTS_IPN_SECRET and IPN_CALLBACK_URL) else ""


async def payments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guard = await guard_callback(update, context)
    if guard is None:
        return
    q, user, is_admin, is_vip_helper = guard
    data = q.data

    if data == "menu_prize":
        await q.edit_message_text(prize_pool_text(), reply_markup=ranking_hub_kb("prize"), parse_mode=ParseMode.HTML)

    elif data == "menu_donate":
        await q.edit_message_text(
            f"<b>🤝  حمایت از ما</b>\n{SEP}\n\n"
            "این صندوق برای حمایت از برترین سیگنال‌دهنده‌هامون و آلفاکالرهاست.\n"
            "تمام مبالغ جمع‌آوری‌شده به لیدربورد برترین کالرهای این ماه اختصاص پیدا می‌کنه.\n"
            "<i>دونیت کاملاً اختیاریه 🙏</i>\n\n"
            "💳  پرداخت با <b>NOWPayments</b> — بیش از ۳۰۰ ارز دیجیتال، تأیید خودکار\n\n"
            f"{SEP}\nمبلغ رو انتخاب کن 👇",
            reply_markup=donate_amount_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "donate_solana_wallet":
        from signal_bot.site.kv import kv_get
        solana_wallet = kv_get("settings:solana_donate_wallet") or "—"
        await q.edit_message_text(
            f"<b>💜  واریز مستقیم با ولت سولانا</b>\n{SEP}\n\n"
            "هر مبلغی (SOL یا هر توکن دیگه) به این آدرس بفرست:\n\n"
            f"<code>{solana_wallet}</code>\n\n"
            "برای کپی، رو آدرس بزن. ⚠️ این مسیر خودکار نیست — تأییدش دستیه و "
            "تو لیدربورد ماهانه به‌صورت دستی لحاظ می‌شه، نه آنی.",
            reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
        )

    elif data.startswith("donate_"):
        amt_str = data.split("_")[1]
        if amt_str == "custom":
            context.chat_data["step"] = "donate_custom"
            await q.edit_message_text(
                f"<b>✏️  مبلغ دلخواه (دلار)</b>\n{SEP}\n\nمبلغ رو بنویس:\nمثال: <code>35</code>",
                reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
            )
        else:
            await _make_invoice(q, context, user, float(amt_str))

    elif data.startswith("checkpay_"):
        donate_id = int(data.split("_")[1])
        row = prize_repo.get_donation(donate_id)
        if not row:
            await q.answer("رکوردی پیدا نشد!", show_alert=True)
            return
        owner_id, payment_id, amount, current_status = row
        if owner_id != user.id:  # SEC-03: IDOR — این پرداخت مال کاربر دیگه‌ست
            await q.answer("⛔️ این پرداخت متعلق به تو نیست.", show_alert=True)
            return
        if current_status == "paid":
            await q.answer("✅ پرداخت قبلاً تأیید شده!", show_alert=True)
            return
        if not payment_id:
            # هنوز هیچ IPN ای نرسیده که payment_id رو بهمون بده — صادقانه بگیم،
            # نه اینکه وانمود کنیم چک کردیم (باگ قدیمی همین بود: با None چک می‌کرد)
            await q.answer("⏳ هنوز اطلاعی از پرداخت دریافت نکردیم. اگه تازه پرداخت کردی، "
                           "چند دقیقه صبر کن و دوباره چک کن.", show_alert=True)
            return
        status = await payments_service.check_payment(payment_id)
        new_status = STATUS_MAP.get(status, "pending")
        if new_status == "paid":
            prize_repo.set_donation_paid(donate_id)
            await q.edit_message_text(
                f"✅  <b>پرداخت {amount}$ تأیید شد!</b>\n\nممنون از حمایتت 🙏\nاسمت توی استخر جایزه ثبت شد 💎",
                parse_mode=ParseMode.HTML, reply_markup=back_main_kb()
            )
            for admin_id in ADMIN_IDS:
                await safe_send_message(context.bot, chat_id=admin_id,
                    text=f"💰  <b>پرداخت جدید!</b>\n👤 {esc(user.full_name)}\n💵 {amount}$",
                    parse_mode=ParseMode.HTML)
        elif new_status == "failed":
            await q.answer("❌ پرداخت ناموفق یا منقضی شده.", show_alert=True)
        else:
            await q.answer("⏳ هنوز در انتظاره. چند دقیقه صبر کن.", show_alert=True)


async def _make_invoice(q, context, user, amount: float):
    await q.edit_message_text(f"⏳  <b>در حال ساخت فاکتور {amount}$ ...</b>", parse_mode=ParseMode.HTML)
    order_id = payments_service.make_order_id(f"pool_{user.id}")
    invoice  = await payments_service.create_invoice(amount, order_id, user.full_name or str(user.id), _ipn_url())
    if not invoice or "id" not in invoice:
        await q.edit_message_text("❌  خطا در ساخت فاکتور. دوباره امتحان کن.",
                                  reply_markup=back_main_kb())
        return
    invoice_url = invoice.get("invoice_url", "")
    invoice_id  = str(invoice.get("id", ""))
    donate_id = prize_repo.insert_donation(user.id, amount, order_id, invoice_id, invoice_url)
    await q.edit_message_text(
        f"<b>💳  فاکتور آماده‌ست!</b>\n{SEP}\n\n"
        f"💰  مبلغ: <b>{amount}$</b>\n🔸  بیش از ۳۰۰ ارز\n\n👇  روی دکمه پرداخت بزن:",
        reply_markup=payment_link_kb(invoice_url, donate_id), parse_mode=ParseMode.HTML
    )


# ══════════════════════════════════════════════════════════
#  مرحله ورودی متنی: مبلغ دلخواه دونیت
# ══════════════════════════════════════════════════════════
async def handle_step_donate_custom(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    try:
        amount = float(text.replace(",", ""))
        if amount <= 0:
            raise ValueError
        context.chat_data.clear()
        await update.message.reply_html(f"⏳  <b>در حال ساخت فاکتور {amount}$ ...</b>")
        order_id = payments_service.make_order_id(f"pool_{user.id}")
        invoice  = await payments_service.create_invoice(amount, order_id, user.full_name or str(user.id), _ipn_url())
        if not invoice or "id" not in invoice:
            await update.message.reply_html("❌  خطا در ساخت فاکتور.", reply_markup=back_main_kb())
            return
        invoice_url = invoice.get("invoice_url", "")
        invoice_id  = str(invoice.get("id", ""))
        donate_id = prize_repo.insert_donation(user.id, amount, order_id, invoice_id, invoice_url)
        await update.message.reply_html(
            f"<b>💳  فاکتور آماده‌ست!</b>\n{SEP}\n\n💰  مبلغ: <b>{amount}$</b>\n\n👇  روی دکمه پرداخت بزن:",
            reply_markup=payment_link_kb(invoice_url, donate_id)
        )
    except ValueError:
        await update.message.reply_text("⚠️  مبلغ معتبر وارد کن!")
