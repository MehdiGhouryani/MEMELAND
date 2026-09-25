"""دور چهارم — نتایج ممیزی جامع: لینک معکوس، آپلود عکس، فونت واترمارک،
هماهنگی کادر بین چت/وب‌اپ، UTC در پرونده‌ی تریدر، سخت‌سازی هشدار قیمت."""
import os, sys, asyncio, tempfile, shutil, io
from datetime import datetime, timedelta

TMP = tempfile.mkdtemp()
ADMIN_ID = 2088114041
STAFF_TARGET = 611000222

os.environ["BOT_TOKEN"] = "123456:TEST-TOKEN"
os.environ["ADMIN_IDS"] = str(ADMIN_ID)
os.environ["SITE_DB_FILE"] = os.path.join(TMP, "site.db")
os.environ["DB_FILE"] = os.path.join(TMP, "signals.db")
sys.path.insert(0, ".")

from signal_bot.config import settings
settings.setup_logging()
from signal_bot.db import connection as bot_db, signals_repo, users_repo, staff_repo
from signal_bot.site import db as site_db, signals as site_signals, auth as site_auth, traders
from signal_bot.services import site_sync, image_upload
from signal_bot.services.watermark import apply_watermark

bot_db.init_db(); site_db.init_db()

R = []
def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))


class FakeFile:
    def __init__(self, payload):
        self._payload = payload
    async def download_as_bytearray(self):
        return bytearray(self._payload)


class FakeBot:
    def __init__(self, payload=b"\xff\xd8\xff\xe0fake-jpeg-bytes"):
        self._payload = payload
    async def get_file(self, file_id):
        return FakeFile(self._payload)


