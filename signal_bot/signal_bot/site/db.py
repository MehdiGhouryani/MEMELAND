"""
اتصال به SQLite سایت (جدا از signals.db خودِ بات — دیتای عمومی/محتوای سایت
از دیتای عملیاتی بات جداست، دقیقاً همون تفکیک مفهومی که قبلاً هم بین
signals داخلی بات و signals_feed سایت وجود داشت، فقط الان هر دو SQLite‌ان
نه یکی SQLite یکی Postgres).

⚠️ صادقانه: این اسکیما جایگزین Postgres/Supabase سایته. جدول signals دقیقاً
از رو migrate_legacy_signals.sql (که واقعاً دیدمش) کپی شده، پس اون یکی
مطمئنم. sessions/caller_ratings/kv_store بر اساس رفتار قابل‌مشاهده‌ی کلاینت
(چی می‌فرسته/چی انتظار داره برگرده) طراحی شده، نه دیدن اسکیمای واقعی قبلی —
چون گفتی دیتای واقعی نیست، این یعنی از صفر شروع می‌کنیم، پس این یه طراحی
جدیده، نه بازسازی چیزی که باید دقیقاً یکی باشه.
"""
import os
import sqlite3

DB_FILE = os.environ.get("SITE_DB_FILE", "site.db")


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # ---------- kv_store: جایگزین عمومی برای هرچی که قبلاً بلاب بود ----------
    # مقاله‌ها، استراتژی‌ها، و کدهای PIN قدیمی (subscriber/community/unlock)
    # همه از همین یه جدول رد می‌شن، دقیقاً مثل قبل — فقط پشتش SQLite‌ه نه
    # Postgres. مقادیر حساس (PIN) هش‌شده ذخیره می‌شن (services/site_auth.py).
    c.execute("""CREATE TABLE IF NOT EXISTS kv_store(
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    )""")

    # ---------- sessions ----------
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(
        token TEXT PRIMARY KEY,
        telegram_id INTEGER NOT NULL,
        username TEXT,
        first_name TEXT,
        photo_url TEXT,
        role TEXT,                    -- NULL تا وقتی claim_role صدا زده بشه؛ بعدش 'admin' یا 'caller'
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_telegram_id ON sessions(telegram_id)")

    # ---------- user_profiles (دائمی، به‌ازای telegram_id — نه به‌ازای session) ----------
    # ⚠️ قبلاً role فقط رو خودِ session بود، و نام نمایشی فقط تو localStorage
    # مرورگر؛ یعنی با انقضای session یا عوض‌کردن مرورگر/دستگاه، هردو گم
    # می‌شدن. این جدول همون دو مقدار رو دائمی، وصل به هویت تلگرام نگه می‌داره.
    c.execute("""CREATE TABLE IF NOT EXISTS user_profiles(
        telegram_id INTEGER PRIMARY KEY,
        display_name TEXT,
        role TEXT,
        updated_at TEXT NOT NULL
    )""")

    # ---------- signals (public feed) ----------
    # ⚠️ این بخش دقیقاً از migrate_legacy_signals.sql کپی شده — اون رو واقعاً دیدم.
    c.execute("""CREATE TABLE IF NOT EXISTS signals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT DEFAULT 'manual',           -- 'bot' | 'manual'
        bot_signal_id INTEGER,                  -- id سیگنال تو signals.db بات، اگه از اون سینک شده (یکتا وقتی NULL نیست)
        owner_telegram_id INTEGER,
        caller_name TEXT,                       -- برای سیگنال‌های دستی/تاریخی بدون owner_telegram_id
        channel TEXT DEFAULT 'alt',
        coin TEXT,
        direction TEXT,
        tier TEXT DEFAULT 'free',
        entry_open INTEGER DEFAULT 1,           -- 0/1 (SQLite بولین نداره)
        review_status TEXT DEFAULT 'approved',  -- 'pending' | 'approved' | 'rejected'
        outcome_status TEXT DEFAULT 'open',     -- 'open' | 'win' | 'loss'
        result TEXT,
        note TEXT,
        hashtag TEXT,
        hold_period TEXT,
        thesis TEXT,
        rating NUMERIC,
        before_img TEXT,
        after_img TEXT,
        buy_link TEXT,
        contract_address TEXT,
        dex_type TEXT,
        created_at TEXT NOT NULL
    )""")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_bot_signal_id ON signals(bot_signal_id) WHERE bot_signal_id IS NOT NULL")
    c.execute("CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at)")

    # آلارم قیمت ورود (chain لازمه چون contract_address به‌تنهایی چندمعنایی‌ه —
    # همون آدرس می‌تونه رو چند شبکه‌ی EVM مختلف، توکن‌های کاملاً نامرتبط باشه).
    # entry_alert_sent: 0/1، برای این‌که هر سیگنال فقط یه‌بار آلارم بده.
    for col, typ in [("chain", "TEXT"), ("entry_price", "REAL"), ("entry_alert_sent", "INTEGER DEFAULT 0")]:
        try:
            c.execute(f"ALTER TABLE signals ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
    c.execute("""CREATE INDEX IF NOT EXISTS idx_signals_entry_alert
                 ON signals(entry_alert_sent) WHERE contract_address IS NOT NULL AND entry_price IS NOT NULL""")

    c.execute("""CREATE TABLE IF NOT EXISTS signal_result_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
        result TEXT,
        outcome_status TEXT,
        changed_at TEXT NOT NULL
    )""")

    # ---------- caller_ratings ----------
    # ⚠️ عمداً caller_telegram_id (نه فقط caller_name) اضافه شد — تو تحلیل قبلی
    # فلگ شده بود که کلید کردن فقط رو اسم نمایشی باعث پخش‌شدن امتیاز کالر
    # می‌شه اگه اسمش تو تلگرام عوض بشه. این‌جا چون از صفر می‌سازیم، از اول
    # درست طراحیش می‌کنیم: caller_telegram_id منبع اصلی هویته وقتی موجوده،
    # caller_name فقط برای کالرهای تاریخی/دستی بدون شناسه‌ی تلگرام.
    c.execute("""CREATE TABLE IF NOT EXISTS caller_ratings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caller_telegram_id INTEGER,
        caller_name TEXT,
        rater_telegram_id INTEGER NOT NULL,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        comment TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(rater_telegram_id, caller_telegram_id, caller_name)
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_caller_ratings_caller ON caller_ratings(caller_telegram_id, caller_name)")

    # ---------- caller_tiers (دستی، فقط ادمین می‌ده/می‌گیره — نه محاسبه‌ی خودکار) ----------
    # caller_key = str(caller_telegram_id) اگه باشه، وگرنه 'name:'+caller_name —
    # همون الگوی گروه‌بندی get_top_callers.
    c.execute("""CREATE TABLE IF NOT EXISTS caller_tiers(
        caller_key TEXT PRIMARY KEY,
        caller_telegram_id INTEGER,
        caller_name TEXT,
        tier TEXT NOT NULL,
        set_by INTEGER,
        updated_at TEXT NOT NULL
    )""")

    # ---------- audit ----------
    c.execute("""CREATE TABLE IF NOT EXISTS admin_action_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_telegram_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target TEXT,
        details TEXT,
        created_at TEXT NOT NULL
    )""")

    # ---------- throttling (تلاش‌های پین/امتیازدهی) ----------
    c.execute("""CREATE TABLE IF NOT EXISTS attempt_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,          -- 'pin' | 'rating' | ...
        actor_telegram_id INTEGER,
        actor_ip TEXT,
        created_at TEXT NOT NULL
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_attempt_log_lookup ON attempt_log(kind, actor_telegram_id, created_at)")

    conn.commit()
    conn.close()
