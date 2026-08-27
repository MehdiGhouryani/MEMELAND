"""لایه دسترسی به جدول signals — همه query های خام مربوط به سیگنال‌ها."""
from datetime import datetime

from signal_bot.db.connection import get_db


def daily_signal_count(user_id):
    conn = get_db()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("""SELECT COUNT(*) FROM signals
                 WHERE user_id=? AND created_at LIKE ? AND status != 'rejected'""",
              (user_id, f"{today}%"))
    count = c.fetchone()[0]
    conn.close()
    return count


def insert_signal(user_id, coin, signal_type="full", direction=None, entry=None, sl=None, tp=None,
                   description="", photo_file_id="", channel="alt"):
    """
    ثبت سیگنال جدید. فقط user_id و coin لازمن — بقیه اختیاری هستن چون Full
    Signal (عکس) و Fast Call (بدون Entry/TP) نیازی به مقادیر عددی کامل ندارن
    (بند ۴ نیازمندی‌ها).
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO signals
        (user_id,coin,direction,entry,stop_loss,take_profit,
         description,signal_type,photo_file_id,channel,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,'pending',?)""",
        (user_id, coin, direction, entry, sl, tp,
         description, signal_type, photo_file_id, channel,
         datetime.now().isoformat()))
    signal_id = c.lastrowid
    conn.commit()
    conn.close()
    return signal_id


def get_public_feed(limit=10):
    """
    سیگنال‌های فعال (تأییدشده و هنوز باز) برای فید عمومی قابل‌مشاهده توسط همه —
    شامل رول ثبت‌کننده (بند ۶ نیازمندی‌ها). Alpha Score در فاز ۴ به این اضافه می‌شه.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT s.id, s.user_id, u.full_name, u.username, u.role,
               s.coin, s.direction, s.entry, s.stop_loss, s.take_profit,
               s.signal_type, s.photo_file_id, s.description, s.created_at
        FROM signals s JOIN users u ON s.user_id=u.user_id
        WHERE s.status='approved' AND s.result='open'
        ORDER BY s.created_at DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_pending_signals(limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT s.id, u.full_name, u.username, s.coin, s.direction,
               s.entry, s.stop_loss, s.take_profit, s.description, s.created_at,
               s.signal_type, s.photo_file_id
        FROM signals s JOIN users u ON s.user_id=u.user_id
        WHERE s.status='pending' ORDER BY s.created_at DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_signal_owner(signal_id):
    """برمی‌گردونه (user_id, coin, direction, photo_file_id, signal_type, description, channel) یا None.
    ⚠️ channel هم مثل description تازه اضافه شد، به همون دلیل: approve_ باید
    مقدار واقعی کانال رو به push_signal_created بده، نه پیش‌فرض هاردکد.
    صدا زننده‌ها: approve_ (بر اساس موقعیت unpack می‌کنه، آپدیت شد) و reject_
    (فقط row[0] رو می‌خونه، بی‌اثر از این تغییر)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, coin, direction, photo_file_id, signal_type, description, channel FROM signals WHERE id=?", (signal_id,))
    row = c.fetchone()
    conn.close()
    return row


