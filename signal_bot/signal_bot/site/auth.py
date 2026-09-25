"""
ماژول احراز هویت، مدیریت نشست‌ها و دسترسی‌های وب‌سرور Memeland
"""

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from signal_bot.config import settings
from signal_bot.logger import logger
from signal_bot.services.webapp_auth import verify_webapp_data
from signal_bot.site.db import get_db

SESSION_TTL_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_admin_ids() -> List[int]:
    """برگرداندن لیست تمام مدیران از جدول staff و تنظیمات برای استفاده در روت‌ها"""
    admin_ids = [int(x) for x in getattr(settings, "ADMIN_IDS", [])]
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'")
        if c.fetchone():
            c.execute("SELECT user_id FROM staff WHERE role IN ('admin', 'vip_helper')")
            db_admins = [r[0] for r in c.fetchall()]
            admin_ids.extend(db_admins)
    except Exception as e:
        logger.warning(f"GetAdminIdsErr: {e}")
    finally:
        conn.close()
    return list(set(admin_ids))


def _is_super_admin(telegram_id: Any) -> bool:
    if telegram_id is None:
        return False
    try:
        tid = int(telegram_id)
        admin_ids = [int(x) for x in getattr(settings, "ADMIN_IDS", [])]
        return tid in admin_ids
    except (ValueError, TypeError):
        return False


def _is_staff_admin(telegram_id: int) -> bool:
    """
    🚨 فیکس واگرایی دو دیتابیس:
      بات، کادر مدیریتی رو توی جدول `staff` دیتابیس *خودش* (signals.db، از
      طریق db/staff_repo.py) می‌نویسه. ولی این تابع فقط جدول `staff`
      دیتابیس *سایت* (site.db) رو می‌خوند. نتیجه: هر VIP Helper ای که از
      داخل ربات اضافه می‌شد، توی وب‌اپ اصلاً ادمین شناخته نمی‌شد — و
      برعکس. فقط ADMIN_IDS (از .env) اتفاقی توی هر دو کار می‌کرد، چون از
      فایل محیطی میاد نه از دیتابیس.
      الان هر دو دیتابیس چک می‌شن.
    """
    if _staff_row_in_site_db(telegram_id):
        return True
    return _staff_row_in_bot_db(telegram_id)


def _staff_row_in_site_db(telegram_id: int) -> bool:
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'")
        if not c.fetchone():
            return False
        c.execute("SELECT role FROM staff WHERE user_id=? AND role IN ('admin', 'vip_helper')", (telegram_id,))
        return c.fetchone() is not None
    except Exception as e:
        logger.warning(f"StaffChkErr: db=site uid={telegram_id} err={e}")
        return False
    finally:
        conn.close()


def _staff_row_in_bot_db(telegram_id: int) -> bool:
    try:
        from signal_bot.db.connection import get_db as get_bot_db
    except Exception:
        return False
    conn = get_bot_db()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'")
        if not c.fetchone():
            return False
        c.execute("SELECT role FROM staff WHERE user_id=? AND role IN ('admin', 'vip_helper')", (telegram_id,))
        return c.fetchone() is not None
    except Exception as e:
        logger.warning(f"StaffChkErr: db=bot uid={telegram_id} err={e}")
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _bot_user_role(telegram_id: int):
    """
    🚨 فیکس: `get_user_role_and_quota` جدول `users` رو توی site.db جست‌وجو
    می‌کرد — جدولی که اصلاً اون‌جا وجود نداره (فقط توی signals.db هست).
    چون کد قبل از کوئری با sqlite_master وجود جدول رو چک می‌کرد، هیچ خطایی
    نمی‌داد و *بی‌صدا* همیشه رول پیش‌فرض ('rookie') برمی‌گردوند. یعنی سقف
    سهمیه‌ی روزانه‌ی همه‌ی کاربرها روی ۳ گیر کرده بود، صرف‌نظر از رول
    واقعی‌شون توی ربات. (traders.py همین باگ رو قبلاً برای username فیکس
    کرده بود، ولی اینجا جا مونده بود.)
    """
    try:
        from signal_bot.db.connection import get_db as get_bot_db
    except Exception:
        return None
    conn = get_bot_db()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not c.fetchone():
            return None
        c.execute("SELECT role FROM users WHERE user_id=?", (telegram_id,))
        row = c.fetchone()
        return row[0] if row and row[0] else None
    except Exception as e:
        logger.warning(f"BotRoleErr: uid={telegram_id} err={e}")
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _is_admin(telegram_id: Any) -> bool:
    if telegram_id is None:
        return False
    try:
        tid = int(telegram_id)
        return _is_super_admin(tid) or _is_staff_admin(tid)
    except (ValueError, TypeError):
        return False


