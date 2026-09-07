"""
امتیازدهی کالرها — جایگزین submit_caller_rating/delete_caller_rating.
هدف اصلی فاز ۰-ب همینه: هر عضو لاگین‌شده (نه فقط admin/caller) باید بتونه
رأی بده — قبلاً kv_write_secure فقط admin/caller رو قبول می‌کرد.

⚠️ مجوز این‌جا چک نمی‌شه (لایه‌ی route انجامش می‌ده) — این ماژول فقط فرض
می‌کنه rater_telegram_id از یه session معتبر اومده.
"""
from datetime import datetime, timedelta

from signal_bot.site.db import get_db

RATING_MAX_PER_HOUR = 20  # قبلاً هیچ throttling ای رو امتیازدهی نبود


def _check_rate_limit(actor_telegram_id) -> bool:
    conn = get_db()
    c = conn.cursor()
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    c.execute(
        "SELECT COUNT(*) FROM attempt_log WHERE kind='rating' AND actor_telegram_id=? AND created_at > ?",
        (actor_telegram_id, one_hour_ago),
    )
    count = c.fetchone()[0]
    conn.close()
    return count < RATING_MAX_PER_HOUR


def _log_attempt(actor_telegram_id):
    conn = get_db()
    conn.execute(
        "INSERT INTO attempt_log (kind, actor_telegram_id, created_at) VALUES ('rating', ?, ?)",
        (actor_telegram_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def submit_rating(rater_telegram_id: int, rating: int, caller_telegram_id: int = None,
                   caller_name: str = None, comment: str = None):
    """ثبت یا آپدیت امتیاز (upsert — اگه همون rater قبلاً به همون کالر رأی
    داده بود، جایگزین می‌شه نه این‌که رد بشه). caller_telegram_id ترجیح داده
    می‌شه؛ caller_name فقط برای کالرهای بدون شناسه‌ی تلگرام (تاریخی/دستی).
    برمی‌گردونه (ok: bool, error: str|None)."""
    if not (1 <= rating <= 5):
        return False, "امتیاز باید بین ۱ تا ۵ باشه"
    if not caller_telegram_id and not caller_name:
        return False, "باید caller_telegram_id یا caller_name مشخص باشه"
    if not _check_rate_limit(rater_telegram_id):
        return False, "تعداد امتیازدهی‌های این ساعت زیاده، بعداً امتحان کن"

    conn = get_db()
    c = conn.cursor()
    # ⚠️ وقتی caller_telegram_id معلومه، فقط بر اساس اون match/update می‌کنیم —
    # caller_name رو نادیده می‌گیریم برای تطبیق (فقط موقع نوشتن تازه‌ش می‌کنیم).
    # اگه به‌جاش هم caller_telegram_id هم caller_name رو تو WHERE می‌ذاشتیم
    # (که قبلاً همین‌طور بود)، یه تغییر اسم تلگرام می‌تونست باعث بشه upsert
    # جدید بسازه به‌جای آپدیت قدیمی — دقیقاً همون مشکل پخش‌شدن امتیاز که این
    # ستون کلاً برای حلش اضافه شده بود.
    if caller_telegram_id:
        c.execute(
            "SELECT id FROM caller_ratings WHERE rater_telegram_id=? AND caller_telegram_id=?",
            (rater_telegram_id, caller_telegram_id),
        )
    else:
        c.execute(
            "SELECT id FROM caller_ratings WHERE rater_telegram_id=? "
            "AND caller_telegram_id IS NULL AND caller_name IS ?",
            (rater_telegram_id, caller_name),
        )
    existing = c.fetchone()
    now = datetime.utcnow().isoformat()
    if existing:
        c.execute("UPDATE caller_ratings SET rating=?, comment=?, caller_name=?, created_at=? WHERE id=?",
                   (rating, comment, caller_name, now, existing[0]))
    else:
        c.execute(
            "INSERT INTO caller_ratings (caller_telegram_id, caller_name, rater_telegram_id, rating, comment, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (caller_telegram_id, caller_name, rater_telegram_id, rating, comment, now),
        )
    conn.commit()
    conn.close()
    _log_attempt(rater_telegram_id)
    return True, None


def delete_rating(rating_id: int, actor_telegram_id: int, is_admin: bool = False) -> bool:
    """فقط صاحبِ رأی یا ادمین می‌تونه حذف کنه (چک مجوز واقعی این‌جاست، نه route،
    چون نیاز به دیدن rater_telegram_id واقعی رأی داره)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT rater_telegram_id FROM caller_ratings WHERE id=?", (rating_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    if not is_admin and row[0] != actor_telegram_id:
        conn.close()
        return False
    c.execute("DELETE FROM caller_ratings WHERE id=?", (rating_id,))
    conn.commit()
    conn.close()
    return True


def get_ratings_for_caller(caller_telegram_id: int = None, caller_name: str = None):
    conn = get_db()
    c = conn.cursor()
    if caller_telegram_id:
        c.execute(
            "SELECT id, rater_telegram_id, rating, comment, created_at FROM caller_ratings "
            "WHERE caller_telegram_id=? ORDER BY created_at DESC", (caller_telegram_id,))
    else:
        c.execute(
            "SELECT id, rater_telegram_id, rating, comment, created_at FROM caller_ratings "
            "WHERE caller_name=? AND caller_telegram_id IS NULL ORDER BY created_at DESC", (caller_name,))
    cols = ["id", "rater_telegram_id", "rating", "comment", "created_at"]
    rows = [dict(zip(cols, r)) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_ratings():
    """همه‌ی رأی‌های تک‌تک (نه aggregate) — برای بارگذاری یک‌جای همه‌ی
    امتیازها تو صفحه‌ی «کالرها». هر ردیف یه display_name هم داره که از
    caller_name یا (اگه نبود) آخرین session معروف caller_telegram_id
    می‌گیره — دقیقاً همون زنجیره‌ای که signals.get_feed برای owner استفاده
    می‌کنه، تا کلاینت بتونه رأی‌ها رو با همون اسمی که رو کارت سیگنال
    می‌بینه match کنه."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, caller_telegram_id, caller_name, rater_telegram_id, rating, comment, created_at
                 FROM caller_ratings ORDER BY created_at DESC""")
    cols = ["id", "caller_telegram_id", "caller_name", "rater_telegram_id", "rating", "comment", "created_at"]
    rows = [dict(zip(cols, r)) for r in c.fetchall()]
    for row in rows:
        display_name = None
        if row["caller_telegram_id"]:
            # ⚠️ عمداً session رو *همیشه* دوباره چک می‌کنیم، نه فقط وقتی
            # caller_name خالیه — چون هدف اینه همه‌ی ردیف‌های یه
            # caller_telegram_id واحد، دقیقاً یه display_name یکسان بگیرن
            # (از یه منبع تازه)، نه هرکدوم اسمی که موقع ثبت همون ردیف خاص
            # ذخیره شده بود. وگرنه گروه‌بندی سمت کلاینت (بر اساس اسم) دوباره
            # همون کالر رو به چندتا گروه جدا می‌شکافت.
            c.execute(
                "SELECT username, first_name FROM sessions WHERE telegram_id=? ORDER BY created_at DESC LIMIT 1",
                (row["caller_telegram_id"],),
            )
            sess = c.fetchone()
            display_name = (sess[1] or sess[0]) if sess else None
        row["display_name"] = display_name or row["caller_name"] or "ناشناس"
        c.execute(
            "SELECT username, first_name FROM sessions WHERE telegram_id=? ORDER BY created_at DESC LIMIT 1",
            (row["rater_telegram_id"],),
        )
        rater_sess = c.fetchone()
        row["rater_display_name"] = (rater_sess[1] or rater_sess[0]) if rater_sess else None
    conn.close()
    return rows


_VALID_TIERS = ("bronze", "silver", "gold", "diamond")
_TIER_BADGE = {"bronze": "🥉", "silver": "🥈", "gold": "🥇", "diamond": "💎"}


def _caller_key(caller_telegram_id=None, caller_name=None) -> str:
    return str(caller_telegram_id) if caller_telegram_id else f"name:{caller_name}"


def set_caller_tier(caller_telegram_id, caller_name, tier, set_by: int):
    """tier=None یا '' یعنی حذف تیر (نه ست‌کردن یه چیز خالی). فقط ادمین صدا
    می‌زنه (چک تو routes.py) — این تابع خودش نقش رو چک نمی‌کنه، فقط ذخیره."""
    key = _caller_key(caller_telegram_id, caller_name)
    conn = get_db()
    if not tier:
        conn.execute("DELETE FROM caller_tiers WHERE caller_key=?", (key,))
    else:
        if tier not in _VALID_TIERS:
            conn.close()
            raise ValueError(f"تیر نامعتبر: {tier!r} — باید یکی از {_VALID_TIERS} باشه")
        conn.execute(
            "INSERT INTO caller_tiers (caller_key, caller_telegram_id, caller_name, tier, set_by, updated_at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(caller_key) DO UPDATE SET "
            "tier=excluded.tier, set_by=excluded.set_by, updated_at=excluded.updated_at",
            (key, caller_telegram_id, caller_name, tier, set_by, datetime.utcnow().isoformat()),
        )
    conn.commit()
    conn.close()


def get_all_caller_tiers() -> dict:
    """{caller_key: tier} — برای join سریع تو لیست‌ها، بدون یه query جدا به‌ازای هر کالر."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT caller_key, tier FROM caller_tiers")
    out = {k: t for k, t in c.fetchall()}
    conn.close()
    return out


def get_top_callers(limit: int = 10):
    """فاز ۳: نسخه‌ی مرتب‌شده و محدودشده‌ی get_all_ratings_summary، مخصوص
    لیدربورد — تابع قبلی رو عمداً دست‌نزدم چون جای دیگه (صفحه‌ی کالرها) با
    فرض «همه‌ی نتایج، بدون ترتیب خاص» صداش می‌زنه.
    ⚠️ حالا tier (دستی، فاز جدید) هم اضافه می‌شه، اگه ادمین ست کرده باشه."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT COALESCE(CAST(caller_telegram_id AS TEXT), 'name:'||caller_name) as gkey,
               caller_telegram_id, caller_name, AVG(rating) as avg_rating, COUNT(*) as n
        FROM caller_ratings
        GROUP BY gkey
        ORDER BY avg_rating DESC, n DESC
        LIMIT ?
    """, (limit,))
    tiers = get_all_caller_tiers()
    rows = []
    for gkey, ctid, name, avg, n in c.fetchall():
        rows.append({
            "caller_telegram_id": ctid,
            "caller_name": name, "avg_rating": round(avg, 2), "count": n,
            "tier": tiers.get(gkey), "tier_badge": _TIER_BADGE.get(tiers.get(gkey)),
        })
    conn.close()
    return rows


def get_all_ratings_summary():
    """میانگین + تعداد رأی به ازای هر کالر — برای صفحه‌ی «کالرها».
    ⚠️ گروه‌بندی بر اساس caller_telegram_id وقتی موجوده (نه جفت
    telegram_id+name) — وگرنه اگه caller_name تو ردیف‌های مختلف یکی نبود
    (که با فیکس submit_rating دیگه نباید پیش بیاد، ولی برای دیتای قدیمی‌تر
    هم مقاومه)، همون کالر به چند گروه جدا می‌شکافت."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT COALESCE(CAST(caller_telegram_id AS TEXT), 'name:'||caller_name) as gkey,
               caller_telegram_id, caller_name, AVG(rating) as avg_rating, COUNT(*) as n
        FROM caller_ratings
        GROUP BY gkey
    """)
    tiers = get_all_caller_tiers()
    rows = []
    for gkey, ctid, name, avg, n in c.fetchall():
        rows.append({
            "caller_telegram_id": ctid,
            "caller_name": name, "avg_rating": round(avg, 2), "count": n,
            "tier": tiers.get(gkey), "tier_badge": _TIER_BADGE.get(tiers.get(gkey)),
        })
    conn.close()
    return rows
