"""لایه دسترسی به جداول prize_pool / prize_seasons / prize_winners / broadcasts."""
from datetime import datetime, timedelta

from signal_bot.db.connection import get_db


def get_active_season():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM prize_seasons WHERE status='active' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row


def count_seasons():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM prize_seasons")
    n = c.fetchone()[0]
    conn.close()
    return n


def create_first_season(name="فصل اول", days=14):
    conn = get_db()
    c = conn.cursor()
    end = (datetime.now() + timedelta(days=days)).isoformat()
    c.execute("INSERT INTO prize_seasons (name,start_date,end_date,status) VALUES (?,?,?,'active')",
              (name, datetime.now().isoformat(), end))
    conn.commit()
    conn.close()


def create_next_season(days=14):
    """
    فصل جدید با نام‌گذاری خودکار می‌سازه («فصل #N»). این تابع رو هم main.py
    (اگه موقع استارت هیچ فصل فعالی نبود) و هم handle_step_endseason_confirm
    (بلافاصله بعد از پایان یک فصل) صدا می‌زنن — تا هیچ‌وقت ربات بدون فصل فعال
    نمونه (باگ قبلی همین بود: بعد از پایان اولین فصل، هیچ فصل جدیدی هیچ‌وقت
    ساخته نمی‌شد، نه خودکار نه با ری‌استارت).
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM prize_seasons")
    n = c.fetchone()[0]
    name = f"فصل #{n + 1}"
    end = (datetime.now() + timedelta(days=days)).isoformat()
    c.execute("INSERT INTO prize_seasons (name,start_date,end_date,status) VALUES (?,?,?,'active')",
              (name, datetime.now().isoformat(), end))
    conn.commit()
    conn.close()
    return name


def end_season(season_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE prize_seasons SET status='ended' WHERE id=?", (season_id,))
    conn.commit()
    conn.close()


def get_prize_pool_sum(status):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM prize_pool WHERE status=?", (status,))
    total = c.fetchone()[0] or 0
    conn.close()
    return total


def get_prize_pool_total():
    return get_prize_pool_sum("paid")


def insert_donation(user_id, amount, order_id, invoice_id, invoice_url):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO prize_pool (user_id,amount,currency,order_id,invoice_id,invoice_url,status,added_at)
                 VALUES (?,?,'USDT',?,?,?,'pending',?)""",
              (user_id, amount, order_id, invoice_id, invoice_url, datetime.now().isoformat()))
    donate_id = c.lastrowid
    conn.commit()
    conn.close()
    return donate_id


def get_donation_by_order_id(order_id):
    """برای وب‌هوک — پیدا کردن رکورد از روی order_id. برمی‌گردونه (id, user_id, status) یا None."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, user_id, status FROM prize_pool WHERE order_id=?", (order_id,))
    row = c.fetchone()
    conn.close()
    return row


def set_payment_id(donate_id, payment_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE prize_pool SET payment_id=? WHERE id=?", (payment_id, donate_id))
    conn.commit()
    conn.close()


def get_donation(donate_id):
    """برمی‌گردونه (user_id, payment_id, amount, status) یا None. ⚠️ SEC-03:
    user_id قبلاً برنگردونده می‌شد — یعنی checkpay_ تو payments.py هیچ راهی
    برای چک مالکیت نداشت (IDOR بالقوه). حالا caller باید user_id رو با
    درخواست‌کننده مقایسه کنه."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, payment_id, amount, status FROM prize_pool WHERE id=?", (donate_id,))
    row = c.fetchone()
    conn.close()
    return row


def set_donation_paid(donate_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE prize_pool SET status='paid' WHERE id=?", (donate_id,))
    conn.commit()
    conn.close()


def get_recent_donations(limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT p.id, u.full_name, p.amount, p.status, p.added_at
                 FROM prize_pool p JOIN users u ON p.user_id=u.user_id
                 ORDER BY p.added_at DESC LIMIT ?""", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows


def insert_prize_winner(season_id, user_id, rank, prize_amt):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO prize_winners (season_id,user_id,rank,prize_amt,paid_at) VALUES (?,?,?,?,?)",
              (season_id, user_id, rank, prize_amt, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_recent_winners(limit=6):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT u.full_name, u.username, pw.rank, pw.prize_amt, ps.name
        FROM prize_winners pw
        JOIN users u ON pw.user_id=u.user_id
        JOIN prize_seasons ps ON pw.season_id=ps.id
        ORDER BY pw.id DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows


def insert_broadcast(admin_id, message, sent_count):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO broadcasts (admin_id,message,sent_count,sent_at) VALUES (?,?,?,?)",
              (admin_id, message, sent_count, datetime.now().isoformat()))
    conn.commit()
    conn.close()
