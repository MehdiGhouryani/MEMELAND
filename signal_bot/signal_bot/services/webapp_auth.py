"""
سرویس اعتبارسنجی Telegram WebApp initData

این ماژول وظیفه بررسی اصالت داده‌های ارسال‌شده از سمت Telegram Mini App را
بر اساس مستندات رسمی تلگرام (HMAC-SHA256 تودرتو) بر عهده دارد.
"""

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, unquote


def _sanitize_init_data(raw_data: str) -> str:
    """
    پاک‌سازی رشته ورودی از کاراکترها و پیشوندهای ناخواسته.
    اگر کلاینت کل URL یا هش مرورگر (#tgWebAppData=...) را فرستاده باشد،
    این تابع داده خالص را استخراج می‌کند.
    """
    raw = (raw_data or "").strip()
    if not raw:
        return ""

    if raw.startswith("#"):
        raw = raw[1:]

    if "tgWebAppData=" in raw:
        for part in raw.split("&"):
            if part.startswith("tgWebAppData="):
                raw = unquote(part.split("tgWebAppData=", 1)[1])
                break

    return raw


def _data_check_string(pairs: list[tuple[str, str]]) -> str:
    """
    تولید رشته اعتبارسنجی طبق استاندارد تلگرام:
    ۱. حذف پارامتر hash
    ۲. مرتب‌سازی الفبایی بر اساس نام کلیدها
    ۳. اتصال کلید و مقدار با '=' و ردیف‌ها با '\\n'
    """
    filtered = [(k, v) for k, v in pairs if k != "hash"]
    filtered.sort(key=lambda kv: kv[0])
    return "\n".join(f"{k}={v}" for k, v in filtered)


def verify_webapp_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> Optional[Dict[str, Any]]:
    """
    اعتبارسنجی جامع داده‌های WebApp تلگرام.

    در صورت معتبر بودن امضا، دیکشنری کاملی شامل اطلاعات کاربر، زمان ورود و
    پارامترهای مسیردهی (start_param) برمی‌گرداند؛ در غیر این صورت None.
    """
    clean_data = _sanitize_init_data(init_data)
    if not clean_data or not bot_token:
        return None

    try:
        pairs = parse_qsl(clean_data, keep_blank_values=True, strict_parsing=False)
    except Exception:
        return None

    if not pairs:
        return None

    data_dict = dict(pairs)
    received_hash = data_dict.get("hash")
    if not received_hash:
        return None

    check_string = _data_check_string(pairs)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date_raw = data_dict.get("auth_date", "")
    if not auth_date_raw.isdigit():
        return None

    auth_date = int(auth_date_raw)
    now = int(time.time())

    # مجاز دانستن تا ۵ دقیقه اختلاف ساعت سرور با کلاینت (Clock Drift)
    if auth_date > now + 300:
        return None

    if max_age_seconds > 0 and (now - auth_date) > max_age_seconds:
        return None

    user = None
    user_raw = data_dict.get("user")
    if user_raw:
        try:
            user = json.loads(user_raw)
            if isinstance(user, dict) and "id" in user:
                user["id"] = int(user["id"])
            else:
                user = None
        except (json.JSONDecodeError, TypeError, ValueError):
            user = None

    return {
        "user": user,
        "auth_date": auth_date,
        "query_id": data_dict.get("query_id"),
        "start_param": data_dict.get("start_param"),
        "chat_type": data_dict.get("chat_type"),
        "chat_instance": data_dict.get("chat_instance"),
        "raw_data": data_dict,
    }


def verify_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> Optional[Dict[str, Any]]:
    """
    تابع سازگار با امضای کدهای قبلی پروژه.
    دیکشنری کاربر را همراه با فیلدهای تکمیلی برمی‌گرداند.
    """
    payload = verify_webapp_data(init_data, bot_token, max_age_seconds)
    if not payload or not payload.get("user"):
        return None

    user = payload["user"]
    if payload.get("start_param"):
        user["start_param"] = payload["start_param"]
    user["auth_date"] = payload["auth_date"]
    return user