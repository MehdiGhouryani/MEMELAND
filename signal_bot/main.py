"""
نقطه ورود ربات. اجرا: python main.py
(قبلش .env رو بر اساس .env.example پر کن.)
"""
import os
import logging
from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    PicklePersistence,
    filters,
)

from signal_bot.config import settings
from signal_bot.db import connection as db_connection
from signal_bot.db import prize_repo
from signal_bot.site import db as site_db
from signal_bot.site import auth as site_auth

from signal_bot.handlers import common, profile, signals, payments, support, admin
from signal_bot.handlers.text_router import text_handler
from signal_bot.jobs.scheduled import (
    daily_leaderboard_post,
    notify_rank_changes,
    check_entry_alerts,
)
from signal_bot.web.ipn_server import start_web_server
from signal_bot.logger import get_recent_logs, LOG_FILE

WEB_RUNNER = None


async def _post_init(application):
    global WEB_RUNNER
    WEB_RUNNER = await start_web_server(application.bot)


async def _post_shutdown(application):
    global WEB_RUNNER
    if WEB_RUNNER:
        await WEB_RUNNER.cleanup()
        WEB_RUNNER = None
        logging.info("سرور وب بات خاموش شد.")


async def _error_handler(update, context):
    """
    error handler سراسری.
    خطای تکراری «Message is not modified» نادیده گرفته می‌شود.
    """
    err = context.error
    if isinstance(err, BadRequest) and "message is not modified" in str(err).lower():
        logging.debug("کاربر روی محتوای فعلی دوباره کلیک کرد (نادیده گرفته شد).")
        return
    logging.error(f"خطای مدیریت‌نشده در پردازش یک آپدیت: {err}", exc_info=err)


async def handle_logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت لاگ‌های اخیر سرور یا ارسال فایل کامل لاگ برای مدیران"""
    user_id = update.effective_user.id

    if not site_auth._is_admin(user_id):
        return

    # ارسال فایل لاگ با دستور: /logs file
    if context.args and context.args[0].lower() == "file":
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "rb") as doc:
                await update.message.reply_document(
                    document=doc,
                    filename="memeland_bot.log",
                    caption="📄 لاگ کامل سرور",
                )
        else:
            await update.message.reply_text("فایل لاگ هنوز ایجاد نشده است.")
        return

    lines_count = 30
    if context.args and context.args[0].isdigit():
        lines_count = min(int(context.args[0]), 100)

    recent_text = get_recent_logs(lines=lines_count)

    # محدودیت سقف کاراکتر تلگرام
    if len(recent_text) > 3800:
        recent_text = recent_text[-3800:]

    reply_msg = (
        f"📋 <b>آخرین {lines_count} خط لاگ سرور:</b>\n\n"
        f"<code>{recent_text}</code>"
    )
    await update.message.reply_text(reply_msg, parse_mode=ParseMode.HTML)


def main():
    settings.setup_logging()
    settings.validate()

    db_connection.init_db()
    site_db.init_db()
    site_auth.bootstrap_pins_from_env()

    if prize_repo.get_active_season() is None:
        prize_repo.create_next_season(days=14)

    app = (
        ApplicationBuilder()
        .token(settings.TOKEN)
        .persistence(PicklePersistence(filepath=settings.PERSISTENCE_FILE))
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.add_error_handler(_error_handler)

    # ── هندلرهای دستورات (Commands) ──────────────────────
    app.add_handler(CommandHandler("start", common.start))
    app.add_handler(CommandHandler("help", common.cmd_help))
    app.add_handler(CommandHandler("fastcall", signals.cmd_fastcall))
    app.add_handler(CommandHandler("fullsignal", signals.cmd_fullsignal))
    app.add_handler(CommandHandler("markpaid", admin.cmd_markpaid))
    app.add_handler(CommandHandler(["logs", "syslog"], handle_logs_command))

    # ── هندلرهای کال‌بک (Callbacks) ──────────────────────
    app.add_handler(CallbackQueryHandler(signals.direction_callback, pattern="^dir_"))
    app.add_handler(
        CallbackQueryHandler(
            common.common_callback, pattern="^(back_main|cancel|menu_caller_hub)$"
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            profile.profile_callback,
            pattern=(
                "^(menu_leader|leader_week|leader_month|leader_all|"
                "menu_stats|menu_profile|menu_profile_details|"
                "menu_halloffame|menu_myrewards)$"
            ),
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            signals.signals_callback,
            pattern=(
                "^(menu_mysignals|mysig_open|mysig_approved|mysig_rejected|"
                "menu_signal|sigtype_full|sigtype_fast|ch_.*|"
                "menu_activesignals|fastcall_skipdir|"
                "menu_myresults|myresult_.*|selfresult_.*)$"
            ),
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            payments.payments_callback,
            pattern="^(menu_prize|menu_donate|donate_.*|checkpay_.*)$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            support.support_callback,
            pattern="^(support_.*|csupport_.*|checkcsupport_.*)$",
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            admin.admin_callback,
            pattern=(
                "^(menu_admin|adm_.*|approve_.*|reject_.*|"
                "setresult_.*|block_.*|unblock_.*|setpts_.*|"
                "setrole_.*|role_.*|vip_add_.*|vip_remove_.*|"
                "grantreward_.*)$"
            ),
        )
    )
    app.add_handler(CallbackQueryHandler(common.unhandled_callback))

    # ── هندلرهای پیام و مدیا ─────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.PHOTO, signals.photo_handler))

    # ── جاب‌های زمان‌بندی (Job Queue) ────────────────────
    jq = app.job_queue
    if jq:
        jq.run_daily(
            daily_leaderboard_post,
            time=datetime.strptime("22:00", "%H:%M").time(),
        )
        jq.run_repeating(notify_rank_changes, interval=21600, first=60)
        jq.run_repeating(check_entry_alerts, interval=45, first=30)

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Signal Master Bot — فاز ۵ ✅")
    print("  ✅ Full/Fast Signal    ✅ Alpha Score        ")
    print("  ✅ رول‌ها/VIP Helper    ✅ حمایت مستقیم       ")
    print("  ✅ Reward مستقل        ✅ وب‌هوک IPN (اختیاری) ")
    print("  ✅ لاگر فشرده (/logs)   ✅ دستورات گروهی       ")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    app.run_polling()


if __name__ == "__main__":
    main()