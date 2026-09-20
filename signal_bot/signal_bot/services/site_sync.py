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


# ══════════════════════════════════════════════════════════════════════════
#  جهت معکوس: سایت → ربات
#
#  🚨 تا این نسخه، سینک فقط یک‌طرفه بود (ربات → سایت). سیگنالی که از وب‌اپ
#  ثبت می‌شد هیچ‌وقت وارد دیتابیس ربات نمی‌شد، و چون تمام نماهای ربات از
#  جدول signals دیتابیس ربات می‌خونن، اون سیگنال‌ها در چت اصلاً وجود
#  نداشتن. این بخش اون شکاف رو می‌بنده.
# ══════════════════════════════════════════════════════════════════════════

import re

# ⚠️ مدل نتیجه‌ی دو طرف یکی نیست:
#   • سایت: یه متن آزاد ('+240%') + outcome_status از سه‌تایی open/win/loss
#   • ربات: یه کلید از مجموعه‌ی بسته (win_10x/win_5x/win_2x/win_sl/loss) که
#     مستقیم به جدول امتیاز (settings.POINT_TABLE) وصله
# برای سایت → ربات باید متن آزاد رو به یه کلید نگاشت کنیم. آستانه‌ها همون
# معنای ایکس‌محورِ برچسب‌های خودِ ربات‌ان (۲ایکس یعنی +۱۰۰٪، ۵ایکس یعنی
# +۴۰۰٪، ۱۰ایکس یعنی +۹۰۰٪). اگه هیچ عددی تو متن نبود، محافظه‌کارانه‌ترین
# حالتِ برد (win_sl، ۲ امتیاز) انتخاب می‌شه — نه بیشترین.
_X_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*[xX×]")
_PCT_PATTERN = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")


def site_result_to_bot_key(result_text: str, outcome_status: str) -> str:
    """('+240%', 'win') → 'win_2x'  ·  ('', 'loss') → 'loss'  ·  (…, 'open') → 'open'"""
    status = (outcome_status or "open").lower()
    if status == "loss":
        return "loss"
    if status != "win":
        return "open"

    text = str(result_text or "")

    m = _X_PATTERN.search(text)
    if m:
        try:
            multiple = float(m.group(1))
        except ValueError:
            multiple = 0.0
    else:
        m = _PCT_PATTERN.search(text)
        try:
            multiple = 1.0 + (float(m.group(1)) / 100.0) if m else 0.0
        except ValueError:
            multiple = 0.0

    if multiple >= 10:
        return "win_10x"
    if multiple >= 5:
        return "win_5x"
    if multiple >= 2:
        return "win_2x"
    return "win_sl"


