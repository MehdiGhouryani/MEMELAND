"""
لایه دسترسی به جدول users.
این ماژول فقط query خام می‌زنه — هیچ منطق کسب‌وکاری (محاسبه سطح، استریک و...)
اینجا نیست؛ اون‌ها در services/scoring.py هستن.
"""
from datetime import datetime

from signal_bot.db.connection import get_db


def register_user(user_id, username, full_name):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at)
                 VALUES (?, ?, ?, ?)""",
              (user_id, username or "", full_name or "", datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_total_pts(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT total_pts FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def get_full_name(user_id):
    """فقط full_name — برای جایی که فقط اسم لازمه، نه کل ردیف (مثل approve_
    که باید اسم مالک سیگنال رو موقع سینک به سایت پاس بده)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT full_name FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def is_blocked(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_blocked FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0])


def set_blocked(user_id, blocked: bool):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_blocked=? WHERE user_id=?", (1 if blocked else 0, user_id))
    conn.commit()
    conn.close()


def set_level(user_id, level_name: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET level=? WHERE user_id=?", (level_name, user_id))
    conn.commit()
    conn.close()


def get_streak_info(user_id):
    """برمی‌گردونه (streak, max_streak, total_pts) یا None اگه کاربر نباشه."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT streak, max_streak, total_pts FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row


def set_streak(user_id, streak, max_streak):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET streak=?, max_streak=? WHERE user_id=?",
              (streak, max_streak, user_id))
    conn.commit()
    conn.close()


def add_points(user_id, delta):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET total_pts=total_pts+? WHERE user_id=?", (delta, user_id))
    conn.commit()
    conn.close()


def get_rank(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT rank FROM (
        SELECT user_id, RANK() OVER (ORDER BY total_pts DESC) as rank
        FROM users) WHERE user_id=?""", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_profile_fields(user_id):
    """برمی‌گردونه (full_name, total_pts, streak, max_streak, level) یا None."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT full_name, total_pts, streak, max_streak, level FROM users WHERE user_id=?",
              (user_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_role(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else "rookie"


def set_role(user_id, role_key: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET role=? WHERE user_id=?", (role_key, user_id))
    conn.commit()
    conn.close()


def find_by_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, username, total_pts, is_blocked, role FROM users WHERE user_id=?",
              (user_id,))
    row = c.fetchone()
    conn.close()
    return row


def find_by_username(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, username, total_pts, is_blocked, role FROM users WHERE username=?",
              (username,))
    row = c.fetchone()
    conn.close()
    return row


def list_unblocked_user_ids():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_blocked=0")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


def count_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    n = c.fetchone()[0]
    conn.close()
    return n


def count_new_users_since(since_iso):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (since_iso,))
    n = c.fetchone()[0]
    conn.close()
    return n
