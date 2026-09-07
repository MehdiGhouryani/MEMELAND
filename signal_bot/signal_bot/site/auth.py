"""
ماژول احراز هویت، مدیریت نشست‌ها و دسترسی‌های وب‌سرور Memeland
"""

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from signal_bot.config import settings
from signal_bot.services.webapp_auth import verify_webapp_data
from signal_bot.site.db import get_db

logger = logging.getLogger(__name__)

SESSION_TTL_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_super_admin(telegram_id: Any) -> bool:
    """بررسی عضویت قطعی شناسه در ADMIN_IDS فایل .env"""
    if telegram_id is None:
        return False
    try:
        tid = int(telegram_id)
        admin_ids = [int(x) for x in getattr(settings, "ADMIN_IDS", [])]
        return tid in admin_ids
    except (ValueError, TypeError):
        return False


def _is_staff_admin(telegram_id: int) -> bool:
    """بررسی ادمین یا هلپر بودن در جدول staff دیتابیس ربات"""
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'")
        if not c.fetchone():
            return False
        c.execute("SELECT role FROM staff WHERE user_id=? AND role IN ('admin', 'vip_helper')", (telegram_id,))
        return c.fetchone() is not None
    except Exception as e:
        logger.warning("Staff table query failed: %s", e)
        return False
    finally:
        conn.close()


def _is_admin(telegram_id: Any) -> bool:
    """تشخیص نهایی دسترسی ادمین (Super Admin یا Staff Admin)"""
    if telegram_id is None:
        return False
    try:
        tid = int(telegram_id)
        return _is_super_admin(tid) or _is_staff_admin(tid)
    except (ValueError, TypeError):
        return False


def get_user_role_and_quota(telegram_id: int) -> Dict[str, Any]:
    """استخراج رول ربات، برچسب رول، و سهمیه سیگنال ۲۴ ساعت اخیر"""
    telegram_id = int(telegram_id)
    role_key = getattr(settings, "DEFAULT_ROLE", "rookie")
    
    conn = get_db()
    try:
        c = conn.cursor()
        # استخراج رول از جدول users در صورت وجود
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if c.fetchone():
            c.execute("SELECT role FROM users WHERE user_id=?", (telegram_id,))
            row = c.fetchone()
            if row and row[0]:
                role_key = row[0]

        # شمارش سیگنال‌های ثبت‌شده در ۲۴ ساعت گذشته
        since_24h = (_utcnow() - timedelta(hours=24)).isoformat()
        signals_count = 0
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
        if c.fetchone():
            c.execute(
                "SELECT COUNT(*) FROM signals WHERE owner_telegram_id=? AND created_at >= ?",
                (telegram_id, since_24h)
            )
            signals_count = c.fetchone()[0]
    except Exception as e:
        logger.warning("Failed to fetch user quota: %s", e)
        signals_count = 0
    finally:
        conn.close()

    daily_limits = getattr(settings, "ROLE_DAILY_LIMITS", {})
    daily_limit = daily_limits.get(role_key, getattr(settings, "DAILY_LIMIT", 5))
    role_labels = getattr(settings, "ROLE_LABELS", {})
    role_label = role_labels.get(role_key, role_key)

    is_super = _is_super_admin(telegram_id)
    is_adm = _is_admin(telegram_id)
    if is_super:
        display_role = "👑 Super Admin"
        daily_limit = 999
    elif is_adm:
        display_role = "💎 VIP Admin"
        daily_limit = 999
    else:
        display_role = role_label

    return {
        "role_key": role_key,
        "display_role": display_role,
        "signals_today": signals_count,
        "daily_limit": daily_limit,
        "remaining_signals": max(0, daily_limit - signals_count),
        "is_admin": is_adm,
        "is_super_admin": is_super,
    }


def get_staff_list() -> List[Dict[str, Any]]:
    """لیست اعضای کادر و ادمین‌های دیتابیس"""
    conn = get_db()
    staff_rows = []
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'")
        if c.fetchone():
            c.execute("SELECT user_id, role, added_at FROM staff")
            for r in c.fetchall():
                staff_rows.append({
                    "user_id": r[0],
                    "role": r[1],
                    "added_at": r[2],
                    "is_super": _is_super_admin(r[0])
                })
    finally:
        conn.close()
    return staff_rows


def add_or_update_staff(user_id: int, role: str) -> bool:
    """ثبت یا ویرایش نقش کاربر در دیتابیس ربات"""
    user_id = int(user_id)
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                added_at TEXT NOT NULL
            )
        """)
        c.execute("""
            INSERT INTO staff (user_id, role, added_at) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET role=excluded.role
        """, (user_id, role, _utcnow().isoformat()))

        # اگر نقش در جدول users هم قابل اعمال بود، بروزرسانی شود
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if c.fetchone():
            c.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
        conn.commit()
        return True
    except Exception as e:
        logger.error("Error updating staff: %s", e)
        return False
    finally:
        conn.close()


def remove_staff(user_id: int) -> bool:
    """خلع دسترسی کاربر از کادر ادمین دیتابیس"""
    user_id = int(user_id)
    if _is_super_admin(user_id):
        return False  # سوپرادمین .env حذف نمی‌شود
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM staff WHERE user_id=?", (user_id,))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


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

    quota_info = get_user_role_and_quota(telegram_id)
    role = "admin" if quota_info["is_admin"] else "member"
    display_name = _extract_display_name(first_name, username, telegram_id)

    _upsert_profile(telegram_id, display_name=display_name, role=role)

    token = create_session(
        telegram_id=telegram_id,
        username=username,
        first_name=display_name,
        photo_url=photo_url,
        role=role,
    )

    logger.info(
        "WebApp Auth: ID=%s | Role=%s | is_admin=%s | UserRole=%s",
        telegram_id, role, quota_info["is_admin"], quota_info["display_role"]
    )

    return {
        "token": token,
        "user": user,
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
        "display_name": display_name,
        "role": role,
        "is_admin": quota_info["is_admin"],
        "is_super_admin": quota_info["is_super_admin"],
        "quota": quota_info,
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

    quota_info = get_user_role_and_quota(telegram_id)
    actual_role = "admin" if quota_info["is_admin"] else role
    prof = get_profile(telegram_id)

    return {
        "telegram_id": int(telegram_id),
        "username": username,
        "first_name": first_name,
        "display_name": prof.get("display_name") or first_name or username or f"User_{telegram_id}",
        "role": actual_role,
        "is_admin": quota_info["is_admin"],
        "is_super_admin": quota_info["is_super_admin"],
        "quota": quota_info,
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