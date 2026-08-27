"""
منطق مشترکِ ثبت/به‌روزرسانیِ نتیجه‌ی یک سیگنال.

چرا این فایل جدا شد: دو مسیر متفاوت باید بتونن نتیجه‌ی یه سیگنال رو تنظیم کنن —
(۱) خودِ ثبت‌کننده‌ی سیگنال (خودگزارش‌دهی)، (۲) ادمین (تأیید اولیه یا اصلاح
بعدی). اگه این منطق تو هر دو جا (handlers/admin.py و handlers/signals.py)
جدا نوشته می‌شد، ریسک ناهماهنگی امتیاز/استریک بین این دو مسیر وجود داشت. حالا
دقیقاً یک‌جا نوشته شده و هر دو هندلر همینو صدا می‌زنن.

قانون کسب‌وکار (طبق خواسته‌ی کارفرما): نتیجه‌ی هر سیگنال قابل آپدیته — اگه یک
سیگنال قبلاً با یک نتیجه (مثلاً +۱۰۰٪ / win_2x) ثبت شده باشه و بعداً بیشتر بره
(مثلاً +۲۰۰٪ / win_5x)، نتیجه‌ی جدید جایگزین قبلی می‌شه و امتیاز نهایی بر اساس
*آخرین* نتیجه محاسبه می‌شه (نه جمع هر دو نتیجه).

⚠️ محدودیت شناخته‌شده (آگاهانه، برای اینکه بدونی، نه چیزی که یواشکی جا انداختیم):
استریک (🔥) فقط موقع *اولین‌بار* که نتیجه‌ی یک سیگنال ثبت می‌شه محاسبه می‌شه.
اگه یک نتیجه بعداً آپدیت بشه (چه ارتقای سطح برد، چه تغییر برد↔باخت)، فقط
تفاوتِ امتیاز اعمال می‌شه — استریک دوباره محاسبه نمی‌شه. چون بازسازیِ صحیحِ
استریک نیاز به نگه‌داشتنِ تاریخچه‌ی کامل هر تغییر داره (نه فقط آخرین نتیجه)،
این خارج از دامنه‌ی همین تغییر بود. اگه تغییرِ برد↔باخت (نه فقط ارتقای سطحِ
برد) پیش بیاد، ادمین می‌تونه با «⭐ تنظیم امتیاز» دستی استریک/امتیاز رو چک و
تصحیح کنه.

⚠️ فرض اعتماد: خودگزارش‌دهی به‌خودیِ خود جلوی گزارش نادرست/اغراق‌آمیز رو
نمی‌گیره — این عمداً طبق خواسته‌ی کارفرماست («نتیجه‌ی نهایی جایگزین و ملاک
باشه»). صمام اطمینان، امکانِ «اصلاح نتیجه با شماره‌ی سیگنال» برای ادمینه که تو
همین فایل و handlers/admin.py اضافه شده.
"""
from signal_bot.db import signals_repo, users_repo
from signal_bot.services import scoring


def apply_result(signal_id: int, result_key: str, set_by_user_id: int):
    """
    ثبت یا به‌روزرسانیِ نتیجه‌ی یک سیگنال (سیگنال باید status='approved' باشه).

    خروجی: dict.
      - در صورت موفقیت: {"ok": True, "owner_id", "coin", "direction",
        "is_first_time", "old_result", "delta_points", "new_points",
        "new_total_points", "bonus", "milestone"}
      - در صورت خطا: {"ok": False, "error": "not_found" | "not_approved"}
    """
    row = signals_repo.get_signal_for_result(signal_id)
    if not row:
        return {"ok": False, "error": "not_found"}
    owner_id, coin, direction, status, old_result, old_points = row
    if status != "approved":
        return {"ok": False, "error": "not_approved"}

    new_points    = scoring.get_result_points(result_key)
    is_first_time = (old_result == "open")

    if is_first_time:
        signals_repo.set_signal_result(signal_id, result_key, new_points, result_set_by=set_by_user_id)
        scoring.add_points_and_sync(owner_id, new_points)
        won = result_key != "loss"
        bonus, milestone = scoring.update_streak(owner_id, won)
        delta = new_points
    else:
        delta = new_points - old_points
        signals_repo.set_signal_result(signal_id, result_key, new_points, result_set_by=set_by_user_id)
        scoring.add_points_and_sync(owner_id, delta)
        bonus, milestone = 0, False

    return {
        "ok": True,
        "owner_id": owner_id,
        "coin": coin,
        "direction": direction,
        "is_first_time": is_first_time,
        "old_result": old_result,
        "delta_points": delta,
        "new_points": new_points,
        "new_total_points": users_repo.get_total_pts(owner_id),
        "bonus": bonus,
        "milestone": milestone,
    }