def push_signal_from_site(site_signal_id: int, owner_telegram_id: int, coin: str,
                          direction=None, note: str = "", channel: str = "alt",
                          risk_level: str = "low", created_at: str = None,
                          display_name: str = None, username: str = None) -> bool:
    """
    یه سیگنالِ ثبت‌شده در وب‌اپ رو به دیتابیس ربات منعکس می‌کنه، و ردیف سایت
    رو هم به id جدید ربات لینک می‌کنه (لینک دوطرفه).

    ⚠️ نکته‌ی حیاتی: تقریباً همه‌ی کوئری‌های ربات
    `FROM signals s JOIN users u ON s.user_id=u.user_id` دارن. اگه کاربر
    ردیفی تو جدول users نداشته باشه (مثلاً هیچ‌وقت /start نزده و فقط از
    وب‌اپ استفاده کرده)، سیگنالش با JOIN حذف می‌شه و باز هم نامرئی می‌مونه —
    یعنی همون باگ، فقط یه لایه عمیق‌تر. پس اول وجود ردیف users تضمین می‌شه.
    """
    from signal_bot.db import signals_repo, users_repo
    from signal_bot.site import signals as site_signals

    if signals_repo.get_by_site_id(site_signal_id) is not None:
        return True  # از قبل سینک شده — idempotent

    try:
        users_repo.register_user(
            owner_telegram_id,
            username or "",
            display_name or f"User_{owner_telegram_id}",
        )
    except Exception as e:
        logger.warning("site_sync: ساخت ردیف users برای %s ناموفق: %s", owner_telegram_id, e)

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            bot_id = signals_repo.insert_from_site(
                site_signal_id=site_signal_id, user_id=owner_telegram_id, coin=coin or "",
                direction=direction, description=note or "", channel=channel or "alt",
                risk_level=risk_level or "low", created_at=created_at,
            )
            try:
                site_signals.set_bot_signal_id(site_signal_id, bot_id)
            except Exception as e:
                # لینک معکوس نتونست ست بشه (مثلاً تداخل UNIQUE). سیگنال خودش
                # سینک شده، پس این شکست کامل نیست — ولی باید دیده بشه.
                logger.warning("site_sync: لینک معکوس site#%s → bot#%s ناموفق: %s",
                               site_signal_id, bot_id, e)
            logger.info("site_sync: سیگنال سایت #%s → ربات #%s (تلاش %s)",
                        site_signal_id, bot_id, attempt)
            return True
        except sqlite3.OperationalError as e:
            logger.warning("site_sync: push_signal_from_site site#%s تلاش %s شکست (%s)",
                           site_signal_id, attempt, e)
            if attempt < _RETRY_ATTEMPTS:
                import time as _t
                _t.sleep(_RETRY_DELAY_SECONDS * attempt)
        except Exception as e:
            logger.error("site_sync: push_signal_from_site site#%s خطای غیرقابل‌تکرار: %s",
                         site_signal_id, e)
            return False
    logger.error("site_sync: push_signal_from_site site#%s بعد از %s تلاش شکست خورد",
                 site_signal_id, _RETRY_ATTEMPTS)
    return False


def push_result_from_site(site_signal_id: int, result_text: str, outcome_status: str) -> bool:
    """
    نتیجه‌ای که از وب‌اپ ثبت شده رو به ربات منعکس می‌کنه — از طریق همون
    services/results.apply_result که مسیر خودِ ربات هم استفاده می‌کنه، تا
    امتیاز/استریک/سطح دقیقاً یکسان حساب بشن و دو مسیر از هم جدا نیفتن.
    """
    from signal_bot.db import signals_repo
    from signal_bot.services import results

    bot_id = signals_repo.get_by_site_id(site_signal_id)
    if bot_id is None:
        logger.info("site_sync: سیگنال سایت #%s معادل رباتی نداره (سیگنال قدیمی؟)", site_signal_id)
        return False

    key = site_result_to_bot_key(result_text, outcome_status)
    if key == "open":
        return True  # چیزی برای امتیازدهی نیست

    try:
        outcome = results.apply_result(bot_id, key, set_by_user_id=0)
        if not outcome.get("ok"):
            logger.warning("site_sync: apply_result برای ربات #%s رد شد: %s",
                           bot_id, outcome.get("error"))
            return False
        logger.info("site_sync: نتیجه‌ی سایت #%s → ربات #%s key=%s pts=%s",
                    site_signal_id, bot_id, key, outcome.get("new_points"))
        return True
    except Exception as e:
        logger.error("site_sync: push_result_from_site site#%s خطا: %s", site_signal_id, e)
        return False


def delete_from_site(site_signal_id: int) -> bool:
    """وقتی یه سیگنال از وب‌اپ حذف می‌شه، ردیف متناظرش تو ربات هم باید بره،
    وگرنه دو طرف از هم جدا می‌افتن (همون واگرایی که داشت پیش می‌اومد)."""
    from signal_bot.db import signals_repo
    from signal_bot.db.connection import get_db

    bot_id = signals_repo.get_by_site_id(site_signal_id)
    if bot_id is None:
        return True
    try:
        conn = get_db()
        conn.execute("DELETE FROM signals WHERE id=?", (bot_id,))
        conn.commit()
        conn.close()
        logger.info("site_sync: سیگنال ربات #%s همراه سایت #%s حذف شد", bot_id, site_signal_id)
        return True
    except Exception as e:
        logger.error("site_sync: حذف ربات #%s ناموفق: %s", bot_id, e)
        return False


