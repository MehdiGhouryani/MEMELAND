"""لایه دسترسی به جدول signals — همه query های خام مربوط به سیگنال‌ها."""
from datetime import datetime

from signal_bot.db.connection import get_db


def daily_signal_count(user_id):
    """
    ⚠️ فیکس منطقه‌ی زمانی: قبلاً «امروز» با ساعت محلی سرور (datetime.now())
    محاسبه می‌شد، و created_at این جدول هم قبلاً محلی بود — تا اینجا داخلی
    سازگار بود. ولی سینک دوطرفه‌ی سایت↔ربات که اضافه شد، همین ستون
    created_at رو با رکوردهایی که از سایت میان (UTC ذخیره می‌شن) قاطی کرد.
    اگه این تابع محلی می‌موند ولی insert_signal زیرش UTC بشه، سهمیه‌ی
    روزانه با آفستِ ساعت سرور جابه‌جا می‌شد. برای رفع کامل ناسازگاری، این
    ستون از این‌جا به بعد سراسر UTC ذخیره و مقایسه می‌شه.
    توجه: یعنی سقف سهمیه‌ی روزانه از این پس در نیمه‌شب UTC ریست می‌شه، نه
    نیمه‌شب محلی سرور — یه تغییر رفتاریه که باید بدونید.
    """
    conn = get_db()
    c = conn.cursor()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    c.execute("""SELECT COUNT(*) FROM signals
                 WHERE user_id=? AND created_at LIKE ? AND status != 'rejected'""",
              (user_id, f"{today}%"))
    count = c.fetchone()[0]
    conn.close()
    return count


def insert_signal(user_id, coin, signal_type="full", direction=None, entry=None, sl=None, tp=None,
                   description="", photo_file_id="", channel="alt", risk_level="low"):
    """
    ثبت سیگنال جدید. فقط user_id و coin لازمن — بقیه اختیاری هستن چون Full
    Signal (عکس) و Fast Call (بدون Entry/TP) نیازی به مقادیر عددی کامل ندارن
    (بند ۴ نیازمندی‌ها).
    """
    conn = get_db()
    c = conn.cursor()
    # ⚠️ UTC — نگاه کن به توضیح داخل daily_signal_count بالا. تا با
    # created_at ردیف‌های سینک‌شده از سایت (که همیشه UTC هستن) یکسان بمونه
    # و لیدربورد/سهمیه هیچ‌جا آفست ساعت سرور رو نبینن.
    c.execute("""INSERT INTO signals
        (user_id,coin,direction,entry,stop_loss,take_profit,
         description,signal_type,photo_file_id,channel,risk_level,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending',?)""",
        (user_id, coin, direction, entry, sl, tp,
         description, signal_type, photo_file_id, channel, risk_level,
         datetime.utcnow().isoformat()))
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
    """برمی‌گردونه (user_id, coin, direction, photo_file_id, signal_type, description, channel, risk_level) یا None.
    ⚠️ channel هم مثل description تازه اضافه شد، به همون دلیل: approve_ باید
    مقدار واقعی کانال رو به push_signal_created بده، نه پیش‌فرض هاردکد.
    risk_level هم به همون الگو اضافه شد (فیچر سطح ریسک).
    صدا زننده‌ها: approve_ و cmd_resync_signal (بر اساس موقعیت unpack می‌کنن،
    آپدیت شدن) و reject_ (فقط row[0] رو می‌خونه، بی‌اثر از این تغییر)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, coin, direction, photo_file_id, signal_type, description, channel, risk_level FROM signals WHERE id=?", (signal_id,))
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


def has_any_signal(user_id) -> bool:
    """فاز ۲: آیا این کاربر تا حالا حتی یه سیگنال ثبت کرده (هر status)؟ برای
    تصمیم نشون‌دادن دکمه‌ی «منوی سیگنال‌دهنده» تو منوی اصلی."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM signals WHERE user_id=? LIMIT 1", (user_id,))
    found = c.fetchone() is not None
    conn.close()
    return found


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


