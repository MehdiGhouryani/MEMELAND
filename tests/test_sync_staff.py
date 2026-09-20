"""تست سینک دوطرفه‌ی سیگنال‌ها و فهرست یکپارچه‌ی کادر."""
import os, sys, json, hmac, hashlib, time, asyncio, tempfile, shutil
from urllib.parse import urlencode

TMP = tempfile.mkdtemp()
BOT_TOKEN = "123456:TEST-TOKEN"
ADMIN_ID = 2088114041
HELPER_ID = 555000111
TRADER_ID = 444000222
BOTUSER_ID = 333000333

os.environ["BOT_TOKEN"] = BOT_TOKEN
os.environ["ADMIN_IDS"] = str(ADMIN_ID)
os.environ["SITE_DB_FILE"] = os.path.join(TMP, "site.db")
os.environ["DB_FILE"] = os.path.join(TMP, "signals.db")
sys.path.insert(0, ".")

from signal_bot.config import settings
settings.setup_logging()
from signal_bot.db import connection as bot_db, signals_repo, users_repo, staff_repo
from signal_bot.site import db as site_db, routes as site_routes, signals as site_signals, auth as site_auth
from signal_bot.services import site_sync
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient

bot_db.init_db(); site_db.init_db()

def init_data(uid, name="Mehdi"):
    user = json.dumps({"id": uid, "first_name": name, "username": "mehdi"}, separators=(",", ":"))
    f = {"auth_date": str(int(time.time())), "query_id": "AAA", "user": user}
    check = "\n".join(f"{k}={f[k]}" for k in sorted(f))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    f["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(f)

R = []
def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))

