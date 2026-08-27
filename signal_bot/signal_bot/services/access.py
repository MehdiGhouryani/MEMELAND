"""
منطق دسترسی و رول‌ها:
- تشخیص Admin / VIP Helper
- محدودیت ثبت سیگنال بر اساس رول کاربر
- برچسب نمایشی رول‌ها
"""
from signal_bot.config import settings
from signal_bot.db import staff_repo


def is_admin(user_id) -> bool:
    return user_id in settings.ADMIN_IDS


def is_vip_helper(user_id) -> bool:
    return staff_repo.is_vip_helper(user_id)


def can_review_signals(user_id) -> bool:
    """کسانی که مجاز به تأیید/رد سیگنال هستن: Admin یا VIP Helper (بند ۵ نیازمندی‌ها)."""
    return is_admin(user_id) or is_vip_helper(user_id)


def get_admin_role_label(user_id):
    """برچسب رول مدیریتی کاربر، یا None اگه هیچ‌کدوم نباشه."""
    if is_admin(user_id):
        return settings.ADMIN_ROLE_LABELS[settings.ADMIN_ROLE_ADMIN]
    if is_vip_helper(user_id):
        return settings.ADMIN_ROLE_LABELS[settings.ADMIN_ROLE_VIP_HELPER]
    return None


def get_role_label(role_key: str) -> str:
    return settings.ROLE_LABELS.get(role_key, settings.ROLE_LABELS[settings.DEFAULT_ROLE])


def get_daily_limit(role_key: str) -> int:
    """محدودیت روزانه ثبت سیگنال بر اساس رول — بند ۳ نیازمندی‌ها."""
    return settings.ROLE_DAILY_LIMITS.get(role_key, settings.DAILY_LIMIT)


def is_auto_publish_role(role_key: str) -> bool:
    """آیا سیگنال این رول بدون تأیید Admin/VIP Helper مستقیم منتشر می‌شه (Guardian+)."""
    return role_key in settings.AUTO_PUBLISH_ROLES


def get_role_limits_lines() -> str:
    """
    خط‌های آماده‌ی HTML برای نمایش سقف روزانه‌ی هر رول — مشترک بین /help عمومی
    و راهنمای پنل ادمین، تا هر دو همیشه از یک منبع واحد (تنظیمات واقعی) بخونن
    و اگه محدودیت‌ها بعداً عوض بشن، هر دو خودکار به‌روز بمونن.
    """
    return "\n".join(f"{label}: <b>{get_daily_limit(key)}</b>/روز" for key, label in settings.ROLES)


def next_role(role_key: str):
    """رول بعدی در نردبان رول‌ها، یا None اگه از قبل بالاترین رول باشه (برای UI کمکیه، جایی صدا زده نمی‌شه اجباری)."""
    keys = [k for k, _ in settings.ROLES]
    if role_key not in keys:
        return keys[0]
    idx = keys.index(role_key)
    return keys[idx + 1] if idx + 1 < len(keys) else None
