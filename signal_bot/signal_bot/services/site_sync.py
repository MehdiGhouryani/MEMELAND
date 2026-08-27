"""
سینک بات → سایت (Memeland Hub). بعد از تأیید (دستی یا خودکار) یه سیگنال، یا
ثبت/آپدیت نتیجه‌ش، این ماژول همون رویداد رو به دیتابیس سایت منعکس می‌کنه.

بات و سایت هم‌محل‌ان (یه پروسه، دو SQLite جدا)، پس این‌جا فراخوانی مستقیم
تابع پایتونیه (signal_bot.site.signals)، نه HTTP. عمداً fire-and-forget:
یه خطای پیش‌بینی‌نشده تو نوشتن سایت نباید جریان اصلی بات رو بترکونه.
"""
import logging

from signal_bot.site import signals as site_signals

logger = logging.getLogger(__name__)

# نگاشت enum نتیجه‌ی بات (RESULT_LABEL تو config/settings.py) → (رشته‌ی نمایشی
# سایت, outcome_status سایت).
RESULT_TO_SITE = {
    "win_10x": ("🚀 بالای ۱۰ایکس", "win"),
    "win_5x":  ("💎 ۵ تا ۱۰ایکس", "win"),
    "win_2x":  ("✅ ۲ تا ۵ایکس", "win"),
    "win_sl":  ("🎯 SL/TP عالی", "win"),
    "loss":    ("❌ ضرر", "loss"),
}


async def push_signal_created(bot_signal_id: int, owner_telegram_id: int, coin: str,
                               direction, signal_type: str, note: str = "",
                               channel: str = "alt", tier: str = "free",
                               photo_url=None, caller_name: str = None) -> None:
    """بعد از تأیید (دستی یا خودکار) یه سیگنال، این رو صدا بزن. هیچ‌وقت raise نمی‌کنه.
    caller_name رو صداکننده از users_repo می‌گیره و پاس می‌ده. signal_type
    استفاده نمی‌شه — مدل داده‌ی سایت اصلاً معادلی نداره."""
    try:
        site_signals.create_signal(
            owner_telegram_id=owner_telegram_id, caller_name=caller_name, channel=channel,
            coin=coin or "", direction=direction, tier=tier, note=note or "", before_img=photo_url,
            source="bot", bot_signal_id=bot_signal_id,
        )
        logger.info("site_sync: سیگنال #%s به سایت منعکس شد", bot_signal_id)
    except Exception as e:
        logger.warning("site_sync: push_signal_created #%s خطا داد: %s", bot_signal_id, e)


async def push_signal_result(bot_signal_id: int, result_key: str, points: int) -> None:
    """بعد از apply_result (خودگزارش‌دهی یا ادمین)، این رو صدا بزن. هیچ‌وقت raise نمی‌کنه.
    points فقط برای سازگاری امضا نگه داشته شده — مدل داده‌ی سایت ستونی
    برای امتیاز نداره."""
    display, outcome = RESULT_TO_SITE.get(result_key, (result_key, "open"))
    try:
        site_id = site_signals.get_id_by_bot_signal_id(bot_signal_id)
        if site_id is None:
            logger.warning("site_sync: سیگنال بات #%s رو تو سایت پیدا نکردم (هنوز سینک نشده؟)", bot_signal_id)
            return
        site_signals.set_result(site_id, display, outcome)
        logger.info("site_sync: نتیجه‌ی سیگنال #%s به سایت منعکس شد", bot_signal_id)
    except Exception as e:
        logger.warning("site_sync: push_signal_result #%s خطا داد: %s", bot_signal_id, e)
