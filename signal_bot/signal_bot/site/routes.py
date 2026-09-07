"""
مسیرهای HTTP سایت — همه‌شون رو همون aiohttp اپلیکیشن بات ثبت می‌شن
(web/ipn_server.py صداشون می‌زنه). شامل: سرو کردن خودِ HTML، احراز هویت،
CRUD سیگنال‌ها.

⚠️ این لایه مسئول چک مجوزه (کدوم اکشن به session/role نیاز داره) — ماژول‌های
site/auth.py و site/signals.py خودشون هیچ چکی نمی‌کنن، فرض می‌کنن قبلاً اینجا
چک شده. الگوی مجوز: هدر Authorization: Bearer <token> → get_session(token) →
اگه role نداشت یا None بود، 401/403.
"""
import base64
import json
import os
import uuid

from aiohttp import web

from signal_bot.services import image_upload
from signal_bot.site import auth, signals, ratings, kv

# مسیر خودِ فایل HTML — کنار پوشه‌ی پروژه‌ی بات قرار می‌گیره (memeland_site/
# sibling با پوشه‌ی بیرونی signal_bot، نه پوشه‌ی پکیج داخلی). چون این فایل
# تو signal_bot/signal_bot/site/ هست (دو تا سطح signal_bot تودرتو: پوشه‌ی
# بیرونی پروژه + پکیج پایتون)، برای رسیدن به ریشه‌ی مشترک ۳ تا .. لازمه، نه
# ۲ تا — با تست مستقیم رو یه ساختار پوشه‌ی واقعی تأیید شد (باگ واقعی بود،
# اول ۲ تا نوشته بودم که ۴۰۴ می‌داد).
_HTML_PATH = os.environ.get(
    "SITE_HTML_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "memeland_site", "memeland-hub_UPDATED.html"),
)


def _json_error(status: int, message: str) -> web.Response:
    return web.json_response({"error": message}, status=status)


