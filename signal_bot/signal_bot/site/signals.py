"""
CRUD سیگنال‌های سایت — جایگزین signal_create/signal_edit/signal_set_result/
signal_toggle_entry_open. مجوز (کی حق ویرایش/تأیید نتیجه داره) این‌جا چک
نمی‌شه — لایه‌ی route اینو با site.auth.get_session قبلش انجام می‌ده.

⚠️ caller_name/date: برخلاف نسخه‌ی قبلی (که این دو رو تو bulk-import سایت
اصلاً به سرور نمی‌فرستاد — باگ‌شده بود)، این‌جا از اول جزو پارامترهای
create_signal هستن، چون خودمون داریم اسکیما رو از صفر می‌سازیم.
"""
from datetime import datetime

from signal_bot.site.db import get_db

_EDITABLE_FIELDS = [
    "channel", "coin", "direction", "tier", "entry_open", "note", "hashtag", "hold_period",
    "thesis", "rating", "before_img", "after_img", "buy_link",
    "contract_address", "dex_type", "caller_name", "created_at",
]


def get_id_by_bot_signal_id(bot_signal_id: int):
    """پیدا کردن id سایتِ سیگنالی که از بات سینک شده (bot_signal_id غیر-null و
    یکتاست، طبق UNIQUE INDEX تو db.py) — لازم برای push_signal_result که فقط
    bot_signal_id رو داره، نه id خودِ سایت."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM signals WHERE bot_signal_id=?", (bot_signal_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_owner(signal_id: int):
    """owner_telegram_id یه سیگنال رو برمی‌گردونه (یا None اگه سیگنال نبود
    یا owner نداشت) — برای چک «فقط صاحبش یا ادمین» رو ثبت نتیجه/toggle entry."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT owner_telegram_id FROM signals WHERE id=?", (signal_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def create_signal(
    owner_telegram_id=None, caller_name=None, channel="alt", coin="", direction=None,
    tier="free", note="", hashtag=None, before_img=None, buy_link=None,
    contract_address=None, dex_type=None, source="manual", bot_signal_id=None,
    created_at=None,
):
    """ثبت سیگنال جدید. created_at اگه داده نشه، همین لحظه‌ست — ولی برخلاف
    قبل، بولک-ایمپورت می‌تونه صریح تاریخ تاریخی بده (باگ قبلی همین بود که
    این امکان اصلاً وجود نداشت)."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """INSERT INTO signals
           (source, bot_signal_id, owner_telegram_id, caller_name, channel, coin, direction,
            tier, entry_open, review_status, outcome_status, note, hashtag,
            before_img, buy_link, contract_address, dex_type, created_at)
           VALUES (?,?,?,?,?,?,?,?,1,'approved','open',?,?,?,?,?,?,?)""",
        (source, bot_signal_id, owner_telegram_id, caller_name, channel, coin, direction,
         tier, note, hashtag, before_img, buy_link, contract_address, dex_type,
         created_at or datetime.utcnow().isoformat()),
    )
    signal_id = c.lastrowid
    conn.commit()
    conn.close()
    return signal_id


def edit_signal(signal_id: int, **fields):
    """الگوی COALESCE: فقط فیلدهایی که واقعاً پاس داده شدن (یعنی تو fields
    هستن، حتی اگه مقدارشون None/خالی باشه) آپدیت می‌شن؛ بقیه دست‌نخورده
    می‌مونن. برای پاک‌کردن یه فیلد اختیاری، مقدارش رو صراحتاً None/'' پاس
    بده — این دقیقاً همون رفتاریه که تو باگ قبلی (قبل از فیکس) نداشت.
    برمی‌گردونه True اگه سیگنال پیدا شد و آپدیت شد، وگرنه False."""
    unknown = set(fields) - set(_EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"فیلدهای ناشناخته برای edit_signal: {unknown}")
    if not fields:
        return True  # هیچ‌چی برای آپدیت نیست، خطا هم نیست

    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [signal_id]
    conn = get_db()
    c = conn.cursor()
    c.execute(f"UPDATE signals SET {set_clause} WHERE id=?", values)
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def set_result(signal_id: int, result: str, outcome_status: str):
    """نتیجه رو آپدیت می‌کنه + یه ردیف تاریخچه اضافه می‌کنه (signal_result_history)."""
    if outcome_status not in ("open", "win", "loss"):
        raise ValueError(f"outcome_status نامعتبر: {outcome_status!r}")
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE signals SET result=?, outcome_status=? WHERE id=?", (result, outcome_status, signal_id))
    updated = c.rowcount > 0
    if updated:
        c.execute(
            "INSERT INTO signal_result_history (signal_id, result, outcome_status, changed_at) VALUES (?,?,?,?)",
            (signal_id, result, outcome_status, datetime.utcnow().isoformat()),
        )
    conn.commit()
    conn.close()
    return updated


def toggle_entry_open(signal_id: int):
    """entry_open رو معکوس می‌کنه (باز↔بسته). برمی‌گردونه مقدار جدید (0/1) یا None اگه سیگنال پیدا نشد."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT entry_open FROM signals WHERE id=?", (signal_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    new_val = 0 if row[0] else 1
    c.execute("UPDATE signals SET entry_open=? WHERE id=?", (new_val, signal_id))
    conn.commit()
    conn.close()
    return new_val


def delete_signal(signal_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM signals WHERE id=?", (signal_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# SEC-02: فیلدهای «محتوای پولی» یه سیگنال VIP — چیزی که پی‌وال واقعاً باید
# مخفی نگه داره. فیلدهای متا (نتیجه، owner، وضعیت) عمداً بیرون این لیست‌ان
# چون برای آمار کالر/preview قفل‌شده لازمن، نه محتوای قابل‌فروش.
_VIP_GATED_FIELDS = [
    "coin", "direction", "note", "hashtag", "thesis", "hold_period",
    "before_img", "after_img", "buy_link", "contract_address", "dex_type",
]


def _viewer_has_vip_access(viewer, owner_telegram_id) -> bool:
    if viewer and viewer.get("role") in ("admin", "caller", "subscriber", "community"):
        return True
    return bool(viewer) and owner_telegram_id is not None and owner_telegram_id == viewer.get("telegram_id")


def get_feed(limit: int = 200, viewer=None):
    """معادل sb.from('signals_feed').select('*').order('created_at', desc) —
    شامل caller (نام نمایشی) و history (آرایه‌ی نتایج قبلی).
    ⚠️ owner_first_name/owner_username تو این اسکیما denormalize نشدن (برخلاف
    signals_feed قدیمی Postgres) — برای سیگنال‌هایی که caller_name صریح
    ندارن ولی owner_telegram_id دارن، از آخرین session همون کاربر (اگه
    باشه) اسم نمایشی می‌گیریم؛ وگرنه خودِ کلاینت (rowToSignalObj) به
    'ناشناس' fallback می‌کنه — رفتار قبلی حفظ می‌شه، فقط با یه منبع دیگه.

    ⚠️ SEC-02: قبلاً این تابع همیشه همه‌ی فیلدهای همه‌ی سیگنال‌ها (حتی VIP) رو
    برمی‌گردوند و کل پی‌وال فقط سمت کلاینت (renderSignals) اجرا می‌شد — یعنی
    با یه curl ساده کل محتوای پولی رایگان دیده می‌شد. حالا viewer (session، اگه
    باشه) پاس داده می‌شه: برای سیگنال‌های tier='vip' که viewer بهشون دسترسی
    نداره، _VIP_GATED_FIELDS خالی می‌شن و row["locked"]=True ست می‌شه — ردیف
    کامل حذف نمی‌شه (برای این‌که شمارش «۳ تای رایگان» و آمار کالر هنوز درست
    کار کنن)."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """SELECT id, source, bot_signal_id, owner_telegram_id, caller_name, channel, coin,
                  direction, tier, entry_open, review_status, outcome_status, result, note,
                  hashtag, hold_period, thesis, rating, before_img, after_img, buy_link,
                  contract_address, dex_type, created_at
           FROM signals ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    )
    cols = [d[0] for d in c.description]
    rows = [dict(zip(cols, r)) for r in c.fetchall()]
    for row in rows:
        if not row["caller_name"] and row["owner_telegram_id"]:
            c.execute(
                "SELECT username, first_name FROM sessions WHERE telegram_id=? ORDER BY created_at DESC LIMIT 1",
                (row["owner_telegram_id"],),
            )
            sess = c.fetchone()
            if sess:
                row["owner_username"], row["owner_first_name"] = sess[0], sess[1]
        c.execute(
            "SELECT result, outcome_status, changed_at FROM signal_result_history WHERE signal_id=? ORDER BY changed_at",
            (row["id"],),
        )
        row["history"] = [{"result": r[0], "outcome_status": r[1], "changed_at": r[2]} for r in c.fetchall()]
        if row["tier"] == "vip" and not _viewer_has_vip_access(viewer, row["owner_telegram_id"]):
            for f in _VIP_GATED_FIELDS:
                row[f] = None
            row["locked"] = True
    conn.close()
    return rows