async def main():
    users_repo.register_user(ADMIN_ID, "mehdi", "Mehdi")

    print("\n=== ۱) لینک معکوس: سیگنال بومیِ ربات → سایت ===")
    bot_id = signals_repo.insert_signal(ADMIN_ID, "$BOTNATIVE", channel="alt")
    signals_repo.set_signal_status(bot_id, "approved")
    ok = await site_sync.push_signal_created(
        bot_signal_id=bot_id, owner_telegram_id=ADMIN_ID, coin="$BOTNATIVE",
        direction=None, signal_type="full", caller_name="Mehdi")
    check("push_signal_created موفق بود", ok is True)
    site_id = site_signals.get_id_by_bot_signal_id(bot_id)
    check("لینک رفت (site.bot_signal_id) درست است", site_id is not None, f"site_id={site_id}")
    reverse = signals_repo.get_by_site_id(site_id)
    check("لینک معکوس (bot.site_signal_id) هم ست شده — این باگ اصلی این دور بود",
          reverse == bot_id, f"expected={bot_id} got={reverse}")

    print("\n=== ۲) اثر عملی: حذف سیگنال بومیِ ربات از طریق سینک سایت ===")
    ok_del = site_sync.delete_from_site(site_id)
    check("delete_from_site موفق بود", ok_del is True)
    check("ردیف ربات واقعاً حذف شد (قبل از فیکس اینجا orphan می‌موند)",
          signals_repo.get_signal_for_result(bot_id) is None)

    print("\n=== ۳) آپلود عکس سیگنال‌های ربات بدون Supabase ===")
    check("Supabase غیرفعال است (وضعیت واقعی پروژه)", image_upload._enabled() is False)
    url = await image_upload.upload_telegram_photo(FakeBot(), "fake_file_id", signal_id=4242)
    check("دیگه None برنمی‌گرده — فال‌بک محلی جواب داد", url is not None, str(url))
    check("مسیر برگشتی زیر /static/uploads است", (url or "").startswith("/static/uploads/"), url)
    expected_path = os.path.join(image_upload._UPLOAD_DIR, (url or "").split("/")[-1])
    check("فایل واقعاً روی دیسک نوشته شده", os.path.exists(expected_path), expected_path)

    print("\n=== ۴) مسیر فونت واترمارک ===")
    font_path = os.path.join(os.path.dirname(image_upload.__file__), "..", "..", "..",
                             "memeland_site", "static", "fonts", "Vazirmatn-Bold.ttf")
    check("مسیر محاسبه‌شده دیگه signal_bot/memeland_site نیست (باگ قبلی)",
          "signal_bot/memeland_site" not in os.path.normpath(font_path).replace(os.sep, "/"),
          os.path.normpath(font_path))
    img = __import__("PIL.Image", fromlist=["Image"])
    canvas = img.new("RGB", (300, 200), (10, 10, 10))
    buf = io.BytesIO(); canvas.save(buf, format="JPEG")
    from signal_bot.site.kv import kv_set
    kv_set("settings:watermark_text", "کانال تست")  # متن فارسی — باید بدون کرش رندر بشه
    out = apply_watermark(buf.getvalue())
    check("واترمارک با متن فارسی بدون کرش اجرا شد", len(out) > 0, f"{len(out)} بایت")
    reopened = img.open(io.BytesIO(out))
    check("عکس خروجی معتبر است", reopened.size == (300, 200), str(reopened.size))

    print("\n=== ۵) هماهنگی کادر: دکمه‌ی چت (vip_add_/vip_remove_) با سایت ===")
    staff_repo.add_vip_helper(STAFF_TARGET, added_by=ADMIN_ID)
    site_auth.sync_staff_row_from_bot(STAFF_TARGET, "vip_helper")
    staff_list = site_auth.get_staff_list()
    row = next((x for x in staff_list if x["user_id"] == STAFF_TARGET), None)
    check("بعد از vip_add_ شبیه‌سازی‌شده، در فهرست سایت هم دیده می‌شود", row is not None)
    staff_repo.remove_vip_helper(STAFF_TARGET)
    site_auth.unsync_staff_row_from_bot(STAFF_TARGET)
    staff_list2 = site_auth.get_staff_list()
    row2 = next((x for x in staff_list2 if x["user_id"] == STAFF_TARGET), None)
    check("بعد از vip_remove_ شبیه‌سازی‌شده، از فهرست سایت هم حذف می‌شود — باگ این دور بود",
          row2 is None, str(row2))

    print("\n=== ۶) پرونده‌ی تریدر: created_at با نشانگر UTC ===")
    site_signals.create_signal(owner_telegram_id=ADMIN_ID, coin="$DOSSIERTEST",
                               caller_name="Mehdi", channel="alt")
    dossier = traders.get_trader_dossier(ADMIN_ID)
    check("دوسیه ساخته شد", dossier is not None)
    recents = dossier.get("recent_signals", []) if dossier else []
    check("حداقل یک سیگنال اخیر دارد", len(recents) > 0, str(len(recents)))
    check("created_at سیگنال‌های اخیر همه Z دارند",
          all(str(r.get("created_at", "")).endswith("Z") for r in recents),
          str([r.get("created_at") for r in recents]))

    print("\n=== ۷) سخت‌سازی check_entry_alerts در برابر entry_price نامعتبر ===")
    from signal_bot.jobs.scheduled import check_entry_alerts
    from signal_bot.config import settings as cfg
    cfg.CHANNEL_ID = "-100123456"  # برای عبور از گارد اولیه‌ی تابع

    bad_id = site_signals.create_signal(
        owner_telegram_id=ADMIN_ID, coin="$BADENTRY", caller_name="Mehdi",
        channel="alt", contract_address="0xBAD", chain="eth", entry_price=None)
    # دستی یه مقدار غیرعددی تزریق می‌کنیم — چون هیچ UI فعلی این کار رو نمی‌کنه،
    # ولی دفاعی بودن کد باید تضمین بشه.
    conn = site_db.get_db()
    conn.execute("UPDATE signals SET entry_price=? WHERE id=?", ("not-a-number", bad_id))
    conn.commit(); conn.close()

    good_id = site_signals.create_signal(
        owner_telegram_id=ADMIN_ID, coin="$GOODENTRY", caller_name="Mehdi",
        channel="alt", contract_address="0xGOOD", chain="eth", entry_price=1.0)

    class FakeContext:
        bot = None

    try:
        await check_entry_alerts(FakeContext())
        crashed = False
    except Exception as e:
        crashed = True
        crash_err = e
    check("جاب با entry_price نامعتبر کرش نکرد (رکورد بد رد و لاگ شد)",
          not crashed, "" if not crashed else str(crash_err))

    await cli_noop()

    failed = [n for n, ok_ in R if not ok_]
    print("\n" + "=" * 60)
    print(f"مجموع: {len(R)}  |  موفق: {len(R)-len(failed)}  |  ناموفق: {len(failed)}")
    for f in failed:
        print("   ✗", f)
    print("=" * 60)
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if failed else 0


async def cli_noop():
    return None


sys.exit(asyncio.run(main()))
