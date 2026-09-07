"""
ماژول احراز هویت و مدیریت نشست‌ها در وب‌سرور Memeland
"""

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from signal_bot.config import settings
from signal_bot.services.webapp_auth import verify_webapp_data
from signal_bot.site.db import get_db

logger = logging.getLogger(__name__)

SESSION_TTL_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_admin(telegram_id: Any) -> bool:
    """بررسی قطعی عضویت شناسه در ADMIN_IDS فایل .env با تبدیل صریح به int"""
    if telegram_id is None:
        return False
    try:
        tid = int(telegram_id)
        admin_ids = [int(x) for x in getattr(settings, "ADMIN_IDS", [])]
        return tid in admin_ids
    except (ValueError, TypeError):
        return False


def _extract_display_name(first_name: Optional[str], username: Optional[str], telegram_id: int) -> str:
    if first_name and first_name.strip():
        return first_name.strip()[:64]
    if username and username.strip():
        return f"@{username.strip()[:63]}"
    return f"User_{telegram_id}"


def authenticate_webapp(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> Optional[Dict[str, Any]]:
    payload = verify_webapp_data(init_data, bot_token, max_age_seconds=max_age_seconds)
    if not payload or not payload.get("user"):
        return None

    user = payload["user"]
    telegram_id = int(user["id"])
    username = user.get("username")
    first_name = user.get("first_name")
    photo_url = user.get("photo_url")

    # تخصیص نقش ادمین منحصراً بر اساس تنظیمات .env
    is_adm = _is_admin(telegram_id)
    role = "admin" if is_adm else "member"
    display_name = _extract_display_name(first_name, username, telegram_id)

    _upsert_profile(telegram_id, display_name=display_name, role=role)

    token = create_session(
        telegram_id=telegram_id,
        username=username,
        first_name=display_name,
        photo_url=photo_url,
        role=role,
    )

    logger.info("WebApp Auth OK: ID=%s | Role=%s | is_admin=%s", telegram_id, role, is_adm)

    # بازگرداندن ساختار داده تخت و تودرتو هم‌زمان جهت سازگاری کامل فرانت‌اند
    return {
        "token": token,
        "user": user,
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
        "display_name": display_name,
        "role": role,
        "is_admin": is_adm,
        "start_param": payload.get("start_param"),
    }


def verify_login_widget_payload(payload: dict, bot_token: str, max_age_seconds: int = 86400) -> Optional[Dict[str, Any]]:
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

    now = int(time.time())
    if auth_date > now + 300 or (max_age_seconds > 0 and (now - auth_date) > max_age_seconds):
        return None

    return data


def create_session(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    photo_url: Optional[str] = None,
    role: Optional[str] = None,
) -> str:
    telegram_id = int(telegram_id)
    token = secrets.token_hex(32)
    now = _utcnow()
    expires = now + timedelta(days=SESSION_TTL_DAYS)

    if role is None:
        role = "admin" if _is_admin(telegram_id) else "member"

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO sessions (token, telegram_id, username, first_name, photo_url, role, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                token,
                telegram_id,
                username,
                first_name,
                photo_url,
                role,
                now.isoformat(),
                expires.isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return token


def get_session(token: str) -> Optional[Dict[str, Any]]:
    if not token or not isinstance(token, str):
        return None

    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT telegram_id, username, first_name, role, expires_at FROM sessions WHERE token=?",
            (token.strip(),),
        )
        row = c.fetchone()
    finally:
        conn.close()

    if not row:
        return None

    telegram_id, username, first_name, role, expires_at_raw = row
    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None

    if _utcnow() > expires_at:
        return None

    actual_role = "admin" if _is_admin(telegram_id) else role
    prof = get_profile(telegram_id)

    return {
        "telegram_id": int(telegram_id),
        "username": username,
        "first_name": first_name,
        "display_name": prof.get("display_name") or first_name or username or f"User_{telegram_id}",
        "role": actual_role,
        "is_admin": actual_role == "admin",
    }


def get_profile(telegram_id: int) -> Dict[str, Optional[str]]:
    telegram_id = int(telegram_id)
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT display_name, role FROM user_profiles WHERE telegram_id=?", (telegram_id,))
        row = c.fetchone()
    finally:
        conn.close()

    actual_role = "admin" if _is_admin(telegram_id) else "member"
    if not row:
        return {"display_name": None, "role": actual_role}
    return {"display_name": row[0], "role": actual_role}


def _upsert_profile(telegram_id: int, display_name: Optional[str] = None, role: Optional[str] = None):
    telegram_id = int(telegram_id)
    current = get_profile(telegram_id)
    new_name = current["display_name"] if display_name is None else display_name
    new_role = "admin" if _is_admin(telegram_id) else (role or current["role"] or "member")

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO user_profiles (telegram_id, display_name, role, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET "
            "display_name=excluded.display_name, "
            "role=excluded.role, "
            "updated_at=excluded.updated_at",
            (telegram_id, new_name, new_role, _utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def set_display_name(telegram_id: int, display_name: str) -> Optional[str]:
    prof = get_profile(telegram_id)
    return prof.get("display_name")


def verify_pin(*args, **kwargs) -> bool:
    return False


def claim_role(*args, **kwargs) -> bool:
    return False


def bootstrap_pins_from_env():
    pass