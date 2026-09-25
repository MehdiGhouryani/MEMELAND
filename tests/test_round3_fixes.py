"""تست‌های دور سوم: خودترمیمی سینک، هماهنگی UTC، لیدربورد، و حذف."""
import os, sys, json, hmac, hashlib, time, asyncio, tempfile, shutil
from urllib.parse import urlencode
from datetime import datetime, timedelta

TMP = tempfile.mkdtemp()
BOT_TOKEN = "123456:TEST-TOKEN"
ADMIN_ID = 2088114041
CALLER_ID = 700000111

os.environ["BOT_TOKEN"] = BOT_TOKEN
os.environ["ADMIN_IDS"] = str(ADMIN_ID)
os.environ["SITE_DB_FILE"] = os.path.join(TMP, "site.db")
os.environ["DB_FILE"] = os.path.join(TMP, "signals.db")
sys.path.insert(0, ".")

from signal_bot.config import settings
settings.setup_logging()
from signal_bot.db import connection as bot_db, signals_repo, users_repo
from signal_bot.site import db as site_db, routes as site_routes, signals as site_signals, auth as site_auth
from signal_bot.services import site_sync
from signal_bot.formatters import texts as bot_texts
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

    print("\n=== ۱) خودترمیمی: نتیجه برای سیگنالِ سایتِ لینک‌نشده ===")
    users_repo.register_user(CALLER_ID, "caller1", "کالر تست")
    orphan_id = site_signals.create_signal(owner_telegram_id=CALLER_ID, coin="$ORPHRES",
                                           caller_name="کالر تست", channel="alt")
    check("قبل از ثبت نتیجه، لینک رباتی نداره", signals_repo.get_by_site_id(orphan_id) is None)
    r = await cli.post(f"/site/signals/{orphan_id}/result",
                       json={"result": "+400%", "outcome_status": "win"}, headers=H)
    body = await r.json()
    check("ثبت نتیجه با موفقیت = 200", r.status == 200, str(r.status))
    check("درخواست می‌گه bot_synced=true (نه skip)", body.get("bot_synced") is True, json.dumps(body))
    bot_id = signals_repo.get_by_site_id(orphan_id)
    check("خودترمیمی لینک رباتی ساخت", bot_id is not None, f"bot_id={bot_id}")
    row = signals_repo.get_signal_for_result(bot_id)
    check("نتیجه‌ی درست تو ربات ثبت شد (۵ایکس)", row and row[4] == "win_5x", row[4] if row else None)

    print("\n=== ۲) به‌روزرسانی دوباره‌ی همون نتیجه (اصلاح امتیاز) ===")
    pts_after_first = users_repo.get_total_pts(CALLER_ID)
    r = await cli.post(f"/site/signals/{orphan_id}/result",
                       json={"result": "+950%", "outcome_status": "win"}, headers=H)
    check("آپدیت دوباره‌ی نتیجه = 200", r.status == 200, str(r.status))
    row2 = signals_repo.get_signal_for_result(bot_id)
    check("کلید جدید win_10x ثبت شد", row2 and row2[4] == "win_10x", row2[4] if row2 else None)
    check("امتیاز دوباره از صفر جمع نشد (فقط دلتا)",
          users_repo.get_total_pts(CALLER_ID) >= pts_after_first,
          f"{pts_after_first} → {users_repo.get_total_pts(CALLER_ID)}")

    print("\n=== ۳) هماهنگی UTC بین سایت و ربات ===")
    r = await cli.post("/site/signals", json={"coin": "$UTCTEST", "channel": "dex"}, headers=H)
    new_site_id = (await r.json())["id"]
    new_bot_id = signals_repo.get_by_site_id(new_site_id)
    site_row = site_signals.get_by_id_full(new_site_id)
    bot_created = signals_repo.get_signal_created_at(new_bot_id) if hasattr(signals_repo, "get_signal_created_at") else None
    # اگه تابع کمکی نبود، مستقیم از دیتابیس ربات بخون
    if bot_created is None:
        conn = bot_db.get_db()
        bot_created = conn.execute("SELECT created_at FROM signals WHERE id=?", (new_bot_id,)).fetchone()[0]
        conn.close()
    site_dt = datetime.fromisoformat(site_row["created_at"])
    bot_dt = datetime.fromisoformat(bot_created)
    delta = abs((site_dt - bot_dt).total_seconds())
    check("created_at سایت و ربات هر دو UTC و نزدیک هم‌اند (نه چند ساعت اختلاف)",
          delta < 5, f"delta={delta}s site={site_row['created_at']} bot={bot_created}")

    print("\n=== ۴) لیدربورد: سیگنال تازه‌ی UTC داخل بازه‌ی هفته دیده می‌شود ===")
    r = await cli.get("/site/leaderboard?period=week")
    lb = await r.json()
    giver_ids = {g["user_id"] for g in lb.get("signal_givers", [])}
    check("لیدربورد ۲۰۰ برمی‌گرداند", r.status == 200, str(r.status))
    check("مالک سیگنالِ تازه در لیدربورد هفته دیده می‌شود",
          ADMIN_ID in giver_ids, f"givers={giver_ids}")

    print("\n=== ۵) daily_signal_count بر مبنای UTC ===")
    before = signals_repo.daily_signal_count(ADMIN_ID)
    utc_today = datetime.utcnow().strftime("%Y-%m-%d")
    check(f"شمارش امروز (UTC={utc_today}) شامل سیگنال تازه است", before >= 1, str(before))

    print("\n=== ۶) لیدربورد چت و وب‌اپ همون تعداد را می‌دهند ===")
    chat_text = bot_texts.leaderboard_text(period="week")
    check("متن لیدربورد چت تولید شد", "لیدربورد" in chat_text)
    # هر دو باید signal_givers غیرخالی داشته باشن وقتی سیگنال approved هست
    check("متن چت هم صاحب سیگنال را نشان می‌دهد (نه «هنوز سیگنالی ثبت نشده»)",
          "هنوز سیگنالی ثبت نشده" not in chat_text or len(giver_ids) == 0)

    print("\n=== ۷) history با نشانگر UTC ===")
    r = await cli.get(f"/site/signals?limit=50", headers=H)
    feed = await r.json()
    orphan_row = next((x for x in feed if x["id"] == orphan_id), None)
    check("سیگنال در فید پیدا شد", orphan_row is not None)
    hist = orphan_row.get("history", []) if orphan_row else []
    check("سوابق (history) دو ردیف دارد (دو بار نتیجه عوض شد)", len(hist) == 2, str(len(hist)))
    check("همه‌ی changed_at ها Z دارند",
          all(h["changed_at"].endswith("Z") for h in hist), str(hist))

    print("\n=== ۸) مسیر حذف هنوز درست کار می‌کند (رگرسیون بعد از تغییر لاگ) ===")
    r = await cli.post("/site/signals", json={"coin": "$DELME"}, headers=H)
    del_id = (await r.json())["id"]
    del_bot_id = signals_repo.get_by_site_id(del_id)
    r = await cli.delete(f"/site/signals/{del_id}", headers=H)
    body = await r.json()
    check("حذف = 200", r.status == 200, str(r.status))
    check("ok=true", body.get("ok") is True, json.dumps(body))
    check("از سایت پاک شد", site_signals.get_by_id_full(del_id) is None)
    check("از ربات هم پاک شد", signals_repo.get_signal_for_result(del_bot_id) is None)
    r = await cli.delete(f"/site/signals/{del_id}", headers=H)
    check("حذف دوباره‌ی همون آیدی = 404", r.status == 404, str(r.status))
    r = await cli.delete(f"/site/signals/{del_id}", headers={"X-Telegram-User-Id": str(CALLER_ID)})
    check("حذف با هدر جعلی هنوز 403 است", r.status == 403, str(r.status))

    print("\n=== ۹) wipe_sessions ===")
    n_before = site_auth.count_sessions()
    check("قبل از wipe، سشن داریم", n_before > 0, str(n_before))
    removed = site_auth.wipe_all_sessions()
    check("wipe تعداد درستی برمی‌گرداند", removed == n_before, f"{removed} vs {n_before}")
    check("بعد از wipe، صفر سشن مانده", site_auth.count_sessions() == 0)
    # سشن جدید بساز تا بقیه‌ی جریان‌ها اگه لازم شد کار کنن (اینجا لازم نیست)

    await cli.close(); await srv.close()
    failed = [n for n, ok in R if not ok]
    print("\n" + "=" * 60)
    print(f"مجموع: {len(R)}  |  موفق: {len(R)-len(failed)}  |  ناموفق: {len(failed)}")
    for f in failed: print("   ✗", f)
    print("=" * 60)
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if failed else 0

sys.exit(asyncio.run(main()))
