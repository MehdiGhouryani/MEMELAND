"""
ارسال امن پیام/عکس به کاربران تلگرام.

چرا این ماژول: قبلاً هر جا ربات به کاربر/ادمین پیام می‌فرستاد، یک try/except Exception: pass
جدا و بی‌لاگ داشت (اگه کاربر ربات رو بلاک کرده باشه یا چتش پیدا نشه، خطا کاملاً بی‌صدا
قورت داده می‌شد). این ماژول یک نقطه‌ی مشترک می‌سازه: خطای تلگرام (نه هر Exception دلبخواهی)
رو می‌گیره، یک لاگ فشرده و بامعنی ثبت می‌کنه، و True/False برمی‌گردونه تا فراخواننده
در صورت نیاز خودش تصمیم بگیره (مثلاً برای شمارش ارسال موفق در broadcast).
"""
import logging

from telegram.error import TelegramError


async def safe_send_message(bot, chat_id, text, **kwargs) -> bool:
    try:
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return True
    except TelegramError as e:
        logging.warning(f"ارسال پیام به {chat_id} ناموفق: {e}")
        return False


async def safe_send_photo(bot, chat_id, photo, **kwargs) -> bool:
    try:
        await bot.send_photo(chat_id=chat_id, photo=photo, **kwargs)
        return True
    except TelegramError as e:
        logging.warning(f"ارسال عکس به {chat_id} ناموفق: {e}")
        return False


async def safe_send_document(bot, chat_id, document, **kwargs) -> bool:
    try:
        await bot.send_document(chat_id=chat_id, document=document, **kwargs)
        return True
    except TelegramError as e:
        logging.warning(f"ارسال فایل به {chat_id} ناموفق: {e}")
        return False
