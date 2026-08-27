"""ارتباط با API نوپیمنتس (NOWPayments) برای ساخت فاکتور و چک وضعیت پرداخت.

⚠️ create_invoice/check_payment قبلاً synchronous بودن (requests معمولی) ولی
مستقیم تو هندلرهای async صدا زده می‌شدن — یعنی موقع ساخت فاکتور یا چک پرداخت،
کل event loop بات (برای *همه‌ی* کاربرا، نه فقط اونی که پرداخت می‌کنه) تا
تموم‌شدن اون HTTP call (حداکثر timeout=10 ثانیه) بلاک می‌شد. الان بدنه‌ی
synchronous تو _sync گذاشته شده و با run_in_executor تو یه ترد جدا اجرا
می‌شه؛ امضای عمومی (create_invoice/check_payment) و رفتار خطاها دقیقاً
همونه، فقط الان باید await بشن."""
import asyncio
import logging
import uuid
import requests

from signal_bot.config import settings


def make_order_id(prefix: str) -> str:
    """
    شناسه‌ی یکتا برای هر فاکتور — قبلاً فقط timestamp ثانیه‌ای بود که تئوریاً
    اگه یک کاربر دوبار خیلی سریع (کمتر از ۱ ثانیه) فاکتور می‌ساخت، ممکن بود
    order_id تکراری بسازه (چون هر order_id باید در وب‌هوک به یک رکورد مشخص
    برگرده). الان یک پسوند کاملاً تصادفی هم اضافه می‌شه که تضمین می‌کنه یکتا
    باشه، صرف‌نظر از سرعت درخواست‌ها.
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _create_invoice_sync(amount_usd: float, order_id: str, user_name: str, ipn_callback_url: str = ""):
    headers = {"x-api-key": settings.NOWPAYMENTS_API, "Content-Type": "application/json"}
    payload = {
        "price_amount": amount_usd, "price_currency": "usd",
        "pay_currency": "usdttrc20", "order_id": order_id,
        "order_description": f"استخر جایزه — {user_name}",
        "success_url": settings.SUCCESS_URL, "cancel_url": settings.SUCCESS_URL,
        "is_fixed_rate": True, "is_fee_paid_by_user": False
    }
    if ipn_callback_url:
        payload["ipn_callback_url"] = ipn_callback_url
    try:
        r = requests.post(f"{settings.NOWPAYMENTS_BASE}/invoice", json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        # شامل: خطای شبکه، تایم‌اوت، و status code ناموفق (raise_for_status)
        logging.error(f"NOWPayments create_invoice ناموفق (order={order_id}): {e}")
        return None
    except ValueError as e:
        # پاسخ JSON نامعتبر بود
        logging.error(f"NOWPayments create_invoice: پاسخ نامعتبر (order={order_id}): {e}")
        return None


async def create_invoice(amount_usd: float, order_id: str, user_name: str, ipn_callback_url: str = ""):
    return await asyncio.get_event_loop().run_in_executor(
        None, _create_invoice_sync, amount_usd, order_id, user_name, ipn_callback_url
    )


def _check_payment_sync(payment_id: str) -> str:
    try:
        r = requests.get(f"{settings.NOWPAYMENTS_BASE}/payment/{payment_id}",
                         headers={"x-api-key": settings.NOWPAYMENTS_API}, timeout=10)
        r.raise_for_status()
        return r.json().get("payment_status", "unknown")
    except requests.RequestException as e:
        logging.warning(f"NOWPayments check_payment ناموفق (payment_id={payment_id}): {e}")
        return "unknown"
    except ValueError as e:
        logging.warning(f"NOWPayments check_payment: پاسخ نامعتبر (payment_id={payment_id}): {e}")
        return "unknown"


async def check_payment(payment_id: str) -> str:
    return await asyncio.get_event_loop().run_in_executor(None, _check_payment_sync, payment_id)
