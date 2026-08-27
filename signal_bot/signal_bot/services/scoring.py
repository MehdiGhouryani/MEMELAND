"""
منطق کسب‌وکاری امتیازدهی: محاسبه سطح، استریک و امتیاز نتیجه سیگنال.
این توابع منطق «تصمیم‌گیری» هستن و برای خواندن/نوشتن از db/users_repo.py استفاده می‌کنن
— هیچ SQL خامی اینجا نیست (طبق فاز ۱ نیازمندی‌ها).
"""
from signal_bot.config import settings
from signal_bot.db import users_repo


def get_level(pts: int) -> str:
    """سطح متناظر با یک مقدار امتیاز (تابع خالص، بدون دیتابیس)."""
    level = settings.LEVELS[0][1]
    for threshold, name in settings.LEVELS:
        if pts >= threshold:
            level = name
    return level


def update_user_level(user_id):
    """سطح کاربر رو بر اساس امتیاز فعلیش دوباره محاسبه و ذخیره می‌کنه."""
    pts = users_repo.get_total_pts(user_id)
    users_repo.set_level(user_id, get_level(pts))


def add_points_and_sync(user_id, delta: int):
    """
    نقطه‌ی واحد و امن برای هر تغییر امتیاز (مثبت یا منفی) در هر جای کد.

    ⚠️ چرا این تابع لازم بود: قبلاً هرجا امتیاز مستقیم با users_repo.add_points
    عوض می‌شد، باید جدا یادمون می‌موند update_user_level رو هم صدا بزنیم — و دو جا
    این یادمون رفته بود (تنظیم دستی امتیاز توسط ادمین، و بونوس استریک که *بعد* از
    محاسبه‌ی سطح اضافه می‌شد). نتیجه: سطح نمایش‌داده‌شده گاهی با امتیاز واقعی
    ناهماهنگ می‌موند تا سیگنال بعدی. با استفاده از همین یک تابع به‌جای صدازدن
    مستقیم users_repo.add_points، این کلاس باگ دیگه اصلاً نمی‌تونه رخ بده — سطح
    همیشه بلافاصله بعد از هر تغییر امتیاز، از نو محاسبه می‌شه.
    """
    users_repo.add_points(user_id, delta)
    update_user_level(user_id)


def get_result_points(result_key: str) -> int:
    return settings.POINT_TABLE.get(result_key, 0)


def update_streak(user_id, won: bool):
    """
    استریک کاربر رو آپدیت می‌کنه و در صورت رسیدن به یکی از نقاط بونوس
    (settings.STREAK_BONUS) امتیاز بونوس رو هم اضافه می‌کنه.
    خروجی: (bonus, milestone) — دقیقاً مثل نسخه قبلی.
    """
    row = users_repo.get_streak_info(user_id)
    if not row:
        return 0, False
    streak, max_streak, total_pts = row
    bonus = 0
    milestone = False
    if won:
        streak += 1
        if streak > max_streak:
            max_streak = streak
        if streak in settings.STREAK_BONUS:
            bonus = settings.STREAK_BONUS[streak]
            milestone = True
    else:
        streak = 0
    users_repo.set_streak(user_id, streak, max_streak)
    if bonus:
        add_points_and_sync(user_id, bonus)
    return bonus, milestone
