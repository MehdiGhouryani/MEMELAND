"""
سرویس دانلود، اعمال خودکار واترمارک کپسولی و آپلود به Storage
"""
import io
import os
import uuid
import aiohttp
from telegram import Bot

from signal_bot.config import settings
from signal_bot.logger import logger
from signal_bot.services.watermark import apply_watermark

_TIMEOUT = aiohttp.ClientTimeout(total=15)
BUCKET = "signal-images"

# ⚠️ مسیر پوشه‌ی استاتیک وب‌اپ. از این ماژول (signal_bot/signal_bot/services)
# تا memeland_site دقیقاً همون فاصله‌ای‌ست که routes.py (signal_bot/signal_bot
# /site) داره — هر دو مستقیم زیر signal_bot/signal_bot هستن، پس همون سه‌تا
# ".." درست کار می‌کنه.
_SITE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "memeland_site")
)
_UPLOAD_DIR = os.path.join(_SITE_DIR, "static", "uploads")


def _enabled() -> bool:
    return bool(getattr(settings, "SITE_SUPABASE_URL", "") and getattr(settings, "SITE_SUPABASE_SERVICE_KEY", ""))


def _save_local(image_bytes: bytes, filename: str) -> str:
    """
    🚨 فال‌بک محلی — چرا لازم شد:
    پروژه از Supabase به SQLite محلی مهاجرت کرده و SITE_SUPABASE_URL/
    SERVICE_KEY تقریباً قطعاً دیگه ست نیستن. تا اینجا فقط مسیر آپلود *وب‌اپ*
    (routes.py::handle_image_upload) یه fallback محلی مخصوص خودش داشت.
    upload_telegram_photo — که برای عکسِ سیگنال‌های *تأییدشده‌ی ربات* صدا
    زده می‌شه (هم تو تأیید دستی ادمین، هم انتشار خودکار رول‌های بالا) — هیچ
    fallback ی نداشت و فقط None برمی‌گردوند. اثر عملی: تقریباً هر سیگنالی که
    از ربات با عکس تأیید می‌شد، روی سایت بدون عکس می‌موند — کاملاً بی‌صدا،
    بدون یک خط خطا تو لاگ.
    الان این fallback یه‌بار، در سطح _upload_bytes (نقطه‌ی مشترک هر دو
    مسیر) پیاده شده، پس هم upload_telegram_photo هم upload_web_image
    خودکار ازش استفاده می‌کنن — به‌جای اینکه هر Caller مجبور باشه خودش
    یادش بمونه fallback بسازه (دقیقاً همون الگوی باگی که routes.py قبلاً
    داشت و اینجا نداشت).
    """
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(_UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(image_bytes)
    return f"/static/uploads/{filename}"


async def _upload_bytes(image_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str | None:
    if not _enabled():
        try:
            public_url = _save_local(image_bytes, filename)
            logger.info(f"UploadOK(local): {filename}")
            return public_url
        except Exception as e:
            logger.error(f"UploadLocalErr: file={filename} err={e}")
            return None
    url = f"{settings.SITE_SUPABASE_URL.rstrip('/')}/storage/v1/object/{BUCKET}/{filename}"
    headers = {
        "apikey": settings.SITE_SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SITE_SUPABASE_SERVICE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(url, data=image_bytes, headers=headers) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.warning(f"UploadFail: code={resp.status} msg={body[:80]}")
                    return None
        public_url = f"{settings.SITE_SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{BUCKET}/{filename}"
        logger.info(f"UploadOK: {filename}")
        return public_url
    except Exception as e:
        logger.warning(f"UploadErr: {e}")
        return None


async def upload_telegram_photo(bot: Bot, file_id: str, signal_id: int) -> str | None:
    """
    دانلود عکس از تلگرام، اعمال واترمارک کپسولی، و آپلود نهایی.
    (⚠️ دیگه بی‌قید-و-شرط با _enabled() برنمی‌گرده — نگاه کن به توضیح
    _save_local بالا.)
    """
    try:
        tg_file = await bot.get_file(file_id)
        raw_bytes = bytes(await tg_file.download_as_bytearray())
        logger.info(f"TGPhotoDl: sig#{signal_id} sz={len(raw_bytes)}")
    except Exception as e:
        logger.warning(f"TGPhotoDlErr: sig#{signal_id} err={e}")
        return None

    # تزریق واترمارک قبل از ذخیره‌سازی و ارسال به سایت
    processed_bytes = apply_watermark(raw_bytes)

    filename = f"signal-{signal_id}-{uuid.uuid4().hex[:8]}.jpg"
    return await _upload_bytes(processed_bytes, filename)


async def upload_web_image(image_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str | None:
    """
    اعمال واترمارک و آپلود مستقیم تصویر ارسالی از مینی‌اپ وب.
    """
    processed_bytes = apply_watermark(image_bytes)
    return await _upload_bytes(processed_bytes, filename, content_type)