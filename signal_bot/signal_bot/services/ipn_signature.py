"""
تایید امضای callback های IPN نوپیمنتس (NOWPayments).

⚠️ این پیاده‌سازی بر اساس مستندات رسمی NOWPayments انجام شده (HMAC-SHA512 روی
JSON با کلیدهای مرتب‌شده الفبایی)، ولی چون این سندباکس به سرورهای NOWPayments
دسترسی نداره، نتونستم این رو در برابر یک IPN واقعی از سرور آن‌ها تست کنم — فقط
خودسازگاری الگوریتم رو تست کردم (پایین). قبل از اعتماد کامل به وب‌هوک، حتماً با
یک پرداخت واقعی و کوچیک تستش کن؛ دکمه‌ی «چک وضعیت پرداخت» دستی هم به‌عنوان
fallback نگه داشته شده و از کار نیفتاده.
"""
import hashlib
import hmac
import json


def _sorted_json_bytes(data: dict) -> bytes:
    """
    NOWPayments امضا رو روی JSON با کلیدهای مرتب‌شده الفبایی (به‌صورت بازگشتی)
    و بدون فاصله‌ی اضافه محاسبه می‌کنه.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_signature(payload: dict, ipn_secret: str) -> str:
    body = _sorted_json_bytes(payload)
    return hmac.new(ipn_secret.encode("utf-8"), body, hashlib.sha512).hexdigest()


def verify_signature(payload: dict, received_signature: str, ipn_secret: str) -> bool:
    """
    مقایسه‌ی امن (constant-time) امضای دریافتی با امضای محاسبه‌شده — از
    timing attack جلوگیری می‌کنه.
    """
    if not received_signature or not ipn_secret:
        return False
    expected = compute_signature(payload, ipn_secret)
    return hmac.compare_digest(expected, received_signature)
