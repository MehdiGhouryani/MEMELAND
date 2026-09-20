"""
لاگر مرکزی — تنها منبع حقیقت برای همه‌ی لاگ‌های پروژه.

🚨 باگی که این فایل حل می‌کنه:
    قبلاً دو سیستم لاگ موازی وجود داشت:
      • settings.setup_logging()  →  logging.basicConfig(...) روی root
                                     با FileHandler("bot.log") تو پوشه‌ی جاری
      • logger.py (همین فایل)     →  logger "memeland" با RotatingFileHandler
                                     روی signal_bot/logs/bot.log
    نتیجه:
      ۱. ماژول‌هایی که `logging.info(...)` صدا می‌زدن (ipn_server، site_sync،
         traders، connection) توی فایل *اول* می‌نوشتن.
      ۲. ماژول‌هایی که `logger.info(...)` صدا می‌زدن توی فایل *دوم*.
      ۳. `/logs` فقط فایل دوم رو می‌خوند ⇒ نصف لاگ‌ها اصلاً دیده نمی‌شدن.
      ۴. چون propagate روی logger "memeland" روشن بود، خطوطش هم به root
         می‌رفتن ⇒ توی کنسول دوبار چاپ می‌شدن و توی دو فایل ذخیره می‌شدن.
    الان: هندلرها فقط روی root نصب می‌شن. هم `logging.*` و هم
    `logger.*` دقیقاً یک بار، توی یک فایل می‌نویسن.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

# فرمت فشرده: [ماه-روز ساعت:دقیقه:ثانیه] [سطح] پیام
COMPACT_FORMAT = "%(asctime)s [%(levelname).1s] %(message)s"
DATE_FORMAT = "%m-%d %H:%M:%S"

_MAX_BYTES = 4 * 1024 * 1024
_BACKUPS = 3

# کتابخانه‌های پرحرف. بدون این، لاگ واقعی زیر صدها خط «HTTP Request: POST
# https://api.telegram.org/... 200 OK» (httpx، هر ثانیه یه polling) دفن
# می‌شه — همون چیزی که «لاگ فشرده‌تر» رو ضروری کرده بود.
_NOISY = {
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
    "telegram": logging.WARNING,
    "telegram.ext": logging.WARNING,
    "apscheduler": logging.WARNING,
    "aiohttp.access": logging.WARNING,
    "asyncio": logging.WARNING,
    "urllib3": logging.WARNING,
}

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """پیکربندی idempotent لاگ. چندبار صدا زدنش بی‌خطره."""
    global _configured
    if _configured:
        return

    formatter = logging.Formatter(COMPACT_FORMAT, datefmt=DATE_FORMAT)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # هندلرهای قبلی (مثلاً از یه basicConfig زودهنگام) پاک می‌شن تا دوباره‌نویسی نشه.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    for name, lv in _NOISY.items():
        logging.getLogger(name).setLevel(lv)

    _configured = True


# لاگر نام‌دار پروژه. عمداً *هیچ هندلری* نداره — می‌ذاره رکورد به root
# propagate بشه و دقیقاً یک بار نوشته بشه.
logger = logging.getLogger("memeland")
logger.setLevel(logging.INFO)

# اگه هر ماژولی قبل از main() این فایل رو import کنه، لاگش گم نشه.
setup_logging()


def get_recent_logs(lines: int = 35, level: str = None, contains: str = None) -> str:
    """
    N خط آخر فایل لاگ، بدون لود کردن کل فایل در رم.

    فیکس نسبت به نسخه‌ی قبلی:
      • قبلاً بایت‌به‌بایت به عقب seek می‌کرد (یک syscall به ازای هر بایت).
        الان بلاک ۶۴ کیلوبایتی می‌خونه.
      • فیلتر سطح و متن اضافه شد، چون وقتی دنبال یه خطای خاصی، ۱۰۰ خط
        INFO روتین عملاً بی‌فایده‌ست.

    level: 'E' | 'W' | 'I' | 'D' — فقط خطوطی با این سطح یا بالاتر.
    contains: فقط خطوطی که این رشته توشون هست (case-insensitive).
    """
    if not os.path.exists(LOG_FILE):
        return "فایل لاگ هنوز ایجاد نشده است."

    order = {"D": 0, "I": 1, "W": 2, "E": 3, "C": 4}
    min_rank = order.get((level or "").upper(), -1)
    needle = (contains or "").lower()

    def keep(line: str) -> bool:
        if min_rank >= 0:
            # فرمت: «09-20 20:09:51 [I] ...»
            lv = line[16:17] if len(line) > 17 and line[15:16] == "[" else "I"
            if order.get(lv, 1) < min_rank:
                return False
        if needle and needle not in line.lower():
            return False
        return True

    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 64 * 1024
            pos = size
            chunks = []
            collected = 0
            # کمی بیشتر از `lines` می‌خونیم چون ممکنه بعد از فیلتر، کم بیاریم.
            target = max(lines * 8, lines + 50)
            while pos > 0 and collected <= target:
                step = min(block, pos)
                pos -= step
                f.seek(pos)
                data = f.read(step)
                chunks.insert(0, data)
                collected += data.count(b"\n")
            text = b"".join(chunks).decode("utf-8", errors="replace")

        rows = [r for r in text.splitlines() if r.strip()]
        rows = [r for r in rows if keep(r)]
        if not rows:
            return "خطی با این فیلتر پیدا نشد."
        return "\n".join(rows[-lines:])
    except Exception as e:
        return f"خطا در خواندن لاگ: {e}"


def log_stats() -> dict:
    """آمار سریع فایل لاگ — برای دستور /diag."""
    if not os.path.exists(LOG_FILE):
        return {"exists": False}
    size = os.path.getsize(LOG_FILE)
    errs = warns = 0
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if len(line) > 17 and line[15:16] == "[":
                    if line[16] == "E":
                        errs += 1
                    elif line[16] == "W":
                        warns += 1
    except Exception:
        pass
    return {"exists": True, "path": LOG_FILE, "size_kb": round(size / 1024, 1),
            "errors": errs, "warnings": warns}
