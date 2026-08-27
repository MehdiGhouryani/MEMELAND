"""
تایید initData تلگرام Web App — پیش‌نیاز لاگین از تو خودِ Mini App.

⚠️ فرمول این‌جا عمداً با services/ipn_signature.py و RPC فعلی telegram_login
(که برای Login Widget معمولیه) فرق داره:
  - Login Widget:  secret_key = SHA256(bot_token)                    [ساده]
  - WebApp initData: secret_key = HMAC_SHA256(key="WebAppData", bot_token) [تودرتو]
این تفاوت رسمی و مستنده (core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app) —
یعنی نمی‌شه از یه تابع تأیید برای هر دو استفاده کرد.

مثل ipn_signature.py، این سندباکس به یه کلاینت واقعی تلگرام دسترسی نداره،
پس نتونستم این رو رو یه initData واقعی (از WebApp واقعی، با bot_token واقعی)
تست کنم — فقط self-consistency تست شده (خودم initData امضا کردم، خودم تأیید
کردم، هم مسیر قبول‌شدن هم رد‌شدن). قبل از اعتماد کامل، حتماً با یه WebApp
واقعی (حتی یه دکمه‌ی تستی) امتحانش کن.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def _data_check_string(pairs) -> str:
    """طبق مستندات تلگرام: جفت‌های غیر از hash، مرتب‌شده الفبایی بر اساس کلید،
    با \\n به هم وصل — نه با &، و کلید hash خودش اصلاً تو رشته نمیاد."""
    filtered = [(k, v) for k, v in pairs if k != "hash"]
    filtered.sort(key=lambda kv: kv[0])
    return "\n".join(f"{k}={v}" for k, v in filtered)


def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400):
    """
    اگه initData معتبر و به‌اندازه‌ی کافی تازه باشه، دیکشنری کاربر (فیلد
    user، بعد از json.loads) رو برمی‌گردونه. وگرنه None — هیچ‌وقت raise
    نمی‌کنه (ورودی کاملاً از سمت کلاینت میاد، نباید بتونه سرور رو بترکونه).
    max_age_seconds پیش‌فرض ۲۴ ساعته (محافظت در برابر replay با initData قدیمی).
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None

    data = dict(pairs)
    received_hash = data.get("hash")
    if not received_hash:
        return None

    check_string = _data_check_string(pairs)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = data.get("auth_date", "")
    if not auth_date.isdigit():
        return None
    if time.time() - int(auth_date) > max_age_seconds:
        return None

    user_raw = data.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(user, dict) or "id" not in user:
        return None
    return user
