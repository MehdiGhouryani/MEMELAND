"""
منطق احراز هویت سایت — جایگزین تابع‌های Postgres قبلی (telegram_login,
session_user_role, claim_role, verify_pin). همه رو SQLite (site/db.py).

⚠️ فرمول Login Widget عمداً با WebApp initData (services/webapp_auth.py)
فرق داره: این‌جا secret_key = SHA256(bot_token) ساده‌ست، نه HMAC تودرتو.
دو مکانیزم رسمی جدای تلگرامن.
"""
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta

from signal_bot.site.db import get_db

SESSION_TTL_DAYS = 30
PIN_MAX_ATTEMPTS_PER_HOUR = 10


def verify_login_widget_payload(payload: dict, bot_token: str, max_age_seconds: int = 86400):
    """
    تأیید داده‌ی Telegram Login Widget. فرمول رسمی:
    secret_key = SHA256(bot_token) ؛ hash = HMAC_SHA256(data_check_string, secret_key)
    برمی‌گردونه دیکشنری کاربر (بدون hash) اگه معتبر بود، وگرنه None.
    """
    if not payload or not bot_token:
        return None
    data = dict(payload)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return None

    pairs = sorted((k, str(v)) for k, v in data.items() if v is not None)
    check_string = "\n".join(f"{k}={v}" for k, v in pairs)

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    computed_hash = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = data.get("auth_date")
    try:
        auth_date = int(auth_date)
    except (TypeError, ValueError):
        return None
    if time.time() - auth_date > max_age_seconds:
        return None

    return data


def create_session(telegram_id: int, username: str = None, first_name: str = None, photo_url: str = None) -> str:
    """Session جدید می‌سازه (یا نشست فعلی همون کاربر رو تمدید/جایگزین می‌کنه) و توکن برمی‌گردونه.
    ⚠️ عمداً هر بار یه نشست *جدید* insert می‌شه، نشست‌های قبلی همون کاربر رو
    پاک نمی‌کنه — یعنی چندتا دستگاه/تب هم‌زمان می‌تونن لاگین بمونن. اگه
    می‌خوای فقط یه نشست فعال به ازای کاربر مجاز باشه، بگو تا عوضش کنم."""
    token = secrets.token_hex(32)
    now = datetime.utcnow()
    expires = now + timedelta(days=SESSION_TTL_DAYS)
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (token, telegram_id, username, first_name, photo_url, role, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
        (token, telegram_id, username, first_name, photo_url, now.isoformat(), expires.isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def get_session(token: str):
    """معادل session_user_role — برمی‌گردونه dict(telegram_id, username, first_name, role) یا None اگه
    توکن نامعتبر/منقضی باشه."""
    if not token:
        return None
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT telegram_id, username, first_name, role, expires_at FROM sessions WHERE token=?", (token,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    telegram_id, username, first_name, role, expires_at = row
    if datetime.utcnow() > datetime.fromisoformat(expires_at):
        return None
    return {"telegram_id": telegram_id, "username": username, "first_name": first_name, "role": role}


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def _check_rate_limit(kind: str, actor_telegram_id) -> bool:
    """True یعنی هنوز زیر سقفه (اجازه‌ی تلاش هست). PIN_MAX_ATTEMPTS_PER_HOUR
    تلاش ناموفق در ساعت — قبل از این تابع، هیچ throttling ای رو verify_pin نبود."""
    conn = get_db()
    c = conn.cursor()
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    c.execute(
        "SELECT COUNT(*) FROM attempt_log WHERE kind=? AND actor_telegram_id=? AND created_at > ?",
        (kind, actor_telegram_id, one_hour_ago),
    )
    count = c.fetchone()[0]
    conn.close()
    return count < PIN_MAX_ATTEMPTS_PER_HOUR


def _log_attempt(kind: str, actor_telegram_id=None, actor_ip=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO attempt_log (kind, actor_telegram_id, actor_ip, created_at) VALUES (?, ?, ?, ?)",
        (kind, actor_telegram_id, actor_ip, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def set_pin(role: str, pin: str):
    """برای تنظیم اولیه‌ی PINها (ادمین/کالر/سابسکرایبر/کامیونیتی/آنلاک) — یه‌بار
    دستی صدا زده می‌شه (مثلاً از یه اسکریپت راه‌اندازی)، نه از سمت کلاینت."""
    from signal_bot.site.kv import kv_set
    kv_set(f"pin:{role}", _hash_pin(pin))


def bootstrap_pins_from_env():
    """⚠️ تا الان set_pin() هیچ‌جای پروژه صدا زده نمی‌شد — یعنی kv_store همیشه
    برای هر ۵ نقش خالی می‌موند و verify_pin/claim_role همیشه False برمی‌گردوندن،
    even با یه mySession کاملاً معتبر تلگرام (چون claim_role هم آخرش verify_pin
    رو صدا می‌زنه). این‌جا همون «اسکریپت راه‌اندازی»ای‌ه که دستور set_pin بالا
    ازش حرف می‌زد — main.py سر هر استارت صداش می‌زنه. عمداً فقط رو نقش‌هایی
    اثر می‌ذاره که هنوز تو دیتابیس پین ندارن (idempotent) — یه پین که یه‌بار
    ست شده رو دوباره از .env بازنویسی نمی‌کنه، که یعنی عوض‌کردن دستی یه پین
    (مستقیم تو kv_store) با ری‌استارت بعدی از بین نمی‌ره."""
    from signal_bot.config import settings
    from signal_bot.site.kv import kv_get
    role_env_map = {
        "admin": settings.ADMIN_PIN,
        "caller": settings.CALLER_PIN,
        "subscriber": settings.SUBSCRIBER_PIN,
        "community": settings.COMMUNITY_PIN,
        "unlock": settings.UNLOCK_PIN,
    }
    for role, pin in role_env_map.items():
        if pin and kv_get(f"pin:{role}") is None:
            set_pin(role, pin)


def verify_pin(role: str, pin: str, actor_telegram_id=None) -> bool:
    """معادل verify_pin RPC، با throttling روی هر actor — چه telegram_id واقعی
    (کاربر لاگین‌شده) چه شناسه‌ی IP (کاربر ناشناس، از routes.py). قبلاً
    actor=None کل throttle رو دور می‌زد؛ حالا fallback به یه سطل مشترک
    «anonymous» داره، نه عبور بی‌قید."""
    from signal_bot.site.kv import kv_get
    if not _check_rate_limit("pin", actor_telegram_id or "anonymous"):
        return False
    stored_hash = kv_get(f"pin:{role}")
    _log_attempt("pin", actor_telegram_id)
    if not stored_hash or not pin:
        return False
    return hmac.compare_digest(_hash_pin(pin), stored_hash)


def claim_role(token: str, role: str, pin: str) -> bool:
    """نقش رو رو یه session موجود قفل می‌کنه، اگه pin درست باشه. یک‌طرفه‌ست —
    بعد از claim شدن، دفعات بعدی دیگه نیازی به pin نیست (session.role چک می‌شه)."""
    session = get_session(token)
    if not session:
        return False
    if not verify_pin(role, pin, actor_telegram_id=session["telegram_id"]):
        return False
    conn = get_db()
    conn.execute("UPDATE sessions SET role=? WHERE token=?", (role, token))
    conn.commit()
    conn.close()
    return True
