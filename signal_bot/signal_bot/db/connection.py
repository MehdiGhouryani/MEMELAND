"""اتصال به SQLite و ساخت/آپدیت جداول. تمام ماژول‌های db از get_db() اینجا استفاده می‌کنن."""
import sqlite3
import logging

from signal_bot.config import settings


def get_db():
    return sqlite3.connect(settings.DB_FILE)


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY,
        username   TEXT,
        full_name  TEXT,
        joined_at  TEXT,
        total_pts  INTEGER DEFAULT 0,
        streak     INTEGER DEFAULT 0,
        max_streak INTEGER DEFAULT 0,
        level      TEXT DEFAULT '🪨 مبتدی',
        is_blocked INTEGER DEFAULT 0,
        role       TEXT DEFAULT 'rookie'
    )""")

    # نکته: ستون‌های tp2/tp3/timeframe/leverage/market_type که مال ویزارد قدیمیِ
    # حذف‌شده (فاز ۳) بودن، از schema پاک شدن — هیچ کدی دیگه ازشون استفاده
    # نمی‌کرد (فقط با رشته خالی پر می‌شدن). دو ستون جدید reviewed_by/result_set_by
    # برای accountability اضافه شدن (کدوم ادمین/VIP Helper این کار رو کرده).
    c.execute("""CREATE TABLE IF NOT EXISTS signals (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER,
        coin          TEXT,
        direction     TEXT,
        entry         REAL,
        stop_loss     REAL,
        take_profit   REAL,
        description   TEXT DEFAULT '',
        signal_type   TEXT DEFAULT 'full',
        photo_file_id TEXT DEFAULT '',
        status        TEXT DEFAULT 'pending',
        result        TEXT DEFAULT 'open',
        points        INTEGER DEFAULT 0,
        reviewed_by   INTEGER,
        result_set_by INTEGER,
        created_at    TEXT,
        closed_at     TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS prize_pool (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        amount      REAL,
        currency    TEXT DEFAULT 'USDT',
        order_id    TEXT,
        invoice_id  TEXT,
        invoice_url TEXT,
        payment_id  TEXT,
        status      TEXT DEFAULT 'pending',
        added_at    TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS prize_seasons (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT,
        start_date TEXT,
        end_date   TEXT,
        status     TEXT DEFAULT 'active',
        total_prize REAL DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS prize_winners (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        season_id INTEGER,
        user_id   INTEGER,
        rank      INTEGER,
        prize_amt REAL,
        paid_at   TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS broadcasts (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id   INTEGER,
        message    TEXT,
        sent_count INTEGER DEFAULT 0,
        sent_at    TEXT
    )""")

    # رول‌های مدیریتی غیر از Admin اصلی (که از ADMIN_IDS در .env میاد).
    # فعلاً فقط VIP Helper، ولی ستون role برای گسترش آینده نگه داشته شده.
    # added_by: کدوم ادمین این دسترسی رو داده (accountability).
    c.execute("""CREATE TABLE IF NOT EXISTS staff (
        user_id  INTEGER PRIMARY KEY,
        role     TEXT DEFAULT 'vip_helper',
        added_by INTEGER,
        added_at TEXT
    )""")

    # حمایت مالی مستقیم کاربر از یک Alpha Caller مشخص — کاملاً جدا از prize_pool
    # عمومی (بند ۱۳). donor = کسی که پرداخت می‌کنه، recipient = تحلیلگری که حمایت می‌شه.
    c.execute("""CREATE TABLE IF NOT EXISTS caller_donations (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_user_id     INTEGER,
        recipient_user_id INTEGER,
        amount            REAL,
        currency          TEXT DEFAULT 'USDT',
        order_id          TEXT,
        invoice_id        TEXT,
        invoice_url       TEXT,
        payment_id        TEXT,
        status            TEXT DEFAULT 'pending',
        added_at          TEXT
    )""")

    # دفتر پاداش — عمداً مستقل از prize_pool/prize_seasons (بند ۱۲). فعلاً فقط
    # ثبت دستی توسط ادمین؛ ساختارش آماده‌ست تا بعداً یه موتور پاداش خودکار
    # بدون تغییر schema بتونه همین جدول رو پر کنه.
    c.execute("""CREATE TABLE IF NOT EXISTS rewards (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        amount      REAL DEFAULT 0,
        reason      TEXT,
        granted_by  INTEGER,
        granted_at  TEXT,
        status      TEXT DEFAULT 'recorded'
    )""")

    # آپدیت ستون‌های قدیمی (برای دیتابیس‌های از نسخه‌های قبلی).
    # ⚠️ تعمداً دیگه چیزی برای tp2/tp3/timeframe/leverage/market_type/
    # last_signal_date اضافه نمی‌کنیم (بلااستفاده بودن) — دیتابیس‌های قدیمی که
    # از قبل این ستون‌ها رو دارن، بی‌خطر نادیده گرفته می‌شن (کد دیگه بهشون کاری نداره).
    upgrades = [
        ("users", "streak",            "INTEGER DEFAULT 0"),
        ("users", "max_streak",        "INTEGER DEFAULT 0"),
        ("users", "level",             "TEXT DEFAULT '🪨 مبتدی'"),
        ("users", "is_blocked",        "INTEGER DEFAULT 0"),
        ("users", "role",              "TEXT DEFAULT 'rookie'"),
        ("signals", "description",     "TEXT DEFAULT ''"),
        ("signals", "signal_type",     "TEXT DEFAULT 'full'"),
        ("signals", "photo_file_id",   "TEXT DEFAULT ''"),
        ("signals", "reviewed_by",     "INTEGER"),
        ("signals", "result_set_by",   "INTEGER"),
        ("signals", "channel",         "TEXT DEFAULT 'alt'"),
        ("prize_pool", "invoice_id",   "TEXT"),
        ("prize_pool", "invoice_url",  "TEXT"),
        ("prize_pool", "payment_id",   "TEXT"),
        ("prize_pool", "status",       "TEXT DEFAULT 'pending'"),
        ("prize_pool", "order_id",     "TEXT"),
        ("staff", "added_by",          "INTEGER"),
    ]
    for table, col, typ in upgrades:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                logging.warning(f"آپگرید ستون {table}.{col} ناموفق: {e}")

    # ایندکس‌ها — کوئری‌های پرتکرار (شمارش سیگنال روزانه، سیگنال‌های کاربر، فید
    # عمومی، جست‌وجوی سفارش پرداخت با order_id در وب‌هوک) بدون این‌ها فول‌اسکن
    # می‌خوردن. نبود این‌ها باگ نبود، ولی با رشد داده کند می‌شد.
    indexes = [
        ("idx_signals_user_status",    "signals",  "(user_id, status)"),
        ("idx_signals_status_result",  "signals",  "(status, result)"),
        ("idx_signals_created_at",     "signals",  "(created_at)"),
        ("idx_prize_pool_order",       "prize_pool", "(order_id)"),
        ("idx_caller_donations_order", "caller_donations", "(order_id)"),
        ("idx_rewards_user",           "rewards",  "(user_id)"),
    ]
    for idx_name, table, cols in indexes:
        c.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}{cols}")

    conn.commit()
    conn.close()