def set_signal_status(signal_id, status, reviewed_by=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE signals SET status=?, reviewed_by=? WHERE id=?", (status, reviewed_by, signal_id))
    conn.commit()
    conn.close()


def get_open_approved_signals(limit=15):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT s.id, u.full_name, s.coin, s.direction, s.entry, s.signal_type
                 FROM signals s JOIN users u ON s.user_id=u.user_id
                 WHERE s.status='approved' AND s.result='open'
                 ORDER BY s.created_at DESC LIMIT ?""", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows


def set_signal_result(signal_id, result, points, result_set_by=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE signals SET result=?, points=?, closed_at=?, result_set_by=? WHERE id=?",
              (result, points, datetime.now().isoformat(), result_set_by, signal_id))
    conn.commit()
    conn.close()


def get_signal_for_result(signal_id):
    """
    برای موتور مشترک ثبت/آپدیت نتیجه (services/results.py) — هم مسیر خودگزارش‌دهی
    توسط ثبت‌کننده، هم مسیر اصلاح دستی ادمین از همین تابع استفاده می‌کنن.
    برمی‌گردونه (user_id, coin, direction, status, result, points) یا None.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT user_id, coin, direction, status, result, points
                 FROM signals WHERE id=?""", (signal_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_self_reportable_signals(user_id, limit=15):
    """
    سیگنال‌های تأییدشده‌ی خودِ کاربر (چه هنوز باز، چه قبلاً یه نتیجه براشون ثبت
    شده) — برای خودگزارش‌دهی/آپدیت نتیجه توسط ثبت‌کننده. عمداً هم open و هم
    نتیجه‌دارها رو برمی‌گردونه، چون طبق خواسته‌ی کارفرما باید بشه نتیجه رو بعداً
    که سود بیشتر شد (مثلاً ۲ایکس → ۱۰ایکس) دوباره آپدیت کرد.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, coin, direction, signal_type, result, points, created_at
                 FROM signals WHERE user_id=? AND status='approved'
                 ORDER BY created_at DESC LIMIT ?""", (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows


def get_result_counts(user_id, status="approved"):
    """برمی‌گردونه dict از {result: count} — معادل GROUP BY کوئری اصلی."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT result, COUNT(*) FROM signals
                 WHERE user_id=? AND status=? GROUP BY result""", (user_id, status))
    result = dict(c.fetchall())
    conn.close()
    return result


def count_user_signals(user_id, status):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM signals WHERE user_id=? AND status=?", (user_id, status))
    n = c.fetchone()[0]
    conn.close()
    return n


def get_user_signals(user_id, filter_status="approved", limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, coin, direction, entry, stop_loss, take_profit,
                        result, points, created_at, status, signal_type
                 FROM signals WHERE user_id=? AND status=?
                 ORDER BY created_at DESC LIMIT ?""",
              (user_id, filter_status, limit))
    rows = c.fetchall()
    conn.close()
    return rows


def get_leaderboard_rows(since_iso, limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT s.user_id, u.full_name, u.username, u.level, SUM(s.points) as pts,
               COUNT(s.id) as cnt,
               SUM(CASE WHEN s.result != 'loss' AND s.result != 'open' THEN 1 ELSE 0 END) as wins
        FROM signals s JOIN users u ON s.user_id = u.user_id
        WHERE s.status='approved' AND s.created_at >= ?
        GROUP BY s.user_id ORDER BY pts DESC LIMIT ?
    """, (since_iso, limit))
    rows = c.fetchall()
    conn.close()
    return rows


def get_hall_of_fame_top(limit=5):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT u.user_id, u.full_name, u.username, u.level, u.total_pts,
               u.max_streak, COUNT(s.id) as cnt
        FROM users u LEFT JOIN signals s ON u.user_id=s.user_id AND s.status='approved'
        GROUP BY u.user_id ORDER BY u.total_pts DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows


def count_total_signals():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM signals")
    n = c.fetchone()[0]
    conn.close()
    return n


def count_pending_signals():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM signals WHERE status='pending'")
    n = c.fetchone()[0]
    conn.close()
    return n


def count_win_signals():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM signals WHERE status='approved' AND result!='open' AND result!='loss'")
    n = c.fetchone()[0]
    conn.close()
    return n


def count_loss_signals():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM signals WHERE result='loss'")
    n = c.fetchone()[0]
    conn.close()
    return n


def get_top3_by_points():
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT u.user_id, u.full_name, SUM(s.points) as pts
                 FROM signals s JOIN users u ON s.user_id=u.user_id
                 WHERE s.status='approved'
                 GROUP BY s.user_id ORDER BY pts DESC LIMIT 3""")
    rows = c.fetchall()
    conn.close()
    return rows


def get_rank_changes_since(since_iso):
    """برای جاب notify_rank_changes — فعلاً فقط داده رو می‌خونه (منطق اطلاع‌رسانی هنوز پیاده نشده)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT u.user_id, u.full_name, SUM(s.points) as pts,
                        RANK() OVER (ORDER BY SUM(s.points) DESC) as rnk
                 FROM signals s JOIN users u ON s.user_id=u.user_id
                 WHERE s.status='approved' AND s.created_at >= ?
                 GROUP BY s.user_id""", (since_iso,))
    rows = c.fetchall()
    conn.close()
    return rows


def export_rows():
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT u.full_name, u.username, u.total_pts, u.level, u.streak,
                        COUNT(s.id) as cnt
                 FROM users u LEFT JOIN signals s ON u.user_id=s.user_id AND s.status='approved'
                 GROUP BY u.user_id ORDER BY u.total_pts DESC""")
    rows = c.fetchall()
    conn.close()
    return rows
