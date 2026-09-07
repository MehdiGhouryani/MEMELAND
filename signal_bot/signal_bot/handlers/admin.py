"""
دامنه ادمین: پنل مدیریت، بررسی سیگنال‌های در انتظار، ثبت نتیجه، آمار کلی،
مدیریت کاربران (بلاک/امتیاز/رول/VIP Helper)، پیام همگانی، خروجی اکسل،
پایان دوره و تقسیم جایزه.

پترن ثبت‌نام: ^(menu_admin|adm_.*|approve_.*|reject_.*|setresult_.*|block_.*|
                unblock_.*|setpts_.*|setrole_.*|role_.*|vip_add_.*|vip_remove_.*)$

⚠️ بررسی/تأیید/رد سیگنال (adm_pending, approve_, reject_) برای Admin و VIP Helper
هر دو مجازه (بند ۵ نیازمندی‌ها)؛ بقیه‌ی این پنل فقط برای Admin (ADMIN_IDS) است.
"""
import csv
import io
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from signal_bot.config.settings import (
    SEP, ADMIN_IDS, RESULT_LABEL, CHANNEL_ID, ROLE_LABELS, SIGNAL_TYPE_LABELS
)
from signal_bot.db import users_repo, signals_repo, prize_repo, staff_repo, rewards_repo, caller_donations_repo
from signal_bot.services import scoring, access, results, site_sync, image_upload
from signal_bot.services.notify import safe_send_message, safe_send_photo, safe_send_document
from signal_bot.keyboards.keyboards import (
    admin_kb, back_main_kb, approve_reject_kb, signal_result_kb, user_manage_kb, role_picker_kb, btn
)
from signal_bot.handlers.common import guard_callback
from signal_bot.utils import esc


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guard = await guard_callback(update, context)
    if guard is None:
        return
    q, user, is_admin, is_vip_helper = guard
    data = q.data
    can_review = is_admin or is_vip_helper  # بند ۵: Admin یا VIP Helper می‌تونن سیگنال تأیید/رد کنن

    # ── پنل ادمین ─────────────────────────────────────────
    if data == "menu_admin":
        if not is_admin:
            await q.answer("⛔️ دسترسی ندارید!", show_alert=True)
            return
        total_users  = users_repo.count_users()
        pending_sigs = signals_repo.count_pending_signals()
        prize        = prize_repo.get_prize_pool_total()
        await q.edit_message_text(
            f"<b>⚙️  پنل مدیریت</b>\n{SEP}\n\n"
            f"👥  کاربران: <b>{total_users}</b>\n"
            f"⏳  سیگنال در انتظار: <b>{pending_sigs}</b>\n"
            f"💰  استخر جایزه: <b>{prize:.2f}$</b>\n{SEP}",
            reply_markup=admin_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "adm_help":
        if not is_admin:
            return
        role_lines = access.get_role_limits_lines()
        await q.edit_message_text(
            f"<b>❓  راهنمای پنل ادمین</b>\n{SEP}\n\n"
            f"📋 <b>در انتظار</b> — تأیید/رد سیگنال (Admin + VIP Helper)\n"
            f"🎯 <b>ثبت نتیجه</b> — برد/باخت سیگنال‌های تأییدشده\n"
            f"💰 <b>واریزها</b> — استخر جایزه + حمایت مستقیم\n"
            f"📢 <b>همگانی</b> — پیام به همه‌ی کاربران\n"
            f"📊 <b>آمار</b> — کاربر/سیگنال/جایزه/VIP Helper\n"
            f"👥 <b>کاربران</b> — جست‌وجو → بلاک/امتیاز/درجه/پاداش/VIP\n"
            f"🏆 <b>پایان دوره</b> — تقسیم ۵۰/۳۰/۲۰٪، فصل بعد خودکاره\n"
            f"📤 <b>اکسل</b> — خروجی CSV امتیازها\n"
            f"🆕 <b>فصل جدید</b> — فقط اگه فصلی فعال نبود لازمه\n"
            f"{SEP}\n"
            f"💬  <b>دستور (گروه یا دایرکت)</b>\n"
            f"<code>/fastcall کوین [long/short]</code>\n"
            f"<code>/fullsignal [کوین] [جهت] [توضیح]</code> (± عکس)\n"
            f"{SEP}\n"
            f"🎖  <b>سقف سیگنال روزانه هر درجه</b>\n"
            f"{role_lines}\n"
            f"{SEP}\n"
            f"💎  VIP Helper فقط سیگنال تأیید/رد می‌کنه، به بقیه‌ی پنل دسترسی نداره.",
            reply_markup=admin_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "adm_solana_wallet":
        if not is_admin:
            return
        from signal_bot.site.kv import kv_get
        current = kv_get("settings:solana_donate_wallet")
        context.chat_data["step"] = "set_solana_wallet"
        await q.edit_message_text(
            f"<b>💜  ولت سولانا برای «حمایت از ما»</b>\n{SEP}\n\n"
            f"مقدار فعلی: <code>{esc(current) if current else 'ست نشده'}</code>\n\n"
            "آدرس ولت جدید رو بفرست (یا برای حذف کامل دکمه، <code>-</code> بفرست):",
            reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "adm_pending":
        if not can_review:
            return
        rows = signals_repo.get_pending_signals(limit=10)
        if not rows:
            await q.answer("✅  سیگنال در انتظاری نیست!", show_alert=True)
            return
        await q.edit_message_text(f"<b>📋  سیگنال‌های در انتظار ({len(rows)})</b>", parse_mode=ParseMode.HTML)
        for row in rows:
            sid, name, uname, coin, direction, entry, sl, tp, desc, created, signal_type, photo_file_id = row
            type_label = SIGNAL_TYPE_LABELS.get(signal_type, signal_type)
            dir_part = ""
            if direction:
                emoji = "🟢" if direction == "LONG" else "🔴"
                dir_part = f"  {emoji} {direction}"
            price_part = ""
            if entry or sl or tp:
                price_part = f"💵  ورود: <code>{entry or '—'}</code>  🛑 <code>{sl or '—'}</code>  🎯 <code>{tp or '—'}</code>\n"
            desc_line = f"\n📝  {esc(desc[:250])}" if desc else ""
            caption = (
                f"<b>سیگنال #{sid}</b>  {type_label}  —  👤 {esc(name) or '@'+esc(uname)}\n{SEP}\n"
                f"<b>{esc(coin)}</b>{dir_part}\n"
                f"{price_part}"
                f"{desc_line}\n🕐  {created[:16]}"
            )
            if signal_type == "full" and photo_file_id:
                await safe_send_photo(context.bot, chat_id=q.message.chat_id, photo=photo_file_id,
                                      caption=caption, reply_markup=approve_reject_kb(sid), parse_mode=ParseMode.HTML)
            else:
                await safe_send_message(context.bot, chat_id=q.message.chat_id, text=caption,
                                        reply_markup=approve_reject_kb(sid), parse_mode=ParseMode.HTML)

    elif data.startswith("approve_"):
        if not can_review:
            return
        sid = int(data.split("_")[1])
        row = signals_repo.get_signal_owner(sid)
        signals_repo.set_signal_status(sid, "approved", reviewed_by=user.id)
        await q.edit_message_text(f"✅  سیگنال #{sid} تأیید شد.")
        if row:
            uid, coin, direction, photo_file_id, signal_type, description, channel = row
            photo_url = None
            if photo_file_id:
                photo_url = await image_upload.upload_telegram_photo(context.bot, photo_file_id, sid)
            await site_sync.push_signal_created(
                bot_signal_id=sid, owner_telegram_id=uid, coin=coin, direction=direction,
                signal_type=signal_type, note=description or "", photo_url=photo_url, channel=channel,
                caller_name=users_repo.get_full_name(uid)
            )
            dir_part = ""
            if direction:
                emoji = "🟢" if direction == "LONG" else "🔴"
                dir_part = f"  {emoji} {direction}"
            await safe_send_message(context.bot, chat_id=uid,
                text=(
                    f"🎉  <b>سیگنال #{sid} تأیید شد!</b>\n{SEP}\n\n"
                    f"<b>{esc(coin)}</b>{dir_part}\n\n"
                    f"سیگنالت توی فید عمومی و لیدربورد قرار گرفت ✅"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[btn("📊  آمار من","menu_stats","primary")]]))

    elif data.startswith("reject_"):
        if not can_review:
            return
        sid = int(data.split("_")[1])
        row = signals_repo.get_signal_owner(sid)
        signals_repo.set_signal_status(sid, "rejected", reviewed_by=user.id)
        await q.edit_message_text(f"❌  سیگنال #{sid} رد شد.")
        if row:
            uid = row[0]
            await safe_send_message(context.bot, chat_id=uid,
                text=f"❌  <b>سیگنال #{sid} رد شد</b>\n\nبا ادمین در ارتباط باش.",
                parse_mode=ParseMode.HTML)

    elif data == "adm_result":
        if not is_admin:
            return
        rows = signals_repo.get_open_approved_signals(limit=15)
        if not rows:
            await q.answer("سیگنال باز تأییدشده‌ای نیست!", show_alert=True)
            return
        await q.edit_message_text("<b>🎯  ثبت نتیجه سیگنال‌ها</b>", parse_mode=ParseMode.HTML)
        for sid, name, coin, direction, entry, signal_type in rows:
            type_label = SIGNAL_TYPE_LABELS.get(signal_type, signal_type)
            dir_part = ""
            if direction:
                emoji = "🟢" if direction == "LONG" else "🔴"
                dir_part = f"  {emoji} {direction}"
            entry_part = f" @ {entry}" if entry else ""
            await safe_send_message(context.bot, chat_id=q.message.chat_id,
                text=f"<b>#{sid}</b>  {type_label}  {esc(coin)}{dir_part}{entry_part}  —  👤 {esc(name)}",
                reply_markup=signal_result_kb(sid), parse_mode=ParseMode.HTML)

    elif data.startswith("setresult_"):
        if not is_admin:
            return
        parts  = data.split("_", 2)
        sid    = int(parts[1])
        result = parts[2]
        outcome = results.apply_result(sid, result, set_by_user_id=user.id)
        if not outcome["ok"]:
            msg = "سیگنال پیدا نشد!" if outcome["error"] == "not_found" else "این سیگنال هنوز تأیید نشده!"
            await q.answer(msg, show_alert=True)
            return
        uid, coin, direction = outcome["owner_id"], outcome["coin"], outcome["direction"]
        pts, new_pts = outcome["new_points"], outcome["new_total_points"]
        await site_sync.push_signal_result(bot_signal_id=sid, result_key=result, points=pts)
        label = RESULT_LABEL.get(result, result)
        streak_msg = ""
        if outcome["milestone"]:
            s_row = users_repo.get_streak_info(uid)
            current_streak = s_row[0] if s_row else ""
            streak_msg = (
                f"\n\n🔥  <b>استریک {current_streak}!</b>\n"
                f"بونوس: +{outcome['bonus']} امتیاز اضافه شد 🎁"
            )
        # اگه این آپدیت (نه اولین‌بار) بود، به‌جای امتیاز نتیجه، تفاوتِ اعمال‌شده رو نشون بده
        shown_pts  = pts if outcome["is_first_time"] else outcome["delta_points"]
        shown_sign = "+" if shown_pts >= 0 else ""
        update_note = "" if outcome["is_first_time"] else (
            f"\n<i>(اصلاح نتیجه‌ی قبلی — {RESULT_LABEL.get(outcome['old_result'], outcome['old_result'])} → {label})</i>"
        )
        dir_part = f" {direction}" if direction else ""
        await safe_send_message(context.bot, chat_id=uid,
            text=(
                f"{'🎉' if pts>0 else '😔'}  <b>نتیجه سیگنال #{sid}</b>\n{SEP}\n\n"
                f"کوین:   <b>{esc(coin)}{dir_part}</b>\n"
                f"نتیجه:  {label}{update_note}\n"
                f"امتیاز: <b>{shown_sign}{shown_pts} ⭐️</b>\n"
                f"سطح:    <b>{scoring.get_level(new_pts)}</b>"
                f"{streak_msg}"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn("📊 آمار من","menu_stats","primary")]]))
        await q.edit_message_text(f"✅  نتیجه #{sid} ثبت شد  —  {label}")

    elif data == "adm_fixresult":
        if not is_admin:
            return
        context.chat_data["step"] = "admin_fix_result_id"
        await q.edit_message_text(
            "🔧  <b>اصلاح نتیجه‌ی یک سیگنال</b>\n\n"
            "شماره‌ی سیگنال رو بفرست (همون #عددی که تو پیام‌ها می‌بینی).\n"
            "برای سیگنال‌های خودگزارش‌دهی‌شده یا نتیجه‌ی قبلاً ثبت‌شده هم کار می‌کنه.",
            parse_mode=ParseMode.HTML, reply_markup=back_main_kb())

    elif data == "adm_donations":
        if not is_admin:
            return
        pool_rows = prize_repo.get_recent_donations(limit=10)
        support_rows = caller_donations_repo.get_recent_all(limit=10)
        if not pool_rows and not support_rows:
            await q.answer("واریزی وجود نداره!", show_alert=True)
            return
        lines = [f"<b>💰  واریزهای اخیر به استخر</b>\n{SEP}\n\n"]
        if pool_rows:
            for pid, name, amount, status, added in pool_rows:
                icon = "✅" if status == "paid" else "⏳"
                lines.append(f"{icon}  <b>{esc(name)}</b>  —  {amount}$  —  {added[:16]}\n")
        else:
            lines.append("📭  هیچی نیست\n")
        lines.append(f"\n{SEP}\n<b>💝  حمایت‌های مستقیم اخیر</b>\n{SEP}\n\n")
        if support_rows:
            for did, donor_name, recipient_name, amount, status, added in support_rows:
                icon = "✅" if status == "paid" else "⏳"
                lines.append(f"{icon}  <b>{esc(donor_name)}</b> → <b>{esc(recipient_name)}</b>  —  {amount}$  —  {added[:16]}\n")
        else:
            lines.append("📭  هیچی نیست\n")
        await q.edit_message_text("".join(lines), reply_markup=back_main_kb(), parse_mode=ParseMode.HTML)

    elif data == "adm_stats":
        if not is_admin:
            return
        total_users = users_repo.count_users()
        total_sigs  = signals_repo.count_total_signals()
        win_sigs    = signals_repo.count_win_signals()
        loss_sigs   = signals_repo.count_loss_signals()
        prize       = prize_repo.get_prize_pool_total()
        new_users   = users_repo.count_new_users_since((datetime.now()-timedelta(days=7)).isoformat())
        helpers     = staff_repo.list_vip_helpers()
        helpers_line = ""
        if helpers:
            names = ", ".join(esc(name or ('@'+uname if uname else uid)) for uid, name, uname in helpers)
            helpers_line = f"\n💎  VIP Helper ({len(helpers)}): {names}\n"
        await q.edit_message_text(
            f"<b>📊  آمار کلی ربات</b>\n{SEP}\n\n"
            f"👥  کل کاربران:      <b>{total_users}</b>\n"
            f"👤  کاربر جدید هفتگی: <b>{new_users}</b>\n"
            f"📡  کل سیگنال:       <b>{total_sigs}</b>\n"
            f"✅  سیگنال موفق:     <b>{win_sigs}</b>\n"
            f"❌  سیگنال ضرر:      <b>{loss_sigs}</b>\n"
            f"💰  کل استخر جایزه:  <b>{prize:.2f}$</b>"
            f"{helpers_line}\n{SEP}",
            reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "adm_broadcast":
        if not is_admin:
            return
        context.chat_data["step"] = "broadcast"
        await q.edit_message_text(
            f"<b>📢  پیام همگانی</b>\n{SEP}\n\nپیامت رو بنویس:\n(به همه کاربران ارسال میشه)",
            reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "adm_users":
        if not is_admin:
            return
        context.chat_data["step"] = "find_user"
        await q.edit_message_text(
            f"<b>👥  مدیریت کاربران</b>\n{SEP}\n\nیوزرنیم یا آیدی کاربر رو بنویس:",
            reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
        )

    elif data.startswith("block_"):
        if not is_admin:
            return
        target_id = int(data.split("_")[1])
        users_repo.set_blocked(target_id, True)
        await q.edit_message_text(f"🔒  کاربر {target_id} بلاک شد.")

    elif data.startswith("unblock_"):
        if not is_admin:
            return
        target_id = int(data.split("_")[1])
        users_repo.set_blocked(target_id, False)
        await q.edit_message_text(f"🔓  کاربر {target_id} آنبلاک شد.")

    elif data.startswith("setpts_"):
        if not is_admin:
            return
        target_id = int(data.split("_")[1])
        context.chat_data["step"] = "set_pts"
        context.chat_data["target_user_id"] = target_id
        await q.edit_message_text(
            f"<b>⭐  تنظیم امتیاز کاربر {target_id}</b>\n\nامتیاز جدید رو بنویس (میتونه منفی باشه):",
            reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
        )

    elif data.startswith("setrole_"):
        if not is_admin:
            return
        target_id = int(data.split("_")[1])
        current_role = users_repo.get_role(target_id)
        await q.edit_message_text(
            f"<b>🎖  تغییر درجه‌ی کاربر {target_id}</b>\n\n"
            f"درجه‌ی فعلی: <b>{access.get_role_label(current_role)}</b>\n\nدرجه‌ی جدید رو انتخاب کن:",
            reply_markup=role_picker_kb(target_id), parse_mode=ParseMode.HTML
        )

    elif data.startswith("role_"):
        if not is_admin:
            return
        # فرمت: role_<user_id>_<role_key>
        _, target_id_str, role_key = data.split("_", 2)
        target_id = int(target_id_str)
        if role_key not in ROLE_LABELS:
            await q.answer("درجه‌ی نامعتبر!", show_alert=True)
            return
        users_repo.set_role(target_id, role_key)
        await q.edit_message_text(f"✅  درجه‌ی کاربر {target_id} به «{ROLE_LABELS[role_key]}» تغییر کرد.")
        await safe_send_message(context.bot, chat_id=target_id,
            text=f"🎖  <b>درجه‌ی شما تغییر کرد!</b>\n\nدرجه‌ی جدید: <b>{ROLE_LABELS[role_key]}</b>",
            parse_mode=ParseMode.HTML)

    elif data.startswith("vip_add_"):
        if not is_admin:
            return
        target_id = int(data.split("_")[2])
        staff_repo.add_vip_helper(target_id, added_by=user.id)
        await q.edit_message_text(f"✅  کاربر {target_id} به VIP Helper ارتقا یافت.")
        await safe_send_message(context.bot, chat_id=target_id,
            text="💎  <b>تبریک!</b> شما به عنوان VIP Helper منصوب شدید و حالا می‌تونید سیگنال‌های در انتظار رو تأیید/رد کنید.",
            parse_mode=ParseMode.HTML)

    elif data.startswith("vip_remove_"):
        if not is_admin:
            return
        target_id = int(data.split("_")[2])
        staff_repo.remove_vip_helper(target_id)
        await q.edit_message_text(f"🔻  دسترسی VIP Helper کاربر {target_id} حذف شد.")

    elif data.startswith("grantreward_"):
        if not is_admin:
            return
        target_id = int(data.split("_")[1])
        context.chat_data["step"] = "grant_reward"
        context.chat_data["reward_target_id"] = target_id
        await q.edit_message_text(
            f"<b>🎁  اعطای پاداش به کاربر {target_id}</b>\n{SEP}\n\n"
            f"مبلغ و دلیل رو با فاصله بنویس:\nمثال: <code>10 بهترین تحلیلگر هفته</code>",
            reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "adm_newseason":
        if not is_admin:
            return
        existing = prize_repo.get_active_season()
        if existing:
            await q.answer(f"یک فصل («{existing[1]}») از قبل فعاله. اول از «پایان دوره» تمومش کن.",
                           show_alert=True)
            return
        name = prize_repo.create_next_season(days=14)
        await q.edit_message_text(f"✅  فصل جدید «{name}» شروع شد.", reply_markup=back_main_kb())

    elif data == "adm_export":
        if not is_admin:
            return
        rows = signals_repo.export_rows()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["نام","یوزرنیم","امتیاز","سطح","استریک","سیگنال"])
        for row in rows:
            writer.writerow(row)
        output.seek(0)
        csv_bytes = output.getvalue().encode("utf-8-sig")
        bio = io.BytesIO(csv_bytes)
        bio.name = "leaderboard.csv"
        await safe_send_document(context.bot, chat_id=q.message.chat_id,
            document=InputFile(bio, filename="leaderboard.csv"),
            caption="📊  خروجی لیدربورد")

    elif data == "adm_endseason":
        if not is_admin:
            return
        context.chat_data["step"] = "endseason_confirm"
        await q.edit_message_text(
            f"<b>🏆  پایان دوره و تقسیم جایزه</b>\n{SEP}\n\n"
            f"💰  استخر فعلی: <b>{prize_repo.get_prize_pool_total():.2f}$</b>\n\n"
            f"تقسیم:\n🥇 ۵۰٪ → نفر اول\n🥈 ۳۰٪ → نفر دوم\n🥉 ۲۰٪ → نفر سوم\n\n"
            f"برای تأیید بنویس: <code>تأیید</code>",
            reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
        )


# ══════════════════════════════════════════════════════════
#  مراحل ورودی متنی پنل ادمین (صدا زده می‌شه از handlers/text_router.py)
# ══════════════════════════════════════════════════════════
async def handle_step_set_solana_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    if user.id not in ADMIN_IDS:
        return
    from signal_bot.site.kv import kv_set, kv_delete
    text = text.strip()
    if text == "-":
        kv_delete("settings:solana_donate_wallet")
        await update.message.reply_html("✅  آدرس ولت حذف شد — دکمه‌ی «واریز مستقیم» دیگه نشون داده نمی‌شه.")
    else:
        kv_set("settings:solana_donate_wallet", text)
        await update.message.reply_html(f"✅  آدرس ولت ذخیره شد:\n<code>{esc(text)}</code>")
    context.chat_data.clear()


async def handle_step_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    if user.id not in ADMIN_IDS:
        return
    all_users = users_repo.list_unblocked_user_ids()
    sent = 0
    for uid in all_users:
        ok = await safe_send_message(context.bot, chat_id=uid,
                                     text=f"📢  <b>پیام از ادمین</b>\n{SEP}\n\n{esc(text)}",
                                     parse_mode=ParseMode.HTML)
        if ok:
            sent += 1
    prize_repo.insert_broadcast(user.id, text, sent)
    await update.message.reply_html(f"✅  پیام به <b>{sent}</b> کاربر ارسال شد.")
    context.chat_data.clear()


async def handle_step_find_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    if user.id not in ADMIN_IDS:
        return
    if text.isdigit():
        row = users_repo.find_by_id(int(text))
    else:
        row = users_repo.find_by_username(text.lstrip("@"))
    if not row:
        await update.message.reply_text("کاربری پیدا نشد!")
        return
    uid, fname, uname, pts, blocked, role = row
    status = "🔒 بلاک" if blocked else "✅ فعال"
    is_vip_now = access.is_vip_helper(uid)
    admin_role_label = access.get_admin_role_label(uid)
    admin_line = f"\nرول مدیریتی: <b>{admin_role_label}</b>" if admin_role_label else ""
    await update.message.reply_html(
        f"<b>👤  کاربر پیدا شد</b>\n{SEP}\n\n"
        f"نام: <b>{esc(fname)}</b>\n"
        f"یوزر: @{esc(uname)}\n"
        f"آیدی: <code>{uid}</code>\n"
        f"🎖  درجه: <b>{access.get_role_label(role)}</b>\n"
        f"امتیاز: <b>{pts}</b>\n"
        f"وضعیت: {status}"
        f"{admin_line}",
        reply_markup=user_manage_kb(uid, bool(blocked), is_vip_now)
    )
    context.chat_data.clear()


async def handle_step_set_pts(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    if user.id not in ADMIN_IDS:
        return
    target_id = context.chat_data.get("target_user_id")
    try:
        pts = int(text)
        scoring.add_points_and_sync(target_id, pts)
        sign = "+" if pts >= 0 else ""
        await update.message.reply_html(f"✅  {sign}{pts} امتیاز به کاربر {target_id} اضافه شد.")
    except ValueError:
        await update.message.reply_text("⚠️  عدد وارد کن!")
    context.chat_data.clear()


async def handle_step_admin_fix_result_id(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    if user.id not in ADMIN_IDS:
        return
    context.chat_data.clear()
    if not text.strip().lstrip("#").isdigit():
        await update.message.reply_text("⚠️  فقط شماره‌ی سیگنال (عدد) رو بفرست.")
        return
    sid = int(text.strip().lstrip("#"))
    row = signals_repo.get_signal_for_result(sid)
    if not row:
        await update.message.reply_text(f"سیگنال #{sid} پیدا نشد!")
        return
    owner_id, coin, direction, status, result, points = row
    if status != "approved":
        await update.message.reply_text(f"سیگنال #{sid} تأیید نشده، پس نتیجه‌ای براش قابل ثبت نیست.")
        return
    current = f"  (فعلی: {RESULT_LABEL.get(result, result)})" if result != "open" else "  (هنوز باز)"
    dir_part = f" {direction}" if direction else ""
    await update.message.reply_html(
        f"<b>#{sid}</b>  {esc(coin)}{dir_part}{current}\n\nنتیجه‌ی جدید رو انتخاب کن:",
        reply_markup=signal_result_kb(sid)
    )


async def handle_step_grant_reward(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    if user.id not in ADMIN_IDS:
        return
    target_id = context.chat_data.get("reward_target_id")
    parts = text.strip().split(maxsplit=1)
    try:
        amount = float(parts[0])
    except (ValueError, IndexError):
        await update.message.reply_text("⚠️  فرمت درست: مبلغ و بعدش دلیل رو با فاصله بنویس. مثال: 10 بهترین تحلیلگر هفته")
        return
    reason = parts[1].strip() if len(parts) > 1 else ""
    rewards_repo.insert_reward(target_id, amount, reason, user.id)
    await update.message.reply_html(f"✅  پاداش <b>{amount}</b> با دلیل «{esc(reason) or '—'}» برای کاربر {target_id} ثبت شد.")
    await safe_send_message(context.bot, chat_id=target_id,
        text=f"🎁  <b>پاداش جدید گرفتی!</b>\n{SEP}\n\n💰 {amount}\n📝 {esc(reason) or '—'}\n\nدست‌مریزاد! 🎉",
        parse_mode=ParseMode.HTML)
    context.chat_data.clear()


async def handle_step_endseason_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    if user.id not in ADMIN_IDS:
        return
    if text.strip() == "تأیید":
        total = prize_repo.get_prize_pool_total()
        top3 = signals_repo.get_top3_by_points()
        prizes = [0.5, 0.3, 0.2]
        season = prize_repo.get_active_season()
        season_id = season[0] if season else None
        result_text = f"<b>🏆  پایان دوره!</b>\n{SEP}\n\n💰  کل جایزه: {total:.2f}$\n\n"
        for i, (uid, fname, pts) in enumerate(top3):
            prize_amt = total * prizes[i]
            medal     = ["🥇","🥈","🥉"][i]
            result_text += f"{medal}  <b>{esc(fname)}</b>  —  {prize_amt:.2f}$\n"
            if season_id:
                prize_repo.insert_prize_winner(season_id, uid, i+1, prize_amt)
            await safe_send_message(context.bot, chat_id=uid,
                text=(
                    f"{medal}  <b>تبریک! رتبه {i+1} دوره!</b>\n\n"
                    f"جایزه: <b>{prize_amt:.2f} USDT</b>\n"
                    f"با ادمین برای دریافت جایزه در ارتباط باش."
                ),
                parse_mode=ParseMode.HTML)
        if season_id:
            prize_repo.end_season(season_id)
        next_name = prize_repo.create_next_season(days=14)
        result_text += f"\n{SEP}\n🆕  فصل جدید «{next_name}» خودکار شروع شد."
        await update.message.reply_html(result_text)
        if CHANNEL_ID:
            await safe_send_message(context.bot, chat_id=CHANNEL_ID, text=result_text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("لغو شد ❌")
    context.chat_data.clear()


async def cmd_markpaid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /markpaid USER_ID            — لیست پاداش‌های پرداخت‌نشده‌ی اون کاربر رو نشون می‌ده
    /markpaid USER_ID REWARD_ID  — همون ردیف رو paid می‌کنه

    ⚠️ rewards_repo.mark_paid() از اول همیشه تو کد بود ولی هیچ‌جا (نه دستور، نه
    دکمه) صداش نمی‌زد — یعنی my_rewards_text() که آیکون ✅/📝 رو بر اساس status
    نشون می‌ده، برای همیشه فقط 📝 می‌داد، حتی برای پاداش‌هایی که ادمین واقعاً
    (دستی، بیرون از بات) پرداخت کرده بود. عمداً فقط ADMIN_IDS، نه VIP Helper —
    چون این یه اقدام مالیه، نه بررسی سیگنال.
    """
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return
    raw = (update.message.text or "").split()
    if len(raw) < 2 or not raw[1].lstrip("-").isdigit():
        await update.message.reply_text(
            "استفاده:\n"
            "<code>/markpaid USER_ID</code> — لیست پاداش‌های پرداخت‌نشده‌ی اون کاربر\n"
            "<code>/markpaid USER_ID REWARD_ID</code> — همون ردیف رو paid کن",
            parse_mode=ParseMode.HTML,
        )
        return

    target_id = int(raw[1])
    if len(raw) >= 3 and raw[2].isdigit():
        reward_id = int(raw[2])
        row = rewards_repo.get_reward(reward_id)
        if not row or row[1] != target_id:
            await update.message.reply_text("⛔️  همچین پاداشی برای این کاربر پیدا نشد.")
            return
        if row[4] == "paid":
            await update.message.reply_text("این پاداش از قبل paid بود.")
            return
        rewards_repo.mark_paid(reward_id)
        await update.message.reply_text(
            f"✅  پاداش #{reward_id}  (💰{row[2]} — {esc(row[3]) or '—'})  الان paid شد.",
            parse_mode=ParseMode.HTML)
        return

    rows = rewards_repo.list_unpaid_for_user(target_id)
    if not rows:
        await update.message.reply_text("این کاربر پاداش پرداخت‌نشده‌ای نداره.")
        return
    lines = [f"<b>پاداش‌های پرداخت‌نشده‌ی {target_id}</b>\n{SEP}\n"]
    for rid, amount, reason, granted_at in rows:
        lines.append(f"#{rid}  💰{amount}  —  {esc(reason) or '—'}  ({granted_at[:16]})\n")
    lines.append(f"\nبرای paid‌کردن: <code>/markpaid {target_id} REWARD_ID</code>")
    await update.message.reply_text("".join(lines), parse_mode=ParseMode.HTML)
