"""لایه دسترسی به جدول staff — رول‌های مدیریتی غیر از Admin اصلی (که از .env میاد)."""
from datetime import datetime

from signal_bot.db.connection import get_db


def is_vip_helper(user_id) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM staff WHERE user_id=? AND role='vip_helper'", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row)


def add_vip_helper(user_id, added_by=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO staff (user_id, role, added_by, added_at)
                 VALUES (?, 'vip_helper', ?, ?)""", (user_id, added_by, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def remove_vip_helper(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM staff WHERE user_id=? AND role='vip_helper'", (user_id,))
    conn.commit()
    conn.close()


def list_vip_helpers():
    """برمی‌گردونه rows: (user_id, full_name, username)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT s.user_id, u.full_name, u.username
                 FROM staff s LEFT JOIN users u ON s.user_id = u.user_id
                 WHERE s.role='vip_helper'""")
    rows = c.fetchall()
    conn.close()
    return rows