async def main():
    app = web.Application(client_max_size=10*1024*1024)
    site_routes.register(app)
    srv = TestServer(app); await srv.start_server()
    cli = TestClient(srv); await cli.start_server()

    r = await cli.post("/site/auth", json={"init_data": init_data(ADMIN_ID)})
    tok = (await r.json())["token"]
    H = {"Authorization": f"Bearer {tok}"}

    print("\n=== ۱) سیگنال ساخته‌شده در وب‌اپ → دیتابیس ربات ===")
    r = await cli.post("/site/signals", json={"coin": "$WEBAPP", "channel": "dex",
                                              "note": "از وب‌اپ", "direction": "LONG"}, headers=H)
    body = await r.json()
    site_id = body["id"]
    check("ساخت سیگنال = 200", r.status == 200, str(r.status))
    check("سرور می‌گوید به ربات سینک شد", body.get("bot_synced") is True, json.dumps(body))
    bot_id = signals_repo.get_by_site_id(site_id)
    check("ردیف متناظر در دیتابیس ربات ساخته شد", bot_id is not None, f"bot_id={bot_id}")
    feed = signals_repo.get_public_feed(limit=20)
    check("در فید عمومی ربات دیده می‌شود", any(r_[5] == "$WEBAPP" for r_ in feed),
          f"{len(feed)} ردیف")
    check("ردیف users برای مالک ساخته شد (وگرنه JOIN حذفش می‌کرد)",
          users_repo.find_by_id(ADMIN_ID) is not None)
    check("لینک معکوس در سایت ست شد",
          site_signals.get_id_by_bot_signal_id(bot_id) == site_id)

    print("\n=== ۲) نتیجه از وب‌اپ → امتیاز در ربات ===")
    pts_before = users_repo.get_total_pts(ADMIN_ID)
    r = await cli.post(f"/site/signals/{site_id}/result",
                       json={"result": "+240%", "outcome_status": "win"}, headers=H)
    check("ثبت نتیجه = 200", r.status == 200, str(r.status))
    row = signals_repo.get_signal_for_result(bot_id)
    check("نتیجه در ربات ثبت شد", row and row[4] == "win_2x", f"result={row[4] if row else None}")
    check("امتیاز کاربر در ربات اضافه شد", users_repo.get_total_pts(ADMIN_ID) > pts_before,
          f"{pts_before} → {users_repo.get_total_pts(ADMIN_ID)}")

    print("\n=== ۳) نگاشت متن نتیجه → کلید امتیاز ربات ===")
    cases = [("+900%", "win", "win_10x"), ("+400%", "win", "win_5x"), ("+150%", "win", "win_2x"),
             ("+30%", "win", "win_sl"), ("10x", "win", "win_10x"), ("", "win", "win_sl"),
             ("", "loss", "loss"), ("هرچیز", "open", "open")]
    for text, status, expected in cases:
        got = site_sync.site_result_to_bot_key(text, status)
        check(f"'{text or '—'}' + {status} → {expected}", got == expected, got)

    print("\n=== ۴) سیگنال قدیمیِ ربات → backfill به سایت ===")
    users_repo.register_user(BOTUSER_ID, "olduser", "کاربر قدیمی")
    old_id = signals_repo.insert_signal(BOTUSER_ID, "$OLDBOT", channel="alt", description="قدیمی")
    signals_repo.set_signal_status(old_id, "approved")
    before = site_signals.count_all()
    st = await site_sync.reconcile(dry_run=True)
    check("dry-run چیزی نمی‌نویسد", site_signals.count_all() == before, str(site_signals.count_all()))
    check("dry-run مورد گم‌شده را می‌شمارد", st["bot_to_site"] >= 1, json.dumps(st))
    st = await site_sync.reconcile()
    check("backfill سیگنال قدیمی را به سایت برد", site_signals.count_all() > before,
          f"{before} → {site_signals.count_all()}")
    r = await cli.get("/site/signals?limit=200", headers=H)
    coins = [x.get("coin") for x in await r.json()]
    check("سیگنال قدیمیِ ربات در فید وب‌اپ دیده می‌شود", "$OLDBOT" in coins, str(coins))

    print("\n=== ۵) سیگنال قدیمیِ سایت (بدون لینک) → backfill به ربات ===")
    orphan = site_signals.create_signal(owner_telegram_id=TRADER_ID, coin="$ORPHAN",
                                        caller_name="یتیم", channel="alt")
    check("قبل از backfill در ربات نیست", signals_repo.get_by_site_id(orphan) is None)
    st = await site_sync.reconcile()
    check("backfill آن را به ربات برد", signals_repo.get_by_site_id(orphan) is not None,
          json.dumps(st))
    check("بعد از backfill همه‌چیز همگام است", site_sync.sync_health().get("in_sync") is True,
          json.dumps(site_sync.sync_health()))
    st2 = await site_sync.reconcile()
    check("اجرای دوباره چیزی تکراری نمی‌سازد (idempotent)",
          st2["bot_to_site"] == 0 and st2["site_to_bot"] == 0, json.dumps(st2))

    print("\n=== ۶) حذف از وب‌اپ → حذف از ربات ===")
    r = await cli.post("/site/signals", json={"coin": "$TEMP"}, headers=H)
    tmp_id = (await r.json())["id"]
    tmp_bot = signals_repo.get_by_site_id(tmp_id)
    check("ساخته و سینک شد", tmp_bot is not None)
    await cli.delete(f"/site/signals/{tmp_id}", headers=H)
    check("از ربات هم حذف شد", signals_repo.get_signal_for_result(tmp_bot) is None)

    print("\n=== ۷) فهرست کادر ===")
    r = await cli.get("/site/staff", headers=H)
    staff = await r.json()
    ids = {x["user_id"] for x in staff}
    check("سوپرادمینِ .env در لیست هست", ADMIN_ID in ids, str(sorted(ids)))
    check("علامت is_super خورده", any(x["user_id"] == ADMIN_ID and x["is_super"] for x in staff))

    staff_repo.add_vip_helper(HELPER_ID, added_by=ADMIN_ID)
    users_repo.register_user(HELPER_ID, "helperguy", "دستیار تست")
    r = await cli.get("/site/staff", headers=H)
    staff = await r.json()
    helper = next((x for x in staff if x["user_id"] == HELPER_ID), None)
    check("دستیارِ اضافه‌شده از داخل ربات دیده می‌شود", helper is not None)
    check("نام واقعی‌اش از جدول users ربات خوانده شد",
          helper and helper["first_name"] == "دستیار تست", helper and helper["first_name"])
    check("یوزرنیمش هم", helper and helper["username"] == "@helperguy", helper and helper["username"])

    print("\n=== ۸) اعطای نقش از وب‌اپ ===")
    users_repo.register_user(TRADER_ID, "traderguy", "تریدر تست")
    r = await cli.post("/site/staff", json={"user_id": TRADER_ID, "role": "alpha"}, headers=H)
    check("اعطای نقش تریدر = 200", r.status == 200, str(r.status))
    row = users_repo.find_by_id(TRADER_ID)
    check("در users دیتابیس ربات ذخیره شد", row and row[5] == "alpha", row and row[5])
    q = site_auth.get_user_role_and_quota(TRADER_ID)
    check("سقف سهمیه‌اش هم عوض شد", q["daily_limit"] == settings.ROLE_DAILY_LIMITS["alpha"],
          f"limit={q['daily_limit']}")
    r = await cli.get("/site/staff", headers=H)
    staff = await r.json()
    check("در تب تریدرهای ویژه دیده می‌شود",
          any(x["user_id"] == TRADER_ID and x["role"] == "alpha" for x in staff))

    r = await cli.post("/site/staff", json={"user_id": HELPER_ID, "role": "admin"}, headers=H)
    check("ارتقا به ادمین = 200", r.status == 200, str(r.status))
    check("ربات هم او را ادمین می‌بیند", site_auth._is_staff_admin(HELPER_ID) is True)
    check("staff_repo ربات هم ردیف دارد", staff_repo.is_vip_helper(HELPER_ID) is False,
          "نقش به admin تغییر کرد نه vip_helper")

    print("\n=== ۹) سلب دسترسی ===")
    r = await cli.delete(f"/site/staff/{HELPER_ID}", headers=H)
    check("حذف = 200", r.status == 200, str(r.status))
    check("دیگر ادمین نیست", site_auth._is_staff_admin(HELPER_ID) is False)
    r = await cli.delete(f"/site/staff/{ADMIN_ID}", headers=H)
    check("سوپرادمین .env حذف نمی‌شود", r.status == 400, str(r.status))

    print("\n=== ۱۰) created_at با نشانگر UTC ===")
    r = await cli.get("/site/signals?limit=5", headers=H)
    rows = await r.json()
    check("همه‌ی created_at ها Z دارند",
          all(str(x.get("created_at", "")).endswith("Z") for x in rows),
          str([x.get("created_at") for x in rows][:2]))

    await cli.close(); await srv.close()
    failed = [n for n, ok in R if not ok]
    print("\n" + "=" * 60)
    print(f"مجموع: {len(R)}  |  موفق: {len(R)-len(failed)}  |  ناموفق: {len(failed)}")
    for f in failed: print("   ✗", f)
    print("=" * 60)
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if failed else 0

sys.exit(asyncio.run(main()))