def _get_session_from_request(request: web.Request):
    """توکن رو فقط از هدر Authorization: Bearer می‌خونه (SEC-04 — قبلاً
    query string هم قبول می‌شد، حذف شد چون restoreSession دیگه هدر می‌فرسته)."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):]
    return None


def _client_ip(request: web.Request) -> str:
    """برای throttle کاربر ناشناس (SEC-01). اگه پشت reverse proxy دیپلوی شده
    (لازم برای HTTPS واقعی، رجوع کن به Audit AUTH-04)، اولین IP تو
    X-Forwarded-For رو در نظر می‌گیره؛ وگرنه IP مستقیم اتصال. ⚠️ این هدر
    فقط وقتی قابل‌اعتماده که یه proxy واقعی جلوشه و مقدار کلاینت رو بازنویسی
    می‌کنه — پشت اتصال مستقیم (بدون proxy)، قابل جعله."""
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote or "unknown"


async def handle_index(request: web.Request) -> web.Response:
    """خودِ HTML سایت رو سرو می‌کنه — یعنی آدرس سرور بات = آدرس سایت.
    ⚠️ AUTH-01: یوزرنیم بات دیگه تو خودِ HTML دستی ادیت نمی‌شه — از
    TELEGRAM_BOT_USERNAME تو .env (تک منبع، مثل SITE_URL) گرفته و جای
    پلیس‌هولدر جایگزین می‌شه. اگه هنوز ست نشده، پلیس‌هولدر دست‌نخورده
    می‌مونه و renderTelegramWidget() مثل قبل چیزی رندر نمی‌کنه (بدون کرش)."""
    if not os.path.exists(_HTML_PATH):
        return web.Response(status=404, text=f"site html not found at {_HTML_PATH}")
    from signal_bot.config import settings
    with open(_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    if settings.TELEGRAM_BOT_USERNAME:
        html = html.replace("'YOUR_BOT_USERNAME'", f"'{settings.TELEGRAM_BOT_USERNAME}'")
    return web.Response(text=html, content_type="text/html")


async def handle_login_widget(request: web.Request) -> web.Response:
    from signal_bot.config import settings
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    user = auth.verify_login_widget_payload(payload, settings.TOKEN)
    if not user:
        return _json_error(401, "invalid login widget payload")
    token = auth.create_session(user["id"], username=user.get("username"), first_name=user.get("first_name"),
                                 photo_url=user.get("photo_url"))
    return web.json_response({"token": token})


async def handle_session(request: web.Request) -> web.Response:
    session = auth.get_session(_get_session_from_request(request))
    if not session:
        return _json_error(401, "invalid or expired session")
    session = dict(session)
    session["display_name"] = auth.get_profile(session["telegram_id"])["display_name"]
    return web.json_response(session)


async def handle_profile_update(request: web.Request) -> web.Response:
    session = auth.get_session(_get_session_from_request(request))
    if not session:
        return _json_error(401, "invalid or expired session")
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    saved = auth.set_display_name(session["telegram_id"], body.get("display_name", ""))
    return web.json_response({"display_name": saved})


async def handle_claim_role(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    token = body.get("token") or _get_session_from_request(request)
    ok = auth.claim_role(token, body.get("role", ""), body.get("pin", ""))
    return web.json_response({"ok": ok}) if ok else _json_error(401, "invalid pin or session")


async def handle_verify_pin(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    ok = auth.verify_pin(body.get("role", ""), body.get("pin", ""), actor_telegram_id=f"ip:{_client_ip(request)}")
    return web.json_response({"ok": ok})


def _require_admin(request: web.Request):
    """برمی‌گردونه session dict اگه role=='admin' باشه، وگرنه None."""
    token = _get_session_from_request(request)
    session = auth.get_session(token)
    if not session or session.get("role") != "admin":
        return None
    return session


def _require_owner_or_admin(request: web.Request, signal_id: int):
    """برای ثبت نتیجه/toggle entry: صاحبِ خودِ سیگنال یا ادمین — نه فقط ادمین.
    ⚠️ این با چک اولیه‌ی من (فقط ادمین) فرق داره؛ با نگاه‌کردن دقیق به کد
    رندر دکمه‌ها پیدا شد: quickUpdateSignal/toggleEntryWindow برخلاف
    rateSignal/deleteItem اصلاً isAdmin-gated نیستن — دقیقاً همون فلسفه‌ی
    «خودگزارش‌دهی با override ادمین» که خودِ بات هم داره."""
    session = auth.get_session(_get_session_from_request(request))
    if not session:
        return None
    if session.get("role") == "admin":
        return session
    owner = signals.get_owner(signal_id)
    if owner is not None and owner == session["telegram_id"]:
        return session
    return None


async def handle_detect_chain(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "admin only")
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    address = (body.get("contract_address") or "").strip()
    if not address:
        return _json_error(400, "contract_address لازمه")
    from signal_bot.services.price_feed import detect_chain_and_price
    chain, price = await detect_chain_and_price(address)
    return web.json_response({"chain": chain, "price": price})


async def handle_home(request: web.Request) -> web.Response:
    """فاز ۵: لندینگ‌پیج — آمار کلان + بهترین کال‌های اخیر (با masking VIP،
    چون این صفحه عمومیه)."""
    viewer = auth.get_session(_get_session_from_request(request))
    return web.json_response({
        "stats": signals.get_stats(),
        "top_recent_wins": signals.get_top_recent_wins(days=7, limit=5, viewer=viewer),
    })


async def handle_set_caller_tier(request: web.Request) -> web.Response:
    """ادمین می‌تونه هر کالری رو (با telegram_id یا فقط اسم) به یکی از
    ۴ تیر (bronze/silver/gold/diamond) بذاره، یا با tier=null/'' برداره —
    دستیه، نه محاسبه‌ی خودکار از رتبه."""
    session = _require_admin(request)
    if not session:
        return _json_error(403, "admin only")
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    ctid = body.get("caller_telegram_id")
    cname = (body.get("caller_name") or "").strip() or None
    if not ctid and not cname:
        return _json_error(400, "caller_telegram_id یا caller_name لازمه")
    try:
        ratings.set_caller_tier(ctid, cname, body.get("tier") or None, set_by=session["telegram_id"])
    except ValueError as e:
        return _json_error(400, str(e))
    return web.json_response({"ok": True})


async def handle_leaderboard(request: web.Request) -> web.Response:
    """فاز ۳: لیدربورد دوبخشی — کالرها (بر اساس رأی کاربرها، site.db) +
    سیگنال‌دهندگان (بر اساس امتیاز، signals.db خودِ بات). ⚠️ اولین باریه که
    site/routes.py مستقیم از دیتابیس بات می‌خونه — چون بات و سایت هم‌پروسه‌ان
    (site_sync هم قبلاً همین‌جوری مستقیم پایتونی بود)، مشکلی نداره، فقط برای
    اولین‌بار صریح import شده."""
    from datetime import datetime, timedelta
    from signal_bot.db import signals_repo

    period = request.query.get("period", "week")
    if period == "week":
        since = (datetime.now() - timedelta(days=7)).isoformat()
    elif period == "month":
        since = (datetime.now() - timedelta(days=30)).isoformat()
    else:
        since = "2000-01-01"

    signal_giver_rows = signals_repo.get_leaderboard_rows(since, limit=10)
    signal_givers = [
        {"user_id": r[0], "full_name": r[1], "username": r[2], "level": r[3],
         "points": r[4], "count": r[5], "wins": r[6]}
        for r in signal_giver_rows
    ]
    return web.json_response({"callers": ratings.get_top_callers(limit=10), "signal_givers": signal_givers})


async def handle_signals_get(request: web.Request) -> web.Response:
    # ⚠️ فاز ۸: برخلاف قبل، الان دیدن سیگنال‌ها (حتی تیر رایگان) نیاز به لاگین
    # داره — طبق تصمیم صریح: «همه‌ی بخش‌ها در دسترس باشه به‌جز سیگنال‌ها».
    # این جدا از ماسک VIP (SEC-02) هست: اونجا لاگین‌شده‌ی غیرمشترک VIP رو
    # نمی‌بینه؛ اینجا اصلاً بدون لاگین هیچی (حتی رایگان) نمی‌بینه.
    viewer = auth.get_session(_get_session_from_request(request))
    if not viewer:
        return _json_error(401, "برای دیدن سیگنال‌ها باید با تلگرام وارد بشی")
    try:
        limit = min(int(request.query.get("limit", 200)), 200)  # سقف ۲۰۰ — جلوی offset/limit غیرمنطقی
        offset = max(int(request.query.get("offset", 0)), 0)
    except ValueError:
        return _json_error(400, "limit/offset باید عدد باشن")
    status = request.query.get("status") or None
    channel = request.query.get("channel") or None
    q = request.query.get("q") or None
    return web.json_response(signals.get_feed(limit=limit, offset=offset, status=status, channel=channel, q=q, viewer=viewer))


async def handle_signals_create(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "admin only")
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    try:
        sid = signals.create_signal(**{k: v for k, v in body.items() if k in (
            "owner_telegram_id", "caller_name", "channel", "coin", "direction", "tier", "note",
            "hashtag", "before_img", "buy_link", "contract_address", "dex_type", "created_at",
            "chain", "entry_price",
        )})
    except TypeError as e:
        return _json_error(400, str(e))
    return web.json_response({"id": sid})


async def handle_signals_edit(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "admin only")
    signal_id = int(request.match_info["id"])
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    try:
        ok = signals.edit_signal(signal_id, **body)
    except ValueError as e:
        return _json_error(400, str(e))
    return web.json_response({"ok": ok}) if ok else _json_error(404, "signal not found")


async def handle_signals_result(request: web.Request) -> web.Response:
    signal_id = int(request.match_info["id"])
    if not _require_owner_or_admin(request, signal_id):
        return _json_error(403, "فقط صاحبِ سیگنال یا ادمین")
    try:
        body = await request.json()
        ok = signals.set_result(signal_id, body.get("result", ""), body.get("outcome_status", "open"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        return _json_error(400, str(e))
    return web.json_response({"ok": ok}) if ok else _json_error(404, "signal not found")


async def handle_signals_toggle_entry(request: web.Request) -> web.Response:
    signal_id = int(request.match_info["id"])
    if not _require_owner_or_admin(request, signal_id):
        return _json_error(403, "فقط صاحبِ سیگنال یا ادمین")
    new_val = signals.toggle_entry_open(signal_id)
    if new_val is None:
        return _json_error(404, "signal not found")
    return web.json_response({"entry_open": bool(new_val)})


_MAX_IMAGE_BYTES = 6 * 1024 * 1024  # بعد از رسایز/فشرده‌سازی سمت کلاینت خیلی کمتر از اینه؛ این فقط سقفِ دفاعیه
_ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


async def handle_signal_image_upload(request: web.Request) -> web.Response:
    """
    عکس قبل/بعدِ یه سیگنال رو از خودِ سایت آپلود می‌کنه (نه پیست‌کردن لینک).
    ⚠️ عمداً یه endpoint باریکِ جداست، نه بازکردن کل handle_signals_edit —
    دقیقاً همون فلسفه‌ی result/toggle-entry بالا: صاحبِ سیگنال فقط به عکسِ
    خودش دسترسی می‌گیره، نه بقیه‌ی فیلدها (coin/direction/...) که باید
    admin-only بمونه.
    """
    signal_id = int(request.match_info["id"])
    if not _require_owner_or_admin(request, signal_id):
        return _json_error(403, "فقط صاحبِ سیگنال یا ادمین")
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    kind = body.get("kind")
    if kind not in ("before", "after"):
        return _json_error(400, "kind باید before یا after باشه")

    raw = body.get("image_data", "")
    if not raw:
        return _json_error(400, "image_data خالیه")

    # کلاینت data URL می‌فرسته: "data:image/jpeg;base64,/9j/...." (خروجی مستقیم canvas.toDataURL)
    content_type = "image/jpeg"
    b64_part = raw
    if raw.startswith("data:"):
        try:
            header, b64_part = raw.split(",", 1)
            if ";base64" in header:
                content_type = header[len("data:"):header.index(";")]
        except ValueError:
            return _json_error(400, "فرمت image_data نامعتبره")

    if content_type not in _ALLOWED_IMAGE_TYPES:
        return _json_error(400, "فقط jpeg/png/webp مجازه")

    try:
        image_bytes = base64.b64decode(b64_part, validate=True)
    except Exception:
        return _json_error(400, "دیکد base64 ناموفق بود")

    # ⚠️ هیچ‌وقت به اعتبارسنجی سمت کلاینت (رسایز/کیفیت canvas) اعتماد نکن —
    # اینجا هم حجم واقعی رو بعد از دیکد چک می‌کنیم.
    if len(image_bytes) == 0:
        return _json_error(400, "عکس خالیه")
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        return _json_error(413, f"عکس بیشتر از {_MAX_IMAGE_BYTES // (1024 * 1024)}MB نمی‌تونه باشه")

    ext = _ALLOWED_IMAGE_TYPES[content_type]
    filename = f"signal-{signal_id}-{kind}-{uuid.uuid4().hex[:8]}.{ext}"
    url = await image_upload.upload_web_image(image_bytes, filename, content_type)
    if not url:
        return _json_error(502, "آپلود عکس ناموفق بود (سرویس Storage در دسترس نیست یا تنظیم نشده)")

    field = "before_img" if kind == "before" else "after_img"
    ok = signals.edit_signal(signal_id, **{field: url})
    if not ok:
        return _json_error(404, "signal not found")
    return web.json_response({"ok": True, "url": url})


async def handle_signals_delete(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "admin only")
    signal_id = int(request.match_info["id"])
    ok = signals.delete_signal(signal_id)
    return web.json_response({"ok": ok}) if ok else _json_error(404, "signal not found")


def _require_session(request: web.Request):
    """برای اکشن‌هایی که فقط لاگین‌بودن (نه لزوماً ادمین) لازم دارن — مثل امتیازدهی."""
    token = _get_session_from_request(request)
    return auth.get_session(token)


async def handle_ratings_get(request: web.Request) -> web.Response:
    ctid = request.query.get("caller_telegram_id")
    cname = request.query.get("caller_name")
    if not ctid and not cname:
        return _json_error(400, "caller_telegram_id یا caller_name لازمه")
    rows = ratings.get_ratings_for_caller(caller_telegram_id=int(ctid) if ctid else None, caller_name=cname)
    return web.json_response(rows)


async def handle_ratings_all(request: web.Request) -> web.Response:
    return web.json_response(ratings.get_all_ratings())


async def handle_ratings_summary(request: web.Request) -> web.Response:
    return web.json_response(ratings.get_all_ratings_summary())


async def handle_ratings_submit(request: web.Request) -> web.Response:
    # ⚠️ هدف اصلی فاز ۰-ب: هر عضو لاگین‌شده، نه فقط admin/caller.
    session = _require_session(request)
    if not session:
        return _json_error(401, "اول باید با تلگرام وارد شده باشی")
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    ok, err = ratings.submit_rating(
        rater_telegram_id=session["telegram_id"], rating=body.get("rating", 0),
        caller_telegram_id=body.get("caller_telegram_id"), caller_name=body.get("caller_name"),
        comment=body.get("comment"),
    )
    return web.json_response({"ok": True}) if ok else _json_error(400, err)


async def handle_ratings_delete(request: web.Request) -> web.Response:
    session = _require_session(request)
    if not session:
        return _json_error(401, "اول باید با تلگرام وارد شده باشی")
    rating_id = int(request.match_info["id"])
    ok = ratings.delete_rating(rating_id, actor_telegram_id=session["telegram_id"], is_admin=session.get("role") == "admin")
    return web.json_response({"ok": True}) if ok else _json_error(403, "فقط صاحبِ رأی یا ادمین می‌تونه حذفش کنه")


_ALLOWED_CONTENT_KEYS = {"articles", "strategies"}


async def handle_content_list(request: web.Request) -> web.Response:
    prefix = request.query.get("prefix", "")
    return web.json_response({"keys": kv.kv_list(prefix)})


async def handle_content_get(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    if key not in _ALLOWED_CONTENT_KEYS:
        return _json_error(404, "کلید ناشناخته")
    value = kv.kv_get(key)
    return web.json_response(json.loads(value) if value else [])


async def handle_content_set(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    if key not in _ALLOWED_CONTENT_KEYS:
        return _json_error(404, "کلید ناشناخته")
    if not _require_admin(request):
        return _json_error(403, "admin only")
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")
    kv.kv_set(key, json.dumps(body, ensure_ascii=False))
    return web.json_response({"ok": True})


def register(app: web.Application):
    app.router.add_get("/", handle_index)
    app.router.add_post("/site/login-widget", handle_login_widget)
    app.router.add_get("/site/session", handle_session)
    app.router.add_post("/site/profile", handle_profile_update)
    app.router.add_post("/site/claim-role", handle_claim_role)
    app.router.add_post("/site/verify-pin", handle_verify_pin)
    app.router.add_get("/site/signals", handle_signals_get)
    app.router.add_post("/site/signals", handle_signals_create)
    app.router.add_post("/site/detect-chain", handle_detect_chain)
    app.router.add_patch("/site/signals/{id}", handle_signals_edit)
    app.router.add_post("/site/signals/{id}/result", handle_signals_result)
    app.router.add_post("/site/signals/{id}/toggle-entry", handle_signals_toggle_entry)
    app.router.add_post("/site/signals/{id}/images", handle_signal_image_upload)
    app.router.add_delete("/site/signals/{id}", handle_signals_delete)
    app.router.add_get("/site/ratings", handle_ratings_get)
    app.router.add_get("/site/leaderboard", handle_leaderboard)
    app.router.add_post("/site/callers/tier", handle_set_caller_tier)
    app.router.add_get("/site/home", handle_home)
    app.router.add_get("/site/ratings/all", handle_ratings_all)
    app.router.add_get("/site/ratings/summary", handle_ratings_summary)
    app.router.add_post("/site/ratings", handle_ratings_submit)
    app.router.add_delete("/site/ratings/{id}", handle_ratings_delete)
    app.router.add_get("/site/content", handle_content_list)
    app.router.add_get("/site/content/{key}", handle_content_get)
    app.router.add_post("/site/content/{key}", handle_content_set)
