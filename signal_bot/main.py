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
from signal_bot.logger import get_recent_logs, log_stats, LOG_FILE

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
    """
    لاگ‌های اخیر سرور — با فیلتر.

    قبلاً فقط «N خط آخر» بود. مشکل عملی: لاگ پر از خطوط روتین INFO می‌شه و
    برای پیدا کردن یه خطا باید چند بار /logs 100 می‌زدی و چشمی می‌گشتی.
    حالا:
        /logs            →  ۳۰ خط آخر
        /logs 80         →  ۸۰ خط آخر
        /logs err        →  فقط ERROR
        /logs warn       →  WARNING و بالاتر
        /logs js         →  فقط لاگ‌های کلاینت وب‌اپ
        /logs auth       →  هر خطی که «auth» توش باشه
        /logs err 60     →  ۶۰ خط آخر از ERROR ها
        /logs file       →  ارسال فایل کامل
    """
    user_id = update.effective_user.id
    if not site_auth._is_admin(user_id):
        return

    args = [a.lower() for a in (context.args or [])]

    if "file" in args:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "rb") as doc:
                await update.message.reply_document(
                    document=doc, filename="memeland_bot.log", caption="📄 لاگ کامل سرور"
                )
        else:
            await update.message.reply_text("فایل لاگ هنوز ایجاد نشده است.")
        return

    lines_count = 30
    level = None
    contains = None
    _ALIASES = {"err": "E", "error": "E", "warn": "W", "warning": "W", "info": "I", "debug": "D"}

    for a in args:
        if a.isdigit():
            lines_count = min(int(a), 120)
        elif a in _ALIASES:
            level = _ALIASES[a]
        elif a == "js":
            contains = "[js"
        else:
            contains = a

    recent_text = get_recent_logs(lines=lines_count, level=level, contains=contains)
    if len(recent_text) > 3800:
        recent_text = recent_text[-3800:]

    tag = []
    if level:
        tag.append({"E": "خطاها", "W": "هشدار به‌بالا", "I": "info", "D": "debug"}[level])
    if contains:
        tag.append(f"شامل «{contains}»")
    suffix = f" ({'، '.join(tag)})" if tag else ""

    await update.message.reply_text(
        f"📋 <b>آخرین {lines_count} خط لاگ{suffix}:</b>\n\n<code>{recent_text}</code>",
        parse_mode=ParseMode.HTML,
    )


async def handle_diag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /diag — یه عکس فوری از وضعیت سیستم، بدون نیاز به خوندن لاگ.

    این دستور دقیقاً برای جلوگیری از همون حلقه‌ی «لاگ بگیر، حدس بزن، دوباره
    دیپلوی کن» اضافه شده: هر چیزی که برای جواب دادن به «چرا وب‌اپ کار
    نمی‌کنه» لازمه، یک‌جا و با داده‌ی واقعی نشون داده می‌شه.
    """
    user_id = update.effective_user.id
    if not site_auth._is_admin(user_id):
        return

    from signal_bot.site import signals as site_signals
    from signal_bot.site.db import DB_FILE as SITE_DB_FILE

    def ok(v):
        return "✅" if v else "❌"

    try:
        feed_total = site_signals.get_feed(limit=1).get("total", 0)
    except Exception as e:
        feed_total = f"خطا: {e}"

    in_env = user_id in settings.ADMIN_IDS
    in_staff = site_auth._is_staff_admin(user_id)
    stats = log_stats()

    site_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "memeland_site")
    )
    html_ok = os.path.exists(os.path.join(site_dir, "index.html"))
    js_dir = os.path.join(site_dir, "static", "js")
    js_files = sorted(os.listdir(js_dir)) if os.path.isdir(js_dir) else []
    logger_deployed = "logger.js" in js_files

    lines = [
        "🩺 <b>وضعیت سیستم</b>",
        "",
        "<b>هویت شما</b>",
        f"• آیدی: <code>{user_id}</code>",
        f"• در ADMIN_IDS ({len(settings.ADMIN_IDS)} نفر): {ok(in_env)}",
        f"• در جدول staff: {ok(in_staff)}",
        "",
        "<b>دیتابیس</b>",
        f"• بات: <code>{os.path.abspath(settings.DB_FILE)}</code>",
        f"• سایت: <code>{os.path.abspath(SITE_DB_FILE)}</code>",
        f"• سیگنال در فید سایت: <b>{feed_total}</b>",
        f"• سشن‌های فعال: {site_auth.count_sessions()}",
        "",
        "<b>وب‌اپ</b>",
        f"• index.html: {ok(html_ok)}",
        f"• تعداد فایل JS: {len(js_files)}",
        f"• logger.js دیپلوی شده: {ok(logger_deployed)}",
        f"• SITE_URL: <code>{settings.SITE_URL or '—'}</code>",
        "",
        "<b>لاگ</b>",
        f"• حجم: {stats.get('size_kb', 0)} کیلوبایت",
        f"• خطا: {stats.get('errors', 0)} | هشدار: {stats.get('warnings', 0)}",
        "",
        "<i>برای جزئیات: /logs err 40</i>",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def _purge_sessions_job(context: ContextTypes.DEFAULT_TYPE):
    """پاک‌سازی دوره‌ی سشن‌های منقضی — قبلاً هیچ‌وقت چیزی حذف نمی‌شد."""
    site_auth.purge_expired_sessions()


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
    app.add_handler(CommandHandler("resync_signal", admin.cmd_resync_signal))
    app.add_handler(CommandHandler("sync_report", admin.cmd_sync_report))
    app.add_handler(CommandHandler(["logs", "syslog"], handle_logs_command))
    app.add_handler(CommandHandler("diag", handle_diag_command))

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
        jq.run_repeating(_purge_sessions_job, interval=86400, first=300)

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Signal Master Bot — فاز ۵ ✅")
    print("  ✅ Full/Fast Signal    ✅ Alpha Score        ")
    print("  ✅ رول‌ها/VIP Helper    ✅ حمایت مستقیم       ")
    print("  ✅ Reward مستقل        ✅ وب‌هوک IPN (اختیاری) ")
    print("  ✅ لاگر یکپارچه (/logs) ✅ تشخیص سریع (/diag)   ")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    app.run_polling()


if __name__ == "__main__":
    main()