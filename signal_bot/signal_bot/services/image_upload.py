"""
سرویس دانلود، اعمال خودکار واترمارک کپسولی و آپلود به Storage
"""
import io
import uuid
import aiohttp
from telegram import Bot

from signal_bot.config import settings
from signal_bot.logger import logger
from signal_bot.services.watermark import apply_watermark

_TIMEOUT = aiohttp.ClientTimeout(total=15)
BUCKET = "signal-images"


def _enabled() -> bool:
    return bool(getattr(settings, "SITE_SUPABASE_URL", "") and getattr(settings, "SITE_SUPABASE_SERVICE_KEY", ""))


async def _upload_bytes(image_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str | None:
    if not _enabled():
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
    دانلود عکس از تلگرام، اعمال واترمارک کپسولی، و آپلود نهایی
    """
    if not _enabled():
        return None
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
    اعمال واترمارک و آپلود مستقیم تصویر ارسالی از مینی‌اپ وب
    """
    processed_bytes = apply_watermark(image_bytes)
    return await _upload_bytes(processed_bytes, filename, content_type)