def get_leaderboard_ranked_full(since_iso):
    """
    فاز ۲ (بازبینی UX — لیدربورد نسبی): نسخه‌ی کامل (بدون LIMIT) لیدربورد
    همون دوره + ستون رتبه (RANK window function روی همون امتیاز تجمیعی).
    هدف: پیدا کردن جایگاه یه کاربر خاص داخل کل صف، نه فقط تاپ ۱۰ — تا
    کاربری که تو تاپ ۱۰ نیست هم بتونه ببینه چند نفر بالا/پایینشن، به‌جای
    اینکه اصلاً تو لیدربورد دیده نشه (طبق پرینسیپل UX گیمیفیکیشن: دیدن
    فقط عدد رتبه‌ی مطلق بین صدها نفر بی‌انگیزه‌کننده‌ست؛ دیدن «همسایه‌های
    رتبه»ی خودت مفیدتره).
    خروجی هر ردیف دقیقاً هم‌شکل get_leaderboard_rows + یه ستون rnk اضافه.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, full_name, username, level, pts, cnt, wins, rnk FROM (
            SELECT s.user_id, u.full_name, u.username, u.level, SUM(s.points) as pts,
                   COUNT(s.id) as cnt,
                   SUM(CASE WHEN s.result != 'loss' AND s.result != 'open' THEN 1 ELSE 0 END) as wins,
                   RANK() OVER (ORDER BY SUM(s.points) DESC) as rnk
            FROM signals s JOIN users u ON s.user_id = u.user_id
            WHERE s.status='approved' AND s.created_at >= ?
            GROUP BY s.user_id
        ) ORDER BY rnk ASC
    """, (since_iso,))
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


def get_approved_signal_ids():
    """برای ابزار تشخیصی sync_report — همه‌ی id هایی که تو بات approved شدن،
    تا با site.db مقایسه بشن و ببینیم کدوم‌ها سینک نشدن."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM signals WHERE status='approved'")
    ids = [r[0] for r in c.fetchall()]
    conn.close()
    return ids


# ══════════════════════════════════════════════════════════════════════════
#  سینک سایت → ربات
#
#  🚨 مشکلی که این بخش حل می‌کنه: سینک تا الان *یک‌طرفه* بود. یه سیگنال که
#  تو ربات تأیید می‌شد، با site_sync.push_signal_created به سایت می‌رفت. ولی
#  سیگنالی که از وب‌اپ ثبت می‌شد، هیچ‌وقت به دیتابیس ربات نمی‌رسید — و چون
#  همه‌ی نماهای ربات (فید عمومی، سیگنال‌های من، لیدربورد) از جدول signals
#  دیتابیس ربات می‌خونن، اون سیگنال‌ها اصلاً وجود نداشتن.
#  علائمی که گزارش شد («توی وب‌اپ هست، تو چت نیست» و برعکس) دقیقاً همین بود.
# ══════════════════════════════════════════════════════════════════════════

def get_by_site_id(site_signal_id):
    """id سیگنال ربات که از یه سیگنال سایت ساخته شده (یا None)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM signals WHERE site_signal_id=?", (site_signal_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def insert_from_site(site_signal_id, user_id, coin, direction=None, description="",
                     photo_file_id="", channel="alt", risk_level="low", created_at=None):
    """
    ثبت یه سیگنالِ ساخته‌شده-در-سایت داخل دیتابیس ربات.

    status='approved' چون این سیگنال از قبل از مسیر مجاز وب‌اپ (با هویت
    اثبات‌شده و چک سهمیه) رد شده — دوباره فرستادنش به صف تأیید، هم تکراریه
    هم باعث می‌شه تا تأیید دستی، تو ربات نامرئی بمونه.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO signals
        (user_id, coin, direction, description, signal_type, photo_file_id,
         channel, risk_level, status, result, points, site_signal_id, created_at)
        VALUES (?,?,?,?,'full',?,?,?,'approved','open',0,?,?)""",
        (user_id, coin, direction, description or "", photo_file_id or "",
         channel or "alt", risk_level or "low", site_signal_id,
         # ⚠️ UTC — همون دلیل daily_signal_count. اگه created_at از سایت
         # نیومده باشه (نباید پیش بیاد، ولی برای امنیت)، fallback هم باید
         # همون قرارداد رو رعایت کنه، وگرنه دقیقاً همون قاطی‌شدنی که
         # می‌خواستیم جلوش رو بگیریم دوباره برمی‌گرده.
         created_at or datetime.utcnow().isoformat()))
    signal_id = c.lastrowid
    conn.commit()
    conn.close()
    return signal_id


def link_site_id(bot_signal_id, site_signal_id):
    """وصل کردن یه سیگنال ربات به ردیف متناظرش تو سایت (برای backfill)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE signals SET site_signal_id=? WHERE id=?", (site_signal_id, bot_signal_id))
    conn.commit()
    conn.close()


def get_sync_snapshot():
    """
    (approved_ids, site_linked_ids) — برای گزارش و آشتی‌دادن دو دیتابیس،
    با یک بار باز کردن اتصال به‌جای N بار.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM signals WHERE status='approved'")
    approved = [r[0] for r in c.fetchall()]
    c.execute("SELECT site_signal_id FROM signals WHERE site_signal_id IS NOT NULL")
    linked = {r[0] for r in c.fetchall()}
    conn.close()
    return approved, linked
