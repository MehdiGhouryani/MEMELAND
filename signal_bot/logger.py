import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

# فرمت بسیار فشرده: [ماه-روز ساعت:دقیقه:ثانیه] [سطح] پیام
COMPACT_FORMAT = "%(asctime)s [%(levelname).1s] %(message)s"
DATE_FORMAT = "%m-%d %H:%M:%S"

formatter = logging.Formatter(COMPACT_FORMAT, datefmt=DATE_FORMAT)

# محدود به 2 مگابایت با حفظ حداکثر 2 فایل بکاپ
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

logger = logging.getLogger("memeland")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def get_recent_logs(lines: int = 35) -> str:
    """خواندن N خط آخر فایل لاگ بدون لود کردن کل فایل در رم"""
    if not os.path.exists(LOG_FILE):
        return "فایل لاگ هنوز ایجاد نشده است."
    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(0, os.SEEK_END)
            buffer = bytearray()
            pointer = f.tell()
            line_count = 0

            while pointer > 0 and line_count <= lines:
                pointer -= 1
                f.seek(pointer)
                char = f.read(1)
                if char == b"\n":
                    line_count += 1
                buffer.extend(char)

            buffer.reverse()
            # استخراج خطوط آخر
            text = buffer.decode("utf-8", errors="replace")
            return "\n".join(text.strip().splitlines()[-lines:])
    except Exception as e:
        return f"خطا در خواندن لاگ: {e}"