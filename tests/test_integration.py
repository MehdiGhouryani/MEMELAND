import os, sys, json, hmac, hashlib, time, asyncio, tempfile, shutil
from urllib.parse import urlencode

TMP = tempfile.mkdtemp()
BOT_TOKEN = "123456:TEST-TOKEN-FOR-LOCAL-VERIFICATION"
ADMIN_ID = 2088114041
STRANGER_ID = 999000111

os.environ["BOT_TOKEN"] = BOT_TOKEN
os.environ["ADMIN_IDS"] = f'"{ADMIN_ID}" , 777'
os.environ["SITE_DB_FILE"] = os.path.join(TMP, "site.db")
os.environ["DB_FILE"] = os.path.join(TMP, "signals.db")
sys.path.insert(0, ".")

from signal_bot.config import settings
settings.setup_logging()
from signal_bot.db import connection as bot_db
from signal_bot.site import db as site_db, routes as site_routes, signals as site_signals, auth as site_auth
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient

bot_db.init_db(); site_db.init_db()

def make_init_data(uid, name="Mehdi", token=BOT_TOKEN, auth_date=None):
    user = json.dumps({"id": uid, "first_name": name, "username": "mehdi"}, separators=(",", ":"))
    fields = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAA", "user": user}
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   [{detail}]" if detail else ""))

