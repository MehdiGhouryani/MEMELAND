"""
جایگزین جدول kv_store سوپابیس — مقاله‌ها، استراتژی‌ها، و مقادیر PIN قدیمی
(از site/auth.py) همه از همین رد می‌شن.

⚠️ عمداً بدون چک مجوز اینجا — دقیقاً مثل db/*_repo.py خودِ بات که فقط
CRUD خامه و تصمیم "کی حق داره" رو یه لایه بالاتر (routes) می‌گیره، نه
اینجا. این یعنی این ماژول رو مستقیم از route هندلر صدا نزن مگر این‌که
مجوز رو قبلش (session/role) چک کرده باشی.
"""
from datetime import datetime

from signal_bot.site.db import get_db


def kv_get(key: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM kv_store WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def kv_set(key: str, value: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO kv_store (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def kv_delete(key: str):
    conn = get_db()
    conn.execute("DELETE FROM kv_store WHERE key=?", (key,))
    conn.commit()
    conn.close()


def kv_list(prefix: str = ""):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT key FROM kv_store WHERE key LIKE ?", (prefix + "%",))
    keys = [r[0] for r in c.fetchall()]
    conn.close()
    return keys
