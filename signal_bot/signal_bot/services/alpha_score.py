"""
سرویس محاسبه Alpha Score — معیار اعتبار هر تحلیلگر (بند ۸ نیازمندی‌ها).

⚠️ کاملاً مستقل از services/scoring.py (که سطح و استریک رو مدیریت می‌کنه) و از
total_pts — چون بند ۸ صراحتاً می‌خواد این معیار جدا و به‌سادگی قابل‌تغییر باشه.
اگه فردا فرمول بهتری پیشنهاد شد، فقط تابع calculate() اینجا عوض می‌شه؛ هیچ‌جای
دیگه‌ی کد (پروفایل، فید عمومی، لیدربورد، تابلوی افتخار) نیازی به تغییر نداره.

فرمول v1 — Wilson score lower bound روی نرخ برد:
همون روش شناخته‌شده‌ای که Reddit برای رتبه‌بندی کامنت‌ها استفاده می‌کنه. به‌جای
نرخ برد خام (wins/total)، یک تخمین محافظه‌کارانه از «نرخ برد واقعی» می‌ده که
اندازه‌ی نمونه رو هم در نظر می‌گیره:
- کسی با ۱ سیگنال و ۱ برد (نرخ خام ۱۰۰٪) نمره‌ی پایینی می‌گیره (~۲۰)، چون
  داده کافی برای اعتماد کامل نیست.
- کسی با ۴۰ سیگنال و ۳۲ برد (نرخ خام ۸۰٪) نمره‌ی بالایی می‌گیره (~۶۶-۷۰)،
  چون حجم داده بیشتر، اعتماد بیشتری به نرخ بردش می‌ده.
این دقیقاً هدف بند ۸ رو برآورده می‌کنه: «اعتبار» نه صرفاً «تعداد برد».
"""
import math

from signal_bot.config import settings
from signal_bot.db import signals_repo


def _wilson_lower_bound(wins: int, total: int, z: float = None) -> float:
    """پایین‌ترین حد بازه اطمینان برای نرخ برد — همیشه بین ۰ و ۱."""
    if total <= 0:
        return 0.0
    if z is None:
        z = settings.ALPHA_SCORE_CONFIDENCE_Z
    p_hat = wins / total
    denom = 1 + (z ** 2) / total
    center = p_hat + (z ** 2) / (2 * total)
    margin = z * math.sqrt((p_hat * (1 - p_hat) + (z ** 2) / (4 * total)) / total)
    return max(0.0, (center - margin) / denom)


def calculate(user_id):
    """
    خروجی: عدد بین ۰ تا ۱۰۰ (یک رقم اعشار)، یا None اگه کاربر هنوز هیچ سیگنال
    نتیجه‌گرفته‌ای (برد/باخت) نداشته باشه — یعنی «هنوز داده‌ای برای قضاوت نیست»،
    نه «صفر مطلق».
    سیگنال‌های Full Signal و Fast Call یکسان حساب می‌شن — چون نتیجه (برد/باخت)
    توسط ادمین یکسان و مستقل از نوع ثبت تعیین می‌شه.
    """
    results = signals_repo.get_result_counts(user_id, status="approved")
    losses = results.get("loss", 0)
    wins = sum(v for k, v in results.items() if k and k.startswith("win"))
    total = wins + losses
    if total == 0:
        return None
    return round(_wilson_lower_bound(wins, total) * 100, 1)


def get_label(user_id) -> str:
    """رشته‌ی آماده برای نمایش در UI."""
    score = calculate(user_id)
    return "—" if score is None else f"{score}"
