"""
پل تصویر بات→سایت (فاز ۳، سخت‌شده تو فاز ۳-ب). عکسی که کاربر تو Full Signal
می‌فرسته رو از تلگرام دانلود می‌کنه و به باکت Storage سایت (signal-images)
آپلود می‌کنه تا یه URL عمومی و دائمی بگیره — چون photo_file_id تلگرام نه
عمومیه نه دائمی.

⚠️ فاز ۳-ب: این ماژول قبلاً از SITE_SUPABASE_ANON_KEY (کلید عمومی، همونی که
تو HTML خودِ سایت هم دیده می‌شه) برای آپلود استفاده می‌کرد — یعنی هر کسی با
همون anon key می‌تونست مستقیم به باکت آپلود کنه، نه فقط بات. از این فاز به
بعد از SITE_SUPABASE_SERVICE_KEY (که Storage policy انسرت anon هم حذف شده
و service role خودش RLS/policy رو دور می‌زنه) استفاده می‌کنه. رجوع کن به
supabase_phase3b_storage_lockdown.sql.

⚠️ فرض این ماژول (طبق گفته‌ی خودت): واترمارک از قبل، جای دیگه‌ای خارج از این
پایپ‌لاین، رو عکس اعمال می‌شه («به هوش مصنوعی دادم، خودش می‌زنه»). این ماژول
فقط عکسی که از تلگرام گرفته رو، بدون تغییر، آپلود می‌کنه — واترمارک نمی‌زنه و
تشخیص نمی‌ده که آیا واترمارک داره یا نه. اگه فرآیند واقعی فرق داره (مثلاً باید
قبل از آپلود، یه API واترمارک صدا زده بشه)، این تابع دقیقاً جاییه که باید
اضافه بشه (رجوع کن به کامنت تو _upload_bytes).

⚠️ محدودیت تست: بخش HTTP-client این ماژول (ساخت درخواست، هدرها، مسیر) رو تست
کردم؛ ولی چون Storage واقعی Supabase رو نداشتم، رفتار واقعیِ باکت (پرمیژن‌ها،
اندازه‌ی مجاز فایل و...) رو نمی‌تونستم end-to-end تست کنم. قبل از تکیه‌کردن،
با یه سیگنال واقعی دستی امتحانش کن — مخصوصاً بعد از عوض‌کردن کلید به
service_role، حتماً یه آپلود واقعی رو تست کن که هنوز کار می‌کنه.

⚠️ fire-and-forget مثل site_sync: اگه آپلود شکست بخوره، فقط لاگ می‌شه و
None برمی‌گرده — سیگنال همچنان بدون عکس (یا با فقط عکس تلگرامی که از قبل
داشت) پردازش می‌شه؛ آپلود سایت هیچ‌وقت جلوی ثبت سیگنال تو خودِ بات رو نمی‌گیره.
"""
import logging
import uuid

import aiohttp
from telegram import Bot

from signal_bot.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=15)
BUCKET = "signal-images"


def _enabled() -> bool:
    return bool(getattr(settings, "SITE_SUPABASE_URL", "") and getattr(settings, "SITE_SUPABASE_SERVICE_KEY", ""))


async def _upload_bytes(image_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str | None:
    """آپلود خام به Storage با Service Role Key (نه anon — فاز ۳-ب). اگه بعداً
    خواستی واترمارک رو همین‌جا (قبل از آپلود) با یه API صدا بزنی، این دقیقاً
    همون نقطه‌ست."""
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
                    logger.warning("image_upload: آپلود ناموفق (%s): %s", resp.status, body[:300])
                    return None
        public_url = f"{settings.SITE_SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{BUCKET}/{filename}"
        return public_url
    except Exception as e:
        logger.warning("image_upload: exception: %s", e)
        return None


async def upload_telegram_photo(bot: Bot, file_id: str, signal_id: int) -> str | None:
    """
    عکس رو از تلگرام دانلود می‌کنه و به Storage سایت آپلود می‌کنه.
    خروجی: URL عمومی، یا None اگه سینک غیرفعال بود یا هر مرحله‌ای شکست خورد.
    هیچ‌وقت exception بالا نمی‌ده.
    """
    if not _enabled():
        return None
    try:
        tg_file = await bot.get_file(file_id)
        image_bytes = bytes(await tg_file.download_as_bytearray())
    except Exception as e:
        logger.warning("image_upload: دانلود از تلگرام ناموفق: %s", e)
        return None

    filename = f"signal-{signal_id}-{uuid.uuid4().hex[:8]}.jpg"
    return await _upload_bytes(image_bytes, filename)


async def upload_web_image(image_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str | None:
    """
    آپلود عکسی که مستقیم از سایت (نه تلگرام) اومده — برای قبل/بعدِ سیگنال از
    مسیر وب. همون _upload_bytes موجود رو صدا می‌زنه (خودش عمومیه، از قبل کار
    می‌کرد) بدون مرحله‌ی دانلود از تلگرام. اعتبارسنجی حجم/فرمت مسئولیتِ
    caller‌ه (site/routes.py) — این تابع فقط آپلود می‌کنه.
    """
    return await _upload_bytes(image_bytes, filename, content_type)