def get_user_role_and_quota(telegram_id: int, elevate: bool = True) -> Dict[str, Any]:
    """
    elevate=False ⇒ هیچ ارتقای ادمینی اعمال نمی‌شه، حتی اگه کاربر واقعاً
    ادمین باشه. این برای «سشن تأییدنشده» لازمه (کاربری که فقط آیدی خام
    تلگرام رو فرستاده و هویتش رمزنگاری‌شده اثبات نشده).

    🚨 چرا این پارامتر حیاتیه: routes.py توی مسیر تأییدنشده، is_admin سطح
    بالا رو False می‌کرد ولی همین دیکشنری quota رو دست‌نخورده برمی‌گردوند —
    و داخلش is_admin/is_super_admin واقعی بود. کلاینت (app.js →
    updateUserInterface) دقیقاً `quota?.is_admin === true` رو هم چک می‌کنه،
    پس کل پنل ادمین برای یه هویت اثبات‌نشده باز می‌شد.
    """
    telegram_id = int(telegram_id)
    role_key = _bot_user_role(telegram_id) or getattr(settings, "DEFAULT_ROLE", "rookie")

    conn = get_db()
    try:
        c = conn.cursor()
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
        logger.warning(f"QuotaErr: uid={telegram_id} err={e}")
        signals_count = 0
    finally:
        conn.close()

    daily_limits = getattr(settings, "ROLE_DAILY_LIMITS", {})
    daily_limit = daily_limits.get(role_key, getattr(settings, "DAILY_LIMIT", 5))
    role_labels = getattr(settings, "ROLE_LABELS", {})
    role_label = role_labels.get(role_key, role_key)

    is_super = bool(elevate) and _is_super_admin(telegram_id)
    is_adm = bool(elevate) and _is_admin(telegram_id)
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


# نقش‌هایی که «کادر» محسوب می‌شن (دسترسی مدیریتی) در برابر نقش‌های
# «تریدر ویژه» (فقط سقف سهمیه‌ی بالاتر). وب‌اپ هر دو دسته رو تو همون مودال
# نشون می‌ده، با تب‌های جدا.
_STAFF_ROLES = ("admin", "vip_helper")
_TRADER_ROLES = ("og", "alpha", "guardian", "explorer")


def _resolve_identity(telegram_id: int):
    """
    نام نمایشی و یوزرنیم یه کاربر، از بهترین منبع موجود.

    🚨 چرا لازم شد: get_staff_list قبلاً فقط به جدول sessions دیتابیس *سایت*
    جوین می‌زد. یعنی اسم فقط برای کسی پیدا می‌شد که حداقل یک‌بار وب‌اپ رو باز
    کرده بود. برای ادمینی که فقط از داخل ربات کار می‌کنه، همیشه «کاربر
    123456» نشون داده می‌شد. ترتیب منابع: جدول users ربات (معتبرترین، چون
    تلگرام خودش پرش می‌کنه) ← user_profiles سایت ← sessions سایت.
    """
    name = username = None
    try:
        from signal_bot.db import users_repo
        row = users_repo.find_by_id(telegram_id)
        if row:
            _, full_name, uname, _, _, _ = row
            name, username = full_name or None, uname or None
    except Exception as e:
        logger.warning(f"IdentityBotErr: uid={telegram_id} err={e}")

    if name and username:
        return name, username

    conn = get_db()
    try:
        c = conn.cursor()
        if not name:
            c.execute("SELECT display_name FROM user_profiles WHERE telegram_id=?", (telegram_id,))
            r = c.fetchone()
            if r and r[0]:
                name = r[0]
        if not name or not username:
            c.execute(
                "SELECT first_name, username FROM sessions WHERE telegram_id=? "
                "ORDER BY created_at DESC LIMIT 1", (telegram_id,)
            )
            r = c.fetchone()
            if r:
                name = name or r[0]
                username = username or r[1]
    except Exception as e:
        logger.warning(f"IdentitySiteErr: uid={telegram_id} err={e}")
    finally:
        conn.close()

    return name, username


