"""لایه دسترسی به جدول caller_donations — حمایت مالی مستقیم از یک Alpha Caller مشخص (بند ۱۳)."""
from datetime import datetime

from signal_bot.db.connection import get_db


def insert_donation(donor_user_id, recipient_user_id, amount, order_id, invoice_id, invoice_url):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO caller_donations
        (donor_user_id, recipient_user_id, amount, currency, order_id, invoice_id, invoice_url, status, added_at)
        VALUES (?,?,?,'USDT',?,?,?,'pending',?)""",
        (donor_user_id, recipient_user_id, amount, order_id, invoice_id, invoice_url, datetime.now().isoformat()))
    donate_id = c.lastrowid
    conn.commit()
    conn.close()
    return donate_id


def get_donation_by_order_id(order_id):
    """برای وب‌هوک — برمی‌گردونه (id, donor_user_id, recipient_user_id, amount, status) یا None."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, donor_user_id, recipient_user_id, amount, status
                 FROM caller_donations WHERE order_id=?""", (order_id,))
    row = c.fetchone()
    conn.close()
    return row


def set_payment_id(donate_id, payment_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE caller_donations SET payment_id=? WHERE id=?", (payment_id, donate_id))
    conn.commit()
    conn.close()


def get_donation(donate_id):
    """برمی‌گردونه (donor_user_id, recipient_user_id, payment_id, amount, status) یا None."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT donor_user_id, recipient_user_id, payment_id, amount, status
                 FROM caller_donations WHERE id=?""", (donate_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_donation_by_invoice(invoice_id):
    """نگه‌داشته شده برای دیباگ دستی؛ برای وب‌هوک از get_donation_by_order_id استفاده کن."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, donor_user_id, recipient_user_id, amount, status
                 FROM caller_donations WHERE invoice_id=?""", (invoice_id,))
    row = c.fetchone()
    conn.close()
    return row


def set_donation_paid(donate_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE caller_donations SET status='paid' WHERE id=?", (donate_id,))
    conn.commit()
    conn.close()


def get_total_received(recipient_user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT SUM(amount) FROM caller_donations
                 WHERE recipient_user_id=? AND status='paid'""", (recipient_user_id,))
    total = c.fetchone()[0] or 0
    conn.close()
    return total


def get_recent_for_recipient(recipient_user_id, limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT d.amount, d.status, d.added_at, u.full_name, u.username
                 FROM caller_donations d JOIN users u ON d.donor_user_id=u.user_id
                 WHERE d.recipient_user_id=? ORDER BY d.added_at DESC LIMIT ?""",
              (recipient_user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows


def get_recent_all(limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT d.id, du.full_name, ru.full_name, d.amount, d.status, d.added_at
        FROM caller_donations d
        JOIN users du ON d.donor_user_id=du.user_id
        JOIN users ru ON d.recipient_user_id=ru.user_id
        ORDER BY d.added_at DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows
