"""
مسیرهای HTTP وب‌سرور ربات روی اپلیکیشن aiohttp

وظایف ماژول:
۱. سرو فایل ساختار اصلی مینی‌اپ (index.html) و پوشه فایل‌های استاتیک (static/)
۲. احراز هویت اختصاصی Telegram WebApp (initData) و لاگین ویجت
۳. مدیریت نشست‌ها، سطوح دسترسی (RBAC) و پروفایل کاربری
۴. ثبت، ویرایش، حذف و دریافت فید سیگنال‌ها
۵. مدیریت لیدربورد، سیستم امتیازدهی و آکادمی
"""

import base64
import json
import logging
import os
import uuid
from datetime import datetime, timedelta

from aiohttp import web

from signal_bot.services import image_upload
from signal_bot.site import auth, kv, ratings, signals

logger = logging.getLogger(__name__)

# مسیر ریشه پوشه وب‌سایت و فایل‌های استاتیک
_SITE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "memeland_site")
)
_STATIC_DIR = os.path.join(_SITE_DIR, "static")

# تقدم با index.html جدید؛ در صورت عدم وجود، fallback به فایل‌های قبلی
_CANDIDATE_HTML_FILES = [
    os.environ.get("SITE_HTML_PATH"),
    os.path.join(_SITE_DIR, "index.html"),
    os.path.join(_SITE_DIR, "memeland-hub_UPDATED_2.html"),
    os.path.join(_SITE_DIR, "memeland-hub_UPDATED.html"),
]


def _resolve_html_path() -> str:
    for path in _CANDIDATE_HTML_FILES:
        if path and os.path.exists(path):
            return path
    return os.path.join(_SITE_DIR, "index.html")


def _json_error(status: int, message: str) -> web.Response:
    return web.json_response({"error": message}, status=status)


def _get_session_from_request(request: web.Request):
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    return None