# ══════════════════════════════════════════════════════════════════════════
#  آشتی‌دادن دو دیتابیس (backfill)
#
#  سینک لحظه‌ای فقط سیگنال‌های *جدید* رو درست می‌کنه. هرچی قبل از این پچ
#  ثبت شده، همچنان فقط یک طرف وجود داره — همون «سیگنال‌های ثبتی قبلی فقط
#  تو چت دیده می‌شن». این تابع هر دو جهت رو یک‌بار می‌سازه.
# ══════════════════════════════════════════════════════════════════════════

async def reconcile(dry_run: bool = False) -> dict:
    """
    برمی‌گردونه dict با شمارش‌ها. هیچ‌وقت raise نمی‌کنه.
    dry_run=True فقط گزارش می‌ده و چیزی نمی‌نویسه.
    """
    from signal_bot.db import signals_repo, users_repo
    from signal_bot.site import signals as site_signals

    stats = {"bot_total": 0, "site_total": 0, "bot_to_site": 0, "site_to_bot": 0,
             "bot_failed": 0, "site_failed": 0, "already": 0}

    # ── جهت ۱: سیگنال‌های approvedِ ربات که تو سایت نیستن ────────────────
    approved, _linked = signals_repo.get_sync_snapshot()
    stats["bot_total"] = len(approved)
    for sid in approved:
        if site_signals.get_id_by_bot_signal_id(sid) is not None:
            stats["already"] += 1
            continue
        row = signals_repo.get_signal_owner(sid)
        if not row:
            continue
        uid, coin, direction, _photo, signal_type, description, channel, risk_level = row
        if dry_run:
            stats["bot_to_site"] += 1
            continue
        # عکس عمداً منتقل نمی‌شه: آپلود دوباره‌ی صدها فایل از تلگرام، هم کنده
        # هم ریسک rate-limit داره. متن و متادیتا مهم‌ترن؛ عکس برای سیگنال‌های
        # جدید از مسیر عادی منتقل می‌شه.
        ok = await push_signal_created(
            bot_signal_id=sid, owner_telegram_id=uid, coin=coin, direction=direction,
            signal_type=signal_type, note=description or "", photo_url=None,
            channel=channel or "alt", caller_name=users_repo.get_full_name(uid),
            risk_level=risk_level or "low",
        )
        stats["bot_to_site" if ok else "bot_failed"] += 1

    # ── جهت ۲: سیگنال‌های سایت که معادل رباتی ندارن ─────────────────────
    unlinked = site_signals.get_unlinked_rows()
    stats["site_total"] = site_signals.count_all()
    for row in unlinked:
        if dry_run:
            stats["site_to_bot"] += 1
            continue
        ok = push_signal_from_site(
            site_signal_id=row["id"], owner_telegram_id=row["owner_telegram_id"],
            coin=row["coin"], direction=row["direction"], note=row["note"] or "",
            channel=row["channel"] or "alt", risk_level=row["risk_level"] or "low",
            created_at=row["created_at"], display_name=row["caller_name"],
        )
        if ok and row.get("outcome_status") in ("win", "loss"):
            push_result_from_site(row["id"], row.get("result") or "", row["outcome_status"])
        stats["site_to_bot" if ok else "site_failed"] += 1

    logger.info(
        "site_sync reconcile%s: botTotal=%s siteTotal=%s bot→site=%s site→bot=%s "
        "already=%s failBot=%s failSite=%s",
        " (dry-run)" if dry_run else "", stats["bot_total"], stats["site_total"],
        stats["bot_to_site"], stats["site_to_bot"], stats["already"],
        stats["bot_failed"], stats["site_failed"],
    )
    return stats


def sync_health() -> dict:
    """عکس فوری از وضعیت سینک — برای /diag، بدون نوشتن چیزی."""
    from signal_bot.db import signals_repo
    from signal_bot.site import signals as site_signals
    try:
        approved, linked = signals_repo.get_sync_snapshot()
        site_total = site_signals.count_all()
        unlinked = len(site_signals.get_unlinked_rows())
        missing = sum(1 for sid in approved if site_signals.get_id_by_bot_signal_id(sid) is None)
        return {"bot_approved": len(approved), "site_total": site_total,
                "bot_missing_in_site": missing, "site_missing_in_bot": unlinked,
                "in_sync": missing == 0 and unlinked == 0}
    except Exception as e:
        return {"error": str(e), "in_sync": False}