async def main():
    app = web.Application(client_max_size=10*1024*1024)
    site_routes.register(app)
    server = TestServer(app); await server.start_server()
    cli = TestClient(server); await cli.start_server()

    print("\n=== 1) احراز هویت با initData معتبر (ادمین) ===")
    r = await cli.post("/site/auth", json={"init_data": make_init_data(ADMIN_ID)})
    a = await r.json()
    check("auth 200", r.status == 200, str(r.status))
    check("ادمین شناخته شد", a.get("is_admin") is True, f"is_admin={a.get('is_admin')}")
    check("توکن صادر شد", bool(a.get("token")))
    check("quota.is_admin درست", a.get("quota", {}).get("is_admin") is True)
    admin_token = a.get("token")

    print("\n=== 2) استفاده‌ی مجدد از سشن (نشت جدول sessions) ===")
    n0 = site_auth.count_sessions()
    for _ in range(5):
        await cli.post("/site/auth", json={"init_data": make_init_data(ADMIN_ID)})
    n1 = site_auth.count_sessions()
    check("۵ لاگین ⇒ سشن جدید نساخت", n1 == n0, f"{n0} -> {n1}")

    print("\n=== 3) مسیر تأییدنشده: ارتقای دسترسی بسته شده ===")
    h = {"X-Telegram-User-Id": str(ADMIN_ID)}
    r = await cli.get("/site/session", headers=h)
    u = await r.json()
    check("is_admin سطح بالا False", u.get("is_admin") is False)
    check("quota.is_admin هم False (نشت بسته شد)", u.get("quota", {}).get("is_admin") is False,
          f"quota.is_admin={u.get('quota',{}).get('is_admin')}")
    check("display_role لو نمی‌ده", "Admin" not in str(u.get("quota", {}).get("display_role")),
          str(u.get("quota", {}).get("display_role")))
    check("هیچ توکنی صادر نشد", not u.get("token"), f"token={u.get('token')}")
    n2 = site_auth.count_sessions()
    check("ردیف سشن جدید ساخته نشد", n2 == n1, f"{n1} -> {n2}")

    print("\n=== 4) initData جعلی رد می‌شود ===")
    bad = make_init_data(ADMIN_ID, token="999:WRONG")
    r = await cli.post("/site/auth", json={"init_data": bad})
    b = await r.json()
    check("امضای نامعتبر ⇒ ادمین نه", not b.get("is_admin"), json.dumps(b)[:90])

    print("\n=== 5) دسترسی ادمین با توکن معتبر ===")
    r = await cli.get("/site/staff", headers={"Authorization": f"Bearer {admin_token}"})
    check("staff با توکن ادمین = 200", r.status == 200, str(r.status))
    h_forge = {"X-Telegram-User-Id": str(ADMIN_ID)}
    r = await cli.get("/site/staff", headers=h_forge)
    check("[ارتقا] staff با هدر جعلی = 403", r.status == 403, str(r.status))
    r = await cli.delete("/site/signals/1", headers=h_forge)
    check("[ارتقا] حذف سیگنال با هدر جعلی = 403", r.status == 403, str(r.status))
    r = await cli.post("/site/staff", json={"user_id": STRANGER_ID, "role": "admin"}, headers=h_forge)
    check("[ارتقا] افزودن ادمین با هدر جعلی = 403", r.status == 403, str(r.status))
    r = await cli.post("/site/content/articles", json={"title": "x", "body": "y"}, headers=h_forge)
    check("[ارتقا] انتشار محتوا با هدر جعلی = 403", r.status == 403, str(r.status))
    r = await cli.post("/site/signals", json={"coin": "$FAKE", "owner_telegram_id": ADMIN_ID}, headers=h_forge)
    check("[ارتقا] ثبت سیگنال با هدر جعلی = 403", r.status == 403, str(r.status))
    r = await cli.get("/site/staff", headers={"X-Telegram-User-Id": str(STRANGER_ID)})
    check("staff برای غریبه = 403", r.status == 403, str(r.status))
    r = await cli.get("/site/staff", headers={"Authorization": f"Bearer {admin_token}"})
    check("ادمین واقعی هنوز دسترسی دارد", r.status == 200, str(r.status))

    print("\n=== 6) فید سیگنال ===")
    site_signals.create_signal(owner_telegram_id=ADMIN_ID, caller_name="Mehdi", coin="$PEPE",
                               channel="dex", note="test", risk_level="low")
    site_signals.create_signal(owner_telegram_id=ADMIN_ID, caller_name="Mehdi", coin="$VIPX",
                               channel="alt", tier="vip", note="secret", contract_address="0xdead")
    r = await cli.get("/site/signals?limit=200", headers={"Authorization": f"Bearer {admin_token}"})
    feed = await r.json()
    check("فید ادمین ۲ ردیف", len(feed) == 2, f"count={len(feed)}")
    r = await cli.get("/site/signals?limit=200")
    anon = await r.json()
    vip = [x for x in anon if x.get("locked")]
    check("مهمان: سیگنال VIP قفل است", len(vip) == 1 and vip[0].get("note") is None)

    print("\n=== 7) لاگ کلاینت: batch / سطح / تزریق / نرخ ===")
    r = await cli.post("/site/client-log", json={"sid": "abc123", "build": "2026-09-20.1",
        "events": [{"lv": "I", "msg": "[BOOT] modules API=1 Views=1"},
                   {"lv": "E", "msg": "[JSERR] onerror msg=boom"}]})
    check("batch پذیرفته شد", r.status == 200, str(r.status))
    r = await cli.post("/site/client-log", json={"msg": "[APP] legacy format"})
    check("فرمت قدیمی هنوز کار می‌کند", r.status == 200)
    r = await cli.post("/site/client-log", json={"events": [
        {"lv": "I", "msg": "ok\n09-20 20:09:51 [I] FAKE: admin granted"}]})
    check("تزریق خط جعلی خنثی شد", r.status == 200)
    long_msg = "X" * 5000
    await cli.post("/site/client-log", json={"events": [{"lv": "I", "msg": long_msg}]})
    throttled = 0
    for _ in range(14):
        rr = await cli.post("/site/client-log",
                            json={"events": [{"lv": "I", "msg": "spam"} for _ in range(10)]})
        if (await rr.json()).get("throttled"):
            throttled += 1
    check("محدودیت نرخ روی اسپم روتین فعال شد", throttled > 0, f"{throttled}/14 رد شد")
    r = await cli.post("/site/client-log",
                       json={"events": [{"lv": "E", "msg": "[JSERR] critical after spam"}]})
    b2 = await r.json()
    check("خطا حتی بعد از اسپم دور ریخته نمی‌شود", not b2.get("throttled"), json.dumps(b2))

    print("\n=== 8) ورودی‌های بد ⇒ ۴۰۰ نه ۵۰۰ ===")
    r = await cli.post("/site/signals/abc/result", json={"result": "x", "outcome_status": "win"},
                       headers={"Authorization": f"Bearer {admin_token}"})
    check("id غیرعددی ⇒ 400", r.status == 400, str(r.status))
    r = await cli.delete("/site/signals/notanid", headers={"Authorization": f"Bearer {admin_token}"})
    check("delete با id بد ⇒ 400", r.status == 400, str(r.status))
    r = await cli.patch("/site/signals/1", json={"coin": "$NEW", "id": 1, "token": "junk"},
                        headers={"Authorization": f"Bearer {admin_token}"})
    check("ویرایش با فیلد اضافه ⇒ 200 (فیلتر شد)", r.status == 200, str(r.status))

    print("\n=== 9) آپلود بدون احراز هویت ===")
    r = await cli.post("/site/upload", data={"image": b"x"})
    check("آپلود ناشناس ⇒ 401", r.status == 401, str(r.status))

    print("\n=== 10) /site/diag ===")
    r = await cli.get("/site/diag", headers={"Authorization": f"Bearer {admin_token}"})
    d = await r.json()
    check("diag برای ادمین = 200", r.status == 200, str(r.status))
    check("diag آیدی را در ADMIN_IDS می‌بیند", d.get("viewer", {}).get("in_env_admin_ids") is True)
    check("diag تعداد فید را می‌دهد", d.get("server", {}).get("feed_total") == 2, str(d.get("server", {}).get("feed_total")))
    r = await cli.get("/site/diag", headers={"X-Telegram-User-Id": str(STRANGER_ID)})
    check("diag برای غیرادمین = 403", r.status == 403, str(r.status))

    print("\n=== 11) سیستم لاگ یکپارچه ===")
    import logging
    from signal_bot.logger import LOG_FILE, get_recent_logs
    logging.getLogger("some.random.module").warning("ROOT_LOGGER_PROBE")
    from signal_bot.logger import logger as mlogger
    mlogger.info("NAMED_LOGGER_PROBE")
    for h in logging.getLogger().handlers: h.flush()
    txt = open(LOG_FILE, encoding="utf-8").read()
    check("logging.* در فایل هست", "ROOT_LOGGER_PROBE" in txt)
    check("logger.* در فایل هست", "NAMED_LOGGER_PROBE" in txt)
    check("بدون تکرار", txt.count("NAMED_LOGGER_PROBE") == 1, f"count={txt.count('NAMED_LOGGER_PROBE')}")
    check("فیلتر سطح کار می‌کند", "ROOT_LOGGER_PROBE" in get_recent_logs(200, level="W")
          and "NAMED_LOGGER_PROBE" not in get_recent_logs(200, level="W"))
    check("لاگ کلاینت با سطح ERROR ثبت شد", "[E] [JS:abc123] [JSERR]" in txt, "")
    check("خطای بعد از اسپم واقعاً نوشته شد", "critical after spam" in txt)
    check("خط جعلی به‌عنوان خط مستقل ثبت نشد", "\n09-20 20:09:51 [I] FAKE" not in txt)
    check("پیام بلند بریده شد", ("X"*400) not in txt)

    print("\n=== 12) ثبت نتیجه با ادعای جعلی مالکیت ===")
    r = await cli.post("/site/signals/1/result", json={"result": "+900%", "outcome_status": "win"},
                       headers={"X-Telegram-User-Id": str(ADMIN_ID)})
    check("مالکیت جعلی ⇒ 403", r.status == 403, str(r.status))
    r = await cli.post("/site/signals/1/result", json={"result": "+50%", "outcome_status": "win"},
                       headers={"Authorization": f"Bearer {admin_token}"})
    check("مالک واقعی ⇒ 200", r.status == 200, str(r.status))

    print("\n=== 13) خواندن عمومی هنوز باز است ===")
    r = await cli.get("/site/signals?limit=10")
    check("فید مهمان بدون هدر = 200", r.status == 200, str(r.status))
    r = await cli.get("/site/leaderboard")
    check("لیدربورد عمومی = 200", r.status == 200, str(r.status))
    r = await cli.get("/site/content/articles")
    check("مقالات عمومی = 200", r.status == 200, str(r.status))

    await cli.close(); await server.close()

    print("\n" + "="*62)
    failed = [n for n, ok_, _ in results if not ok_]
    print(f"مجموع: {len(results)}  |  موفق: {len(results)-len(failed)}  |  ناموفق: {len(failed)}")
    if failed:
        for f in failed: print("   ✗", f)
    print("="*62)
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if failed else 0

sys.exit(asyncio.run(main()))