def _staff_rows_from(conn_factory, label):
    out = {}
    try:
        conn = conn_factory()
    except Exception:
        return out
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'")
        if not c.fetchone():
            return out
        c.execute("SELECT user_id, role, added_at FROM staff")
        for uid, role, added_at in c.fetchall():
            out[int(uid)] = {"role": role or "vip_helper", "added_at": added_at, "src": label}
    except Exception as e:
        logger.warning(f"StaffListErr: db={label} err={e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return out


def _trader_rows_from_bot():
    """کاربرانی که تو ربات نقش تریدرِ ارتقایافته گرفتن (users.role)."""
    out = {}
    try:
        from signal_bot.db.connection import get_db as get_bot_db
    except Exception:
        return out
    conn = get_bot_db()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not c.fetchone():
            return out
        placeholders = ",".join("?" * len(_TRADER_ROLES))
        c.execute(f"SELECT user_id, role FROM users WHERE role IN ({placeholders})", _TRADER_ROLES)
        for uid, role in c.fetchall():
            out[int(uid)] = {"role": role, "added_at": None, "src": "bot_users"}
    except Exception as e:
        logger.warning(f"TraderListErr: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return out


def get_staff_list() -> List[Dict[str, Any]]:
    """
    فهرست یکپارچه‌ی کادر و نقش‌های فعال.

    🚨 چرا این بخش تو وب‌اپ کاملاً خالی بود — سه دلیل هم‌زمان:
      ۱. سوپرادمین‌ها (ADMIN_IDS از .env) توی *هیچ* جدولی ردیف ندارن، پس
         هیچ‌وقت لیست نمی‌شدن. برای پروژه‌ای که تنها ادمینش از .env میاد،
         یعنی لیست همیشه خالی.
      ۲. کادری که از داخل ربات اضافه می‌شد (staff_repo → signals.db) خونده
         نمی‌شد؛ فقط جدول staff دیتابیس سایت.
      ۳. نقش‌های تریدر (og/alpha/guardian/explorer) اصلاً تو جدول staff
         نیستن — تو ستون users.role دیتابیس *ربات*‌ان. پس تب «تریدرهای
         ویژه» ذاتاً نمی‌تونست چیزی نشون بده.
    الان هر چهار منبع با هم ادغام می‌شن.
    """
    from signal_bot.config import settings

    merged: Dict[int, Dict[str, Any]] = {}

    # کم‌اولویت‌ترین اول، تا منابع مهم‌تر روش بنویسن.
    merged.update(_trader_rows_from_bot())
    try:
        from signal_bot.db.connection import get_db as get_bot_db
        merged.update(_staff_rows_from(get_bot_db, "bot"))
    except Exception:
        pass
    merged.update(_staff_rows_from(get_db, "site"))

    # سوپرادمین‌ها همیشه، و همیشه با بالاترین اولویت.
    for raw in getattr(settings, "ADMIN_IDS", []):
        try:
            merged[int(raw)] = {"role": "admin", "added_at": None, "src": "env"}
        except (TypeError, ValueError):
            continue

    rows = []
    for uid, info in merged.items():
        name, username = _resolve_identity(uid)
        rows.append({
            "user_id": uid,
            "role": info["role"],
            "added_at": info["added_at"],
            "is_super": _is_super_admin(uid),
            "source": info["src"],
            "first_name": name or f"کاربر {uid}",
            "username": f"@{username}" if username else f"ID: {uid}",
        })

    # سوپرادمین‌ها اول، بعد ادمین‌ها، بعد دستیارها، بعد تریدرها.
    order = {"admin": 0, "vip_helper": 1, "og": 2, "alpha": 3, "guardian": 4, "explorer": 5}
    rows.sort(key=lambda r: (not r["is_super"], order.get(r["role"], 9), r["user_id"]))
    logger.info(f"StaffList: total={len(rows)} " + " ".join(
        f"{k}={sum(1 for r in rows if r['role'] == k)}" for k in ("admin", "vip_helper") ) +
        f" traders={sum(1 for r in rows if r['role'] in _TRADER_ROLES)}")
    return rows


def _write_bot_user_role(user_id: int, role: str) -> bool:
    """نوشتن users.role در دیتابیس *ربات* (تنها جایی که واقعاً خونده می‌شه)."""
    try:
        from signal_bot.db.connection import get_db as get_bot_db
    except Exception:
        return False
    conn = get_bot_db()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not c.fetchone():
            return False
        c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        if c.fetchone():
            c.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
        else:
            # کاربری که هنوز با ربات تعامل نکرده. ردیف حداقلی می‌سازیم تا
            # نقشش گم نشه و بعداً که /start بزنه، INSERT OR IGNORE بی‌خطر رد شه.
            c.execute(
                "INSERT INTO users (user_id, username, full_name, joined_at, role) VALUES (?,?,?,?,?)",
                (user_id, "", f"User_{user_id}", _utcnow().isoformat(), role),
            )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"BotRoleWriteErr: uid={user_id} role={role} err={e}")
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _write_staff_row(conn_factory, user_id: int, role: str) -> bool:
    try:
        conn = conn_factory()
    except Exception:
        return False
    try:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS staff (
            user_id INTEGER PRIMARY KEY, role TEXT NOT NULL, added_at TEXT NOT NULL)""")
        c.execute("""INSERT INTO staff (user_id, role, added_at) VALUES (?, ?, ?)
                     ON CONFLICT(user_id) DO UPDATE SET role=excluded.role""",
                  (user_id, role, _utcnow().isoformat()))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"StaffWriteErr: uid={user_id} err={e}")
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _delete_staff_row(conn_factory, user_id: int) -> int:
    try:
        conn = conn_factory()
    except Exception:
        return 0
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'")
        if not c.fetchone():
            return 0
        c.execute("DELETE FROM staff WHERE user_id=?", (user_id,))
        conn.commit()
        return c.rowcount
    except Exception as e:
        logger.warning(f"StaffDelErr: uid={user_id} err={e}")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def sync_staff_row_from_bot(user_id: int, role: str) -> bool:
    """
    وقتی نقش کادر از داخل *چت* (staff_repo.add_vip_helper، دکمه‌ی
    vip_add_) عوض می‌شه، این جدول staff دیتابیس *سایت* رو هم هماهنگ
    می‌کنه — تا هر دو مسیر (چت و وب‌اپ) همیشه یک نتیجه رو ببینن.

    🚨 بدون این، یه ناسازگاریِ هم‌خانواده با باگ دور دوم باقی می‌موند:
    add_or_update_staff (سمت وب‌اپ) از ابتدا هر دو دیتابیس رو می‌نوشت، ولی
    دکمه‌ی vip_add_/vip_remove_ داخل چت (که قدیمی‌تره) فقط دیتابیس ربات رو
    می‌نوشت. اثر عملی: کسی که با دکمه‌ی چت VIP Helper می‌شد، تو وب‌اپ درست
    دیده می‌شد (چون get_staff_list هر دو دیتابیس رو می‌خونه)، ولی اگه بعداً
    از همون دکمه‌ی چت *حذف* می‌شد، ردیفِ دیتابیس سایت دست‌نخورده می‌موند —
    یعنی توی سایت (و هر جایی که فقط site.db رو چک می‌کرد) همچنان دسترسی
    داشت، درحالی‌که تو چت دیگه نداشت.
    """
    return _write_staff_row(get_db, int(user_id), role)


def unsync_staff_row_from_bot(user_id: int) -> int:
    """نصف مکملِ sync_staff_row_from_bot — برای دکمه‌ی vip_remove_."""
    return _delete_staff_row(get_db, int(user_id))


def add_or_update_staff(user_id: int, role: str) -> bool:
    """
    اعطای نقش — با مسیردهی به دیتابیس درست بر اساس نوع نقش.

    🚨 باگ قبلی: این تابع همیشه هم توی staff دیتابیس *سایت* می‌نوشت، هم
    `UPDATE users SET role=?` روی همون دیتابیس می‌زد. ولی جدول users فقط
    توی دیتابیس *ربات* وجود داره، پس اون UPDATE بی‌صدا هیچ کاری نمی‌کرد و
    نقش‌های تریدر (og/alpha/guardian/explorer) عملاً هرگز ذخیره نمی‌شدن.
    به‌علاوه چون فقط دیتابیس سایت نوشته می‌شد، خودِ ربات هیچ‌وقت از ادمین
    جدید خبردار نمی‌شد.
    الان:
      • نقش کادری (admin / vip_helper) → جدول staff هر دو دیتابیس
      • نقش تریدر                        → users.role دیتابیس ربات، و ردیف
                                           staff حذف می‌شه (تنزل درجه)
    """
    user_id = int(user_id)
    role = str(role or "").strip()

    if role in _STAFF_ROLES:
        ok_site = _write_staff_row(get_db, user_id, role)
        ok_bot = False
        try:
            from signal_bot.db.connection import get_db as get_bot_db
            ok_bot = _write_staff_row(get_bot_db, user_id, role)
        except Exception:
            pass
        _upsert_profile(user_id, role=role)
        logger.info(f"StaffSet: uid={user_id} role={role} site={ok_site} bot={ok_bot}")
        return ok_site or ok_bot

    if role in _TRADER_ROLES or role in [k for k, _ in getattr(settings, "ROLES", [])]:
        # تنزل از کادر به تریدر: ردیف staff باید برداشته بشه، وگرنه کاربر
        # همچنان ادمین می‌مونه در حالی که UI نقش تریدر نشون می‌ده.
        _delete_staff_row(get_db, user_id)
        try:
            from signal_bot.db.connection import get_db as get_bot_db
            _delete_staff_row(get_bot_db, user_id)
        except Exception:
            pass
        ok = _write_bot_user_role(user_id, role)
        _upsert_profile(user_id, role=role)
        logger.info(f"RoleSet: uid={user_id} role={role} botUsers={ok}")
        return ok

    logger.warning(f"StaffSetReject: uid={user_id} role={role!r} نقش ناشناخته")
    return False


def remove_staff(user_id: int) -> bool:
    """
    سلب دسترسی. سوپرادمین‌های .env قابل حذف نیستن (ردیف دیتابیسی ندارن که
    حذف بشه — تنها راه، ویرایش فایل .env و ری‌استارته).
    """
    user_id = int(user_id)
    if _is_super_admin(user_id):
        logger.info(f"StaffDelReject: uid={user_id} سوپرادمین .env است")
        return False

    removed = _delete_staff_row(get_db, user_id)
    try:
        from signal_bot.db.connection import get_db as get_bot_db
        removed += _delete_staff_row(get_bot_db, user_id)
    except Exception:
        pass

    default_role = getattr(settings, "DEFAULT_ROLE", "rookie")
    reset = _write_bot_user_role(user_id, default_role)
    logger.info(f"StaffDel: uid={user_id} rows={removed} roleReset={reset}")
    return removed > 0 or reset


def _extract_display_name(first_name: Optional[str], username: Optional[str], telegram_id: int) -> str:
    if first_name and first_name.strip():
        return first_name.strip()[:64]
    if username and username.strip():
        return f"@{username.strip()[:63]}"
    return f"User_{telegram_id}"


def authenticate_webapp(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> Optional[Dict[str, Any]]:
    payload = verify_webapp_data(init_data, bot_token, max_age_seconds=max_age_seconds)
    if not payload or not payload.get("user"):
        logger.warning("AuthFail: TMA init_data invalid")
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

    # ⚠️ اگه سشن زنده‌ای هست، همون رو استفاده کن. قبلاً هر بار باز کردن
    # وب‌اپ یه ردیف جدید می‌ساخت که هیچ‌وقت پاک نمی‌شد.
    token = find_active_token(telegram_id) or create_session(
        telegram_id=telegram_id,
        username=username,
        first_name=display_name,
        photo_url=photo_url,
        role=role,
    )

    logger.info(f"AuthOK: uid={telegram_id} adm={quota_info['is_admin']} super={quota_info['is_super_admin']} role={quota_info['role_key']}")

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


def find_active_token(telegram_id: int) -> Optional[str]:
    """
    آخرین توکن معتبر و منقضی‌نشده‌ی این کاربر رو برمی‌گردونه (یا None).

    🚨 باگی که حل می‌کنه: `_resolve_user_session` توی routes.py برای *هر
    درخواستی* یه ردیف جدید توی جدول sessions می‌ساخت. هر بار لود صفحه
    حداقل ۲ درخواست می‌زنه (auth + signals) و pull-refresh هم همین‌طور.
    یعنی جدول sessions بی‌نهایت رشد می‌کرد، با هزاران توکن زنده به ازای یه
    کاربر — هم نشت منابع، هم افزایش سطح حمله (هر توکن ۳۰ روز اعتبار داره).
    """
    telegram_id = int(telegram_id)
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT token, expires_at FROM sessions WHERE telegram_id=? "
            "ORDER BY created_at DESC LIMIT 1",
            (telegram_id,),
        )
        row = c.fetchone()
    except Exception as e:
        logger.warning(f"FindTokenErr: uid={telegram_id} err={e}")
        return None
    finally:
        conn.close()

    if not row:
        return None
    token, expires_raw = row
    try:
        expires_at = datetime.fromisoformat(expires_raw)
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None
    # کمتر از یک روز مونده؟ توکن تازه بده تا وسط کار منقضی نشه.
    if expires_at - _utcnow() < timedelta(days=1):
        return None
    return token


def purge_expired_sessions() -> int:
    """
    سشن‌های منقضی‌شده رو پاک می‌کنه. قبلاً هیچ‌وقت هیچ‌چی از جدول sessions
    حذف نمی‌شد. از main.py به‌صورت دوره‌ای صدا زده می‌شه.
    """
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (_utcnow().isoformat(),))
        removed = c.rowcount
        conn.commit()
        if removed:
            logger.info(f"SessPurge: removed={removed}")
        return max(0, removed)
    except Exception as e:
        logger.warning(f"SessPurgeErr: {e}")
        return 0
    finally:
        conn.close()


def count_sessions() -> int:
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM sessions")
        return c.fetchone()[0]
    except Exception:
        return -1
    finally:
        conn.close()


def wipe_all_sessions() -> int:
    """باطل‌کردن یک‌جای همه‌ی نشست‌ها — نگاه کن به /wipe_sessions در main.py
    برای دلیل امنیتی. عمداً غیرقابل‌بازگشت و بدون فیلتره."""
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM sessions")
        n = c.rowcount
        conn.commit()
        logger.warning(f"SessWipeAll: removed={n}")
        return max(0, n)
    except Exception as e:
        logger.error(f"SessWipeAllErr: {e}")
        return 0
    finally:
        conn.close()


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
        logger.warning(f"SessNotFound: tok={token[:8]}...")
        return None

    telegram_id, username, first_name, role, expires_at_raw = row
    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None

    if _utcnow() > expires_at:
        logger.warning(f"SessExpired: uid={telegram_id}")
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
    """⚠️ فیکس: قبلاً این تابع پارامتر display_name رو اصلاً استفاده نمی‌کرد و
    فقط نام فعلی رو بدون تغییر برمی‌گردوند — یعنی «تغییر نام نمایشی» عملاً
    هیچ‌وقت ذخیره نمی‌شد. الان واقعاً با همون الگوی _upsert_profile ثبت
    می‌شه. فعلاً تو کد صدا زده نمی‌شه؛ اگه فیچر «ویرایش نام» بعداً به یه
    endpoint وصل بشه، این تابع از الان درست کار می‌کنه."""
    name = (display_name or "").strip()
    if not name:
        return get_profile(telegram_id).get("display_name")
    name = name[:64]
    _upsert_profile(telegram_id, display_name=name)
    return name


def verify_pin(*args, **kwargs) -> bool:
    return False


def claim_role(*args, **kwargs) -> bool:
    return False


def bootstrap_pins_from_env():
    pass