def _client_ip(request: web.Request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote or "unknown"


async def handle_index(request: web.Request) -> web.Response:
    html_path = _resolve_html_path()
    if not os.path.exists(html_path):
        return web.Response(status=404, text=f"HTML template not found at {html_path}")

    from signal_bot.config import settings

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
    if bot_username:
        html = html.replace("'YOUR_BOT_USERNAME'", f"'{bot_username}'")

    return web.Response(
        text=html,
        content_type="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


async def handle_webapp_auth(request: web.Request) -> web.Response:
    from signal_bot.config import settings

    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    init_data = payload.get("init_data") or payload.get("initData")
    if not init_data:
        return _json_error(400, "init_data الزامی است")

    auth_result = auth.authenticate_webapp(init_data, settings.TOKEN)
    if not auth_result:
        return _json_error(401, "داده‌های تلگرام نامعتبر است")

    return web.json_response(auth_result)


async def handle_login_widget(request: web.Request) -> web.Response:
    from signal_bot.config import settings

    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    user = auth.verify_login_widget_payload(payload, settings.TOKEN)
    if not user:
        return _json_error(401, "invalid login widget payload")

    token = auth.create_session(
        telegram_id=user["id"],
        username=user.get("username"),
        first_name=user.get("first_name"),
        photo_url=user.get("photo_url"),
    )
    profile = auth.get_profile(user["id"])

    return web.json_response({
        "token": token,
        "user": user,
        "role": profile.get("role"),
        "display_name": profile.get("display_name") or user.get("first_name") or user.get("username"),
    })


async def handle_session(request: web.Request) -> web.Response:
    token = _get_session_from_request(request)
    session = auth.get_session(token)
    if not session:
        return _json_error(401, "نشست نامعتبر است یا منقضی شده")

    session = dict(session)
    profile = auth.get_profile(session["telegram_id"])
    session["display_name"] = profile.get("display_name") or session.get("first_name") or session.get("username")
    return web.json_response(session)


async def handle_profile_update(request: web.Request) -> web.Response:
    session = auth.get_session(_get_session_from_request(request))
    if not session:
        return _json_error(401, "نشست نامعتبر است")

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
    ip = _client_ip(request)
    ok = auth.claim_role(token, body.get("role", ""), body.get("pin", ""), actor_ip=ip)
    return web.json_response({"ok": ok}) if ok else _json_error(401, "پین یا توکن نامعتبر است")


async def handle_verify_pin(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    ip = _client_ip(request)
    ok = auth.verify_pin(body.get("role", ""), body.get("pin", ""), actor_ip=ip)
    return web.json_response({"ok": ok})


def _require_admin(request: web.Request):
    token = _get_session_from_request(request)
    session = auth.get_session(token)
    if not session or session.get("role") != "admin":
        return None
    return session


def _require_owner_or_admin(request: web.Request, signal_id: int):
    session = auth.get_session(_get_session_from_request(request))
    if not session:
        return None
    if session.get("role") == "admin":
        return session
    owner = signals.get_owner(signal_id)
    if owner is not None and owner == session["telegram_id"]:
        return session
    return None


def _require_session(request: web.Request):
    token = _get_session_from_request(request)
    return auth.get_session(token)


async def handle_detect_chain(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "دسترسی فقط برای ادمین")

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    address = (body.get("contract_address") or "").strip()
    if not address:
        return _json_error(400, "contract_address الزامی است")

    from signal_bot.services.price_feed import detect_chain_and_price

    chain, price = await detect_chain_and_price(address)
    return web.json_response({"chain": chain, "price": price})


async def handle_home(request: web.Request) -> web.Response:
    viewer = auth.get_session(_get_session_from_request(request))
    return web.json_response({
        "stats": signals.get_stats(),
        "top_recent_wins": signals.get_top_recent_wins(days=7, limit=5, viewer=viewer),
    })


async def handle_set_caller_tier(request: web.Request) -> web.Response:
    session = _require_admin(request)
    if not session:
        return _json_error(403, "دسترسی فقط برای ادمین")

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    ctid = body.get("caller_telegram_id")
    cname = (body.get("caller_name") or "").strip() or None
    if not ctid and not cname:
        return _json_error(400, "caller_telegram_id یا caller_name الزامی است")

    try:
        ratings.set_caller_tier(ctid, cname, body.get("tier") or None, set_by=session["telegram_id"])
    except ValueError as e:
        return _json_error(400, str(e))

    return web.json_response({"ok": True})


async def handle_leaderboard(request: web.Request) -> web.Response:
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
        {
            "user_id": r[0],
            "full_name": r[1],
            "username": r[2],
            "level": r[3],
            "points": r[4],
            "count": r[5],
            "wins": r[6],
        }
        for r in signal_giver_rows
    ]
    return web.json_response({
        "callers": ratings.get_top_callers(limit=10),
        "signal_givers": signal_givers,
    })


async def handle_signals_get(request: web.Request) -> web.Response:
    viewer = auth.get_session(_get_session_from_request(request))
    if not viewer:
        return _json_error(401, "برای دیدن سیگنال‌ها باید با تلگرام وارد بشی")

    try:
        limit = min(int(request.query.get("limit", 200)), 200)
        offset = max(int(request.query.get("offset", 0)), 0)
    except ValueError:
        return _json_error(400, "limit/offset باید عددی باشند")

    status = request.query.get("status") or None
    channel = request.query.get("channel") or None
    q = request.query.get("q") or None

    return web.json_response(
        signals.get_feed(
            limit=limit, offset=offset, status=status, channel=channel, q=q, viewer=viewer
        )
    )


async def handle_signals_create(request: web.Request) -> web.Response:
    session = auth.get_session(_get_session_from_request(request))
    if not session:
        return _json_error(401, "اول باید با تلگرام وارد شده باشی")

    is_admin = session.get("role") == "admin"
    is_caller = session.get("role") == "caller"
    if not (is_admin or is_caller):
        return _json_error(403, "دسترسی ثبت سیگنال ندارید")

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    allowed_fields = (
        "owner_telegram_id", "caller_name", "channel", "coin", "direction", "tier",
        "note", "hashtag", "before_img", "buy_link", "contract_address", "dex_type",
        "created_at", "chain", "entry_price", "hold_period", "thesis"
    )
    payload = {k: v for k, v in body.items() if k in allowed_fields}

    if not is_admin or "owner_telegram_id" not in payload:
        payload["owner_telegram_id"] = session["telegram_id"]
    if not payload.get("caller_name"):
        payload["caller_name"] = session.get("display_name") or session.get("first_name") or session.get("username")

    try:
        sid = signals.create_signal(**payload)
    except TypeError as e:
        return _json_error(400, str(e))

    return web.json_response({"id": sid})


async def handle_signals_edit(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "دسترسی فقط برای ادمین")

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
        return _json_error(403, "فقط صاحب سیگنال یا ادمین")

    try:
        body = await request.json()
        ok = signals.set_result(signal_id, body.get("result", ""), body.get("outcome_status", "open"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        return _json_error(400, str(e))

    return web.json_response({"ok": ok}) if ok else _json_error(404, "signal not found")


async def handle_signals_toggle_entry(request: web.Request) -> web.Response:
    signal_id = int(request.match_info["id"])
    if not _require_owner_or_admin(request, signal_id):
        return _json_error(403, "فقط صاحب سیگنال یا ادمین")

    new_val = signals.toggle_entry_open(signal_id)
    if new_val is None:
        return _json_error(404, "signal not found")

    return web.json_response({"entry_open": bool(new_val)})


_MAX_IMAGE_BYTES = 6 * 1024 * 1024
_ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


async def handle_signal_image_upload(request: web.Request) -> web.Response:
    signal_id = int(request.match_info["id"])
    if not _require_owner_or_admin(request, signal_id):
        return _json_error(403, "فقط صاحب سیگنال یا ادمین")

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    kind = body.get("kind")
    if kind not in ("before", "after"):
        return _json_error(400, "نوع تصویر باید before یا after باشد")

    raw = body.get("image_data", "")
    if not raw:
        return _json_error(400, "تصویر ارسال نشده است")

    content_type = "image/jpeg"
    b64_part = raw
    if raw.startswith("data:"):
        try:
            header, b64_part = raw.split(",", 1)
            if ";base64" in header:
                content_type = header[len("data:"):header.index(";")]
        except ValueError:
            return _json_error(400, "فرمت base64 نامعتبر است")

    if content_type not in _ALLOWED_IMAGE_TYPES:
        return _json_error(400, "فقط فرمت‌های jpeg، png و webp مجاز هستند")

    try:
        image_bytes = base64.b64decode(b64_part, validate=True)
    except Exception:
        return _json_error(400, "دیکود تصویر ناموفق بود")

    if len(image_bytes) == 0:
        return _json_error(400, "فایل تصویر خالی است")
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        return _json_error(413, "حجم تصویر نباید بیشتر از ۶ مگابایت باشد")

    ext = _ALLOWED_IMAGE_TYPES[content_type]
    filename = f"signal-{signal_id}-{kind}-{uuid.uuid4().hex[:8]}.{ext}"
    url = await image_upload.upload_web_image(image_bytes, filename, content_type)
    if not url:
        return _json_error(502, "آپلود تصویر ناموفق بود")

    field = "before_img" if kind == "before" else "after_img"
    ok = signals.edit_signal(signal_id, **{field: url})
    if not ok:
        return _json_error(404, "signal not found")

    return web.json_response({"ok": True, "url": url})


async def handle_signals_delete(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "دسترسی فقط برای ادمین")

    signal_id = int(request.match_info["id"])
    ok = signals.delete_signal(signal_id)
    return web.json_response({"ok": ok}) if ok else _json_error(404, "signal not found")


async def handle_ratings_get(request: web.Request) -> web.Response:
    ctid = request.query.get("caller_telegram_id")
    cname = request.query.get("caller_name")
    if not ctid and not cname:
        return _json_error(400, "caller_telegram_id یا caller_name الزامی است")

    rows = ratings.get_ratings_for_caller(
        caller_telegram_id=int(ctid) if ctid else None, caller_name=cname
    )
    return web.json_response(rows)


async def handle_ratings_all(request: web.Request) -> web.Response:
    return web.json_response(ratings.get_all_ratings())


async def handle_ratings_summary(request: web.Request) -> web.Response:
    return web.json_response(ratings.get_all_ratings_summary())


async def handle_ratings_submit(request: web.Request) -> web.Response:
    session = _require_session(request)
    if not session:
        return _json_error(401, "اول باید با تلگرام وارد شده باشی")

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    ok, err = ratings.submit_rating(
        rater_telegram_id=session["telegram_id"],
        rating=body.get("rating", 0),
        caller_telegram_id=body.get("caller_telegram_id"),
        caller_name=body.get("caller_name"),
        comment=body.get("comment"),
    )
    return web.json_response({"ok": True}) if ok else _json_error(400, err)


async def handle_ratings_delete(request: web.Request) -> web.Response:
    session = _require_session(request)
    if not session:
        return _json_error(401, "اول باید با تلگرام وارد شده باشی")

    rating_id = int(request.match_info["id"])
    ok = ratings.delete_rating(
        rating_id,
        actor_telegram_id=session["telegram_id"],
        is_admin=session.get("role") == "admin",
    )
    return web.json_response({"ok": True}) if ok else _json_error(403, "فقط ثبت‌کننده یا ادمین مجاز به حذف است")


_ALLOWED_CONTENT_KEYS = {"articles", "strategies"}


async def handle_content_list(request: web.Request) -> web.Response:
    prefix = request.query.get("prefix", "")
    return web.json_response({"keys": kv.kv_list(prefix)})


async def handle_content_get(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    if key not in _ALLOWED_CONTENT_KEYS:
        return _json_error(404, "کلید نامعتبر است")
    value = kv.kv_get(key)
    return web.json_response(json.loads(value) if value else [])


async def handle_content_set(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    if key not in _ALLOWED_CONTENT_KEYS:
        return _json_error(404, "کلید نامعتبر است")
    if not _require_admin(request):
        return _json_error(403, "دسترسی فقط برای ادمین")

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    kv.kv_set(key, json.dumps(body, ensure_ascii=False))
    return web.json_response({"ok": True})


def register(app: web.Application):
    app.router.add_get("/", handle_index)

    # سرو فایل‌های استاتیک پوشه static/ (CSS, JS, Assets)
    if os.path.exists(_STATIC_DIR):
        app.router.add_static("/static/", _STATIC_DIR, name="static")

    # روت‌های احراز هویت WebApp و Login Widget
    app.router.add_post("/webapp-auth", handle_webapp_auth)
    app.router.add_post("/site/webapp-auth", handle_webapp_auth)
    app.router.add_post("/site/login-widget", handle_login_widget)

    # مدیریت نشست‌ها، پروفایل و دسترسی‌ها
    app.router.add_get("/site/session", handle_session)
    app.router.add_post("/site/profile", handle_profile_update)
    app.router.add_post("/site/claim-role", handle_claim_role)
    app.router.add_post("/site/verify-pin", handle_verify_pin)

    # فید و کنترل سیگنال‌ها
    app.router.add_get("/site/signals", handle_signals_get)
    app.router.add_post("/site/signals", handle_signals_create)
    app.router.add_post("/site/detect-chain", handle_detect_chain)
    app.router.add_patch("/site/signals/{id}", handle_signals_edit)
    app.router.add_post("/site/signals/{id}/result", handle_signals_result)
    app.router.add_post("/site/signals/{id}/toggle-entry", handle_signals_toggle_entry)
    app.router.add_post("/site/signals/{id}/images", handle_signal_image_upload)
    app.router.add_delete("/site/signals/{id}", handle_signals_delete)

    # رتبه‌بندی، لیدربورد و آمار
    app.router.add_get("/site/ratings", handle_ratings_get)
    app.router.add_get("/site/leaderboard", handle_leaderboard)
    app.router.add_post("/site/callers/tier", handle_set_caller_tier)
    app.router.add_get("/site/home", handle_home)
    app.router.add_get("/site/ratings/all", handle_ratings_all)
    app.router.add_get("/site/ratings/summary", handle_ratings_summary)
    app.router.add_post("/site/ratings", handle_ratings_submit)
    app.router.add_delete("/site/ratings/{id}", handle_ratings_delete)

    # آکادمی و محتوا
    app.router.add_get("/site/content", handle_content_list)
    app.router.add_get("/site/content/{key}", handle_content_get)
    app.router.add_post("/site/content/{key}", handle_content_set)