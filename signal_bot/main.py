"""
نقطه ورود ربات. اجرا: python main.py
(قبلش .env رو بر اساس .env.example پر کن.)
"""
import logging
from datetime import datetime

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, PicklePersistence

from signal_bot.config import settings
from signal_bot.db import connection as db_connection
from signal_bot.db import prize_repo
from signal_bot.site import db as site_db
from signal_bot.site import auth as site_auth

from signal_bot.handlers import common, profile, signals, payments, support, admin
from signal_bot.handlers.text_router import text_handler
from signal_bot.jobs.scheduled import daily_leaderboard_post, notify_rank_changes, check_entry_alerts
from signal_bot.web.ipn_server import start_web_server

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
    error handler سراسری. مهم‌ترین موردی که اینجا مدیریت می‌کنیم:
    «Message is not modified» — وقتی کاربر دوبار پشت‌سرهم روی همون دکمه/تبی که
    از قبل بازه می‌زنه (مثلاً همون تب لیدربورد)، تلگرام این خطا رو می‌ده چون
    محتوای جدید با قبلی یکی‌ئه. این کاملاً بی‌خطره و نیازی به لاگ‌کردن با سطح
    error نداره. بقیه‌ی خطاهای مدیریت‌نشده رو با جزئیات لاگ می‌کنیم تا از بین
    نرن (قبلاً بدون این handler، PTB فقط یک لاگ عمومی می‌داد).
    """
    err = context.error
    from telegram.error import BadRequest
    if isinstance(err, BadRequest) and "message is not modified" in str(err).lower():
        logging.debug("کاربر روی همون محتوای فعلی دوباره کلیک کرد (بی‌خطر، نادیده گرفته شد).")
        return
    logging.error(f"خطای مدیریت‌نشده در پردازش یک آپدیت: {err}", exc_info=err)


def main():
    settings.setup_logging()
    settings.validate()

    db_connection.init_db()
    site_db.init_db()
    site_auth.bootstrap_pins_from_env()

    # اگه هیچ فصل فعالی نباشه (چه بار اول، چه بعد از پایان یک فصل بدون ری‌استارت
    # به موقع)، یکی می‌سازیم. قبلاً این چک count_seasons()==0 بود که فقط یک‌بار
    # در کل عمر دیتابیس true می‌شد — یعنی بعد از پایان اولین فصل، دیگه هیچ‌وقت
    # فصل جدیدی خودکار ساخته نمی‌شد (باگ ۱ گزارش ممیزی).
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

    # ── هندلرها ──────────────────────────────────────────
    app.add_handler(CommandHandler("start", common.start))
    app.add_handler(CommandHandler("help", common.cmd_help))
    app.add_handler(CommandHandler("fastcall", signals.cmd_fastcall))
    app.add_handler(CommandHandler("fullsignal", signals.cmd_fullsignal))
    app.add_handler(CommandHandler("markpaid", admin.cmd_markpaid))

    # نکته ترتیب: پترن‌های اختصاصی‌تر (dir_) قبل از پترن‌های عمومی‌تر ثبت می‌شن.
    app.add_handler(CallbackQueryHandler(signals.direction_callback, pattern="^dir_"))
    app.add_handler(CallbackQueryHandler(common.common_callback,
                                         pattern="^(back_main|cancel|menu_caller_hub)$"))
    app.add_handler(CallbackQueryHandler(profile.profile_callback,
                                         pattern="^(menu_leader|leader_week|leader_month|leader_all|"
                                                 "menu_stats|menu_profile|menu_profile_details|"
                                                 "menu_halloffame|menu_myrewards)$"))
    app.add_handler(CallbackQueryHandler(signals.signals_callback,
                                         pattern="^(menu_mysignals|mysig_open|mysig_approved|mysig_rejected|"
                                                 "menu_signal|sigtype_full|sigtype_fast|ch_.*|"
                                                 "menu_activesignals|fastcall_skipdir|"
                                                 "menu_myresults|myresult_.*|selfresult_.*)$"))
    app.add_handler(CallbackQueryHandler(payments.payments_callback,
                                         pattern="^(menu_prize|menu_donate|donate_.*|checkpay_.*)$"))
    app.add_handler(CallbackQueryHandler(support.support_callback,
                                         pattern="^(support_.*|csupport_.*|checkcsupport_.*)$"))
    app.add_handler(CallbackQueryHandler(admin.admin_callback,
                                         pattern="^(menu_admin|adm_.*|approve_.*|reject_.*|"
                                                 "setresult_.*|block_.*|unblock_.*|setpts_.*|"
                                                 "setrole_.*|role_.*|vip_add_.*|vip_remove_.*|"
                                                 "grantreward_.*)$"))
    # fallback دفاعی: هر callback_data ناشناخته‌ای که با هیچ پترن بالا مچ نشه
    app.add_handler(CallbackQueryHandler(common.unhandled_callback))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.PHOTO, signals.photo_handler))

    # ── جاب‌های زمان‌بندی ──────────────────────────────────
    jq = app.job_queue
    if jq:
        jq.run_daily(daily_leaderboard_post, time=datetime.strptime("22:00", "%H:%M").time())
        jq.run_repeating(notify_rank_changes, interval=21600, first=60)
        jq.run_repeating(check_entry_alerts, interval=45, first=30)

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Signal Master Bot — فاز ۵ ✅")
    print("  ✅ Full/Fast Signal   ✅ Alpha Score        ")
    print("  ✅ رول‌ها/VIP Helper   ✅ حمایت مستقیم       ")
    print("  ✅ Reward مستقل        ✅ وب‌هوک IPN (اختیاری) ")
    print("  ✅ دستورات گروهی       ✅ پایان دوره خودکار    ")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    app.run_polling()


if __name__ == "__main__":
    main()
