"""
سینک بات → سایت (Memeland Hub). بعد از تأیید (دستی یا خودکار) یه سیگنال، یا
ثبت/آپدیت نتیجه‌ش، این ماژول همون رویداد رو به دیتابیس سایت منعکس می‌کنه.

بات و سایت هم‌محل‌ان (یه پروسه، دو SQLite جدا)، پس این‌جا فراخوانی مستقیم
تابع پایتونیه (signal_bot.site.signals)، نه HTTP. عمداً fire-and-forget به این
معنی که هیچ‌وقت raise نمی‌کنه (جریان اصلی بات نباید بترکه) — ولی برخلاف قبل،
دیگه کاملاً بی‌صدا نیست: خروجی True/False برمی‌گردونه تا فراخوان (مثلاً
admin.py) بتونه به کاربر واقعی نشون بده که سینک شکست خورده، نه این‌که فقط تو
لاگ گم بشه. همچنین برای خطاهای گذرا (مثلاً "database is locked" زیر بار
هم‌زمان) یه retry کوتاه داره.
"""
import asyncio
import logging
import sqlite3

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

_RETRY_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 0.4


async def push_signal_created(bot_signal_id: int, owner_telegram_id: int, coin: str,
                               direction, signal_type: str, note: str = "",
                               channel: str = "alt", tier: str = "free",
                               photo_url=None, caller_name: str = None,
                               risk_level: str = "low") -> bool:
    """بعد از تأیید (دستی یا خودکار) یه سیگنال، این رو صدا بزن. هیچ‌وقت raise
    نمی‌کنه؛ ولی True/False برمی‌گردونه تا فراخوان بفهمه سینک واقعاً موفق بوده
    یا نه (قبلاً همیشه None بود و شکست کاملاً بی‌صدا می‌موند).
    caller_name رو صداکننده از users_repo می‌گیره و پاس می‌ده. signal_type
    استفاده نمی‌شه — مدل داده‌ی سایت اصلاً معادلی نداره.
    risk_level: فیچر جدید (خواسته‌ی شریک) — پیش‌فرض کم‌ریسک."""
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            site_signals.create_signal(
                owner_telegram_id=owner_telegram_id, caller_name=caller_name, channel=channel,
                coin=coin or "", direction=direction, tier=tier, note=note or "", before_img=photo_url,
                source="bot", bot_signal_id=bot_signal_id, risk_level=risk_level,
            )
            logger.info("site_sync: سیگنال #%s به سایت منعکس شد (تلاش %s)", bot_signal_id, attempt)
            return True
        except sqlite3.IntegrityError:
            # bot_signal_id تو site.db یونیکه. اگه این خطا بگیریم، یعنی یه
            # فراخوانی هم‌زمان دیگه (مثلاً race بین تأیید عادی و
            # /resync_signal دستی) از قبل موفق سینک کرده — این خودش شکست
            # نیست، signal واقعاً تو سایت هست؛ برخلاف قبل که این حالت هم
            # False (به‌معنی «گم‌شده») گزارش می‌شد.
            logger.info("site_sync: سیگنال #%s ظاهراً هم‌زمان جای دیگه سینک شده (race)، نه شکست واقعی", bot_signal_id)
            return True
        except sqlite3.OperationalError as e:
            # این کلاس خطا (عمدتاً "database is locked") معمولاً گذراست —
            # ارزش یه retry کوتاه رو داره، برخلاف بقیه‌ی خطاها.
            logger.warning("site_sync: push_signal_created #%s تلاش %s شکست (%s)", bot_signal_id, attempt, e)
            if attempt < _RETRY_ATTEMPTS:
                await asyncio.sleep(_RETRY_DELAY_SECONDS * attempt)
        except Exception as e:
            logger.error("site_sync: push_signal_created #%s خطای غیرقابل‌تکرار: %s", bot_signal_id, e)
            return False
    logger.error("site_sync: push_signal_created #%s بعد از %s تلاش شکست خورد", bot_signal_id, _RETRY_ATTEMPTS)
    return False


async def push_signal_result(bot_signal_id: int, result_key: str, points: int) -> bool:
    """بعد از apply_result (خودگزارش‌دهی یا ادمین)، این رو صدا بزن. هیچ‌وقت raise
    نمی‌کنه؛ True/False برمی‌گردونه (نگاه کن به توضیح push_signal_created).
    points فقط برای سازگاری امضا نگه داشته شده — مدل داده‌ی سایت ستونی
    برای امتیاز نداره."""
    display, outcome = RESULT_TO_SITE.get(result_key, (result_key, "open"))
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            site_id = site_signals.get_id_by_bot_signal_id(bot_signal_id)
            if site_id is None:
                logger.warning("site_sync: سیگنال بات #%s رو تو سایت پیدا نکردم (هنوز سینک نشده؟)", bot_signal_id)
                return False
            site_signals.set_result(site_id, display, outcome)
            logger.info("site_sync: نتیجه‌ی سیگنال #%s به سایت منعکس شد (تلاش %s)", bot_signal_id, attempt)
            return True
        except sqlite3.OperationalError as e:
            logger.warning("site_sync: push_signal_result #%s تلاش %s شکست (%s)", bot_signal_id, attempt, e)
            if attempt < _RETRY_ATTEMPTS:
                await asyncio.sleep(_RETRY_DELAY_SECONDS * attempt)
        except Exception as e:
            logger.error("site_sync: push_signal_result #%s خطای غیرقابل‌تکرار: %s", bot_signal_id, e)
            return False
    logger.error("site_sync: push_signal_result #%s بعد از %s تلاش شکست خورد", bot_signal_id, _RETRY_ATTEMPTS)
    return False
