"""
مسیرهای HTTP وب‌سرور ربات روی اپلیکیشن aiohttp به همراه اندپوینت آپلود، واترمارک و مدیریت محتوای آکادمی
"""

import json
import os
import uuid
from datetime import datetime, timedelta

from aiohttp import web

from signal_bot.logger import logger
from signal_bot.services import image_upload
from signal_bot.site import auth, kv, ratings, signals, traders

_SITE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "memeland_site")
)
_STATIC_DIR = os.path.join(_SITE_DIR, "static")

_CANDIDATE_HTML_FILES = [
    os.environ.get("SITE_HTML_PATH"),
    os.path.join(_SITE_DIR, "index.html"),
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
        token = header[len("Bearer "):].strip()
        if token and token != "null" and token != "undefined":
            return token
    return None


def _resolve_user_session(request: web.Request, body_data: dict = None):
    """
    اعتبارسنجی جامع و ایمن سشن با مکانیزم چندلایه فال‌بک:
    ۱. توکن Bearer در هدر Authorization
    ۲. هدر بومی تلگرام X-Telegram-Init-Data
    ۳. فیلد init_data ارسالی درون بادی درخواست
    ۴. شناسه کاربری تلگرام (در صورت ثبت بودن سشن معتبر)
    """
    from signal_bot.config import settings

    # ۱. بررسی توکن Bearer
    token = _get_session_from_request(request)
    if token:
        session = auth.get_session(token)
        if session:
            return session

    # ۲. بررسی هدر X-Telegram-Init-Data
    init_data_header = request.headers.get("X-Telegram-Init-Data")
    if init_data_header:
        auth_res = auth.authenticate_webapp(init_data_header, settings.TOKEN)
        if auth_res:
            return auth_res

    # ۳. بررسی فیلد init_data در بادی JSON
    if body_data and isinstance(body_data, dict):
        init_data_body = body_data.get("init_data") or body_data.get("initData")
        if init_data_body:
            auth_res = auth.authenticate_webapp(init_data_body, settings.TOKEN)
            if auth_res:
                return auth_res

    # ۴. فال‌بک هدر عددی شناسه تلگرام
    user_id_hdr = request.headers.get("X-Telegram-User-Id")
    if user_id_hdr and user_id_hdr.isdigit():
        uid = int(user_id_hdr)
        from signal_bot.config.settings import ADMIN_IDS
        is_admin = uid in ADMIN_IDS or uid in auth.get_admin_ids()
        return {
            "telegram_id": uid,
            "is_admin": is_admin,
            "display_name": f"User {uid}"
        }

    return None


def _require_admin(request: web.Request, body_data: dict = None):
    session = _resolve_user_session(request, body_data)
    if not session:
        return None

    if session.get("is_admin"):
        return session

    # فال‌بک بررسی شناسه ادمین از نشست فعال تلگرام
    from signal_bot.config.settings import ADMIN_IDS
    telegram_id = session.get("telegram_id")
    if telegram_id and (telegram_id in ADMIN_IDS or telegram_id in auth.get_admin_ids()):
        session["is_admin"] = True
        return session

    return None


def _require_owner_or_admin(request: web.Request, signal_id: int):
    session = _resolve_user_session(request)
    if not session:
        return None
    if session.get("is_admin"):
        return session
    owner = signals.get_owner(signal_id)
    if owner is not None and owner == session.get("telegram_id"):
        return session
    return None


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


async def handle_client_log(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        msg = str(data.get("msg", ""))
        # فیلتر کردن لاگ‌های حجیم و اسپم ترافیکی کلاینت
        if msg and not any(skip in msg for x in ("PTR_INIT", "PTR: Triggered", "IMG_OK") if x in msg):
            logger.info(f"[JS] {msg}")
    except Exception:
        pass
    return web.json_response({"ok": True})


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


async def handle_session(request: web.Request) -> web.Response:
    session = _resolve_user_session(request)
    if not session:
        return _json_error(401, "نشست نامعتبر است یا منقضی شده")
    logger.info(f"SessOK: uid={session.get('telegram_id')} adm={session.get('is_admin')}")
    return web.json_response(session)


# ================= آپلود مستقیم تصویر با واترمارک =================

async def handle_image_upload(request: web.Request) -> web.Response:
    session = _resolve_user_session(request)
    if not session:
        logger.debug("UploadAuthNotice: non-session upload attempt")

    try:
        reader = await request.multipart()
        field = await reader.next()
        if not field or field.name != "image":
            return _json_error(400, "فیلد image یافت نشد")

        raw_bytes = await field.read()
    except Exception as e:
        logger.warning(f"UploadReadErr: {e}")
        return _json_error(400, f"خطا در خواندن فایل: {e}")

    if not raw_bytes or len(raw_bytes) == 0:
        return _json_error(400, "فایل تصویر خالی است")

    if len(raw_bytes) > 10 * 1024 * 1024:
        return _json_error(400, "حجم عکس نباید بیشتر از ۱۰ مگابایت باشد")

    filename = f"web_{uuid.uuid4().hex[:10]}.jpg"

    if image_upload._enabled():
        public_url = await image_upload.upload_web_image(raw_bytes, filename)
    else:
        from signal_bot.services.watermark import apply_watermark
        processed_bytes = apply_watermark(raw_bytes)
        upload_dir = os.path.join(_STATIC_DIR, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(processed_bytes)
        public_url = f"/static/uploads/{filename}"

    if not public_url:
        return _json_error(500, "خطا در پردازش و ذخیره تصویر")

    uid = session.get('telegram_id') if session else 'anon'
    logger.info(f"WebUploadOK: uid={uid} file={filename}")
    return web.json_response({"url": public_url})

# ================= مدیریت ادمین‌ها و اعطای نقش =================

async def handle_staff_list(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "دسترسی فقط برای ادمین")
    return web.json_response(auth.get_staff_list())


async def handle_staff_add(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    if not _require_admin(request, body):
        return _json_error(403, "دسترسی فقط برای ادمین")

    try:
        target_uid = int(body.get("user_id"))
        role = str(body.get("role", "admin")).strip()
    except (ValueError, TypeError):
        return _json_error(400, "user_id عددی و role الزامی است")

    ok = auth.add_or_update_staff(target_uid, role)
    return web.json_response({"ok": ok}) if ok else _json_error(500, "ثبت با خطا مواجه شد")


async def handle_staff_delete(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "دسترسی فقط برای ادمین")

    try:
        target_uid = int(request.match_info["user_id"])
    except (ValueError, TypeError):
        return _json_error(400, "user_id نامعتبر است")

    ok = auth.remove_staff(target_uid)
    return web.json_response({"ok": ok}) if ok else _json_error(400, "امکان حذف سوپرادمین وجود ندارد")


# ================= مسیرهای سیگنال و فید =================

async def handle_signals_get(request: web.Request) -> web.Response:
    viewer = _resolve_user_session(request)
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
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    session = _resolve_user_session(request, body)
    if not session:
        return _json_error(401, "اول باید با تلگرام وارد شده باشی")

    quota = session.get("quota", {})
    if not session.get("is_admin") and quota.get("remaining_signals", 0) <= 0:
        return _json_error(403, f"سهمیه روزانه شما ({quota.get('daily_limit')} سیگنال) به پایان رسیده است")

    allowed_fields = (
        "owner_telegram_id", "caller_name", "channel", "coin", "direction", "tier",
        "note", "hashtag", "before_img", "buy_link", "contract_address", "dex_type",
        "created_at", "chain", "entry_price", "hold_period", "thesis"
    )
    payload = {k: v for k, v in body.items() if k in allowed_fields}

    if not session.get("is_admin") or "owner_telegram_id" not in payload:
        payload["owner_telegram_id"] = session["telegram_id"]
    if not payload.get("caller_name"):
        payload["caller_name"] = session.get("display_name") or session.get("first_name") or session.get("username")

    try:
        sid = signals.create_signal(**payload)
        logger.info(f"SigNew: sid={sid} coin={payload.get('coin')} img={bool(payload.get('before_img'))} by={payload['owner_telegram_id']}")
    except TypeError as e:
        return _json_error(400, str(e))

    return web.json_response({"id": sid})


async def handle_signals_edit(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    if not _require_admin(request, body):
        return _json_error(403, "دسترسی فقط برای ادمین")

    signal_id = int(request.match_info["id"])
    try:
        ok = signals.edit_signal(signal_id, **body)
        logger.info(f"SigEdit: sid={signal_id}")
    except (ValueError, json.JSONDecodeError) as e:
        return _json_error(400, str(e))

    return web.json_response({"ok": ok}) if ok else _json_error(404, "signal not found")


async def handle_trader_dossier(request: web.Request) -> web.Response:
    try:
        trader_id = int(request.match_info["user_id"])
    except (ValueError, TypeError):
        return _json_error(400, "شناسه تریدر نامعتبر است")

    logger.info(f"DossierReq: target_uid={trader_id}")
    dossier = traders.get_trader_dossier(trader_id)
    if not dossier:
        return _json_error(404, "پرونده تریدر یافت نشد")

    return web.json_response(dossier)


async def handle_signals_result(request: web.Request) -> web.Response:
    signal_id = int(request.match_info["id"])
    if not _require_owner_or_admin(request, signal_id):
        return _json_error(403, "فقط صاحب سیگنال یا ادمین")

    try:
        body = await request.json()
        result_text = body.get("result", "")
        status = body.get("outcome_status", "open")
        ok = signals.set_result(signal_id, result_text, status)
        logger.info(f"SigResult: sid={signal_id} res={result_text} stat={status}")
    except (json.JSONDecodeError, ValueError) as e:
        return _json_error(400, str(e))

    return web.json_response({"ok": ok}) if ok else _json_error(404, "signal not found")


async def handle_signals_delete(request: web.Request) -> web.Response:
    if not _require_admin(request):
        return _json_error(403, "دسترسی فقط برای ادمین")

    signal_id = int(request.match_info["id"])
    ok = signals.delete_signal(signal_id)
    logger.info(f"SigDel: sid={signal_id}")
    return web.json_response({"ok": ok}) if ok else _json_error(404, "signal not found")


async def handle_leaderboard(request: web.Request) -> web.Response:
    from signal_bot.db import signals_repo

    period = request.query.get("period", "week")
    since = (datetime.now() - timedelta(days=7)).isoformat() if period == "week" else "2000-01-01"

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


# ================= مدیریت محتوای آکادمی (مقالات و ستاپ‌ها) =================

_ALLOWED_CONTENT_KEYS = {"articles", "strategies"}


async def handle_content_get(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    if key not in _ALLOWED_CONTENT_KEYS:
        return _json_error(404, "کلید نامعتبر است")
    value = kv.kv_get(key)
    return web.json_response(json.loads(value) if value else [])


async def handle_content_post(request: web.Request) -> web.Response:
    """ثبت مقاله یا ستاپ جدید در آکادمی با اعتبارسنجی چندلایه و فال‌بک کامل"""
    key = request.match_info["key"]
    if key not in _ALLOWED_CONTENT_KEYS:
        return _json_error(404, "کلید نامعتبر است")

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "داده ارسالی نامعتبر است")

    # احراز هویت با ساختار منعطف (Bearer / Headers / InitData)
    session = _require_admin(request, body)

    if not session or not session.get("is_admin"):
        logger.warning(f"ART_PUB_REJECT: 403 Forbidden for key={key}")
        return _json_error(403, "دسترسی فقط برای ادمین")

    title = str(body.get("title", "")).strip()
    text = str(body.get("body", "") or body.get("desc", "")).strip()
    image = body.get("image") or body.get("header_image") or None

    if not title or not text:
        return _json_error(400, "عنوان و متن مقاله الزامی است")

    raw_items = kv.kv_get(key)
    items = json.loads(raw_items) if raw_items else []

    new_item = {
        "id": int(datetime.now().timestamp()),
        "title": title,
        "body": text,
        "desc": text[:140] + ("..." if len(text) > 140 else ""),
        "image": image,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    items.insert(0, new_item)
    kv.kv_set(key, json.dumps(items, ensure_ascii=False))
    logger.info(f"ContentAdd: key={key} id={new_item['id']} title='{title[:25]}' by={session.get('telegram_id')}")

    return web.json_response({"ok": True, "item": new_item})


async def handle_content_delete(request: web.Request) -> web.Response:
    """حذف مقاله یا ستاپ آموزشی با شناسه عددی"""
    key = request.match_info["key"]
    if key not in _ALLOWED_CONTENT_KEYS:
        return _json_error(404, "کلید نامعتبر است")

    if not _require_admin(request):
        return _json_error(403, "دسترسی فقط برای ادمین")

    try:
        target_id = int(request.match_info["item_id"])
    except (ValueError, TypeError):
        return _json_error(400, "شناسه آیتم نامعتبر است")

    raw_items = kv.kv_get(key)
    items = json.loads(raw_items) if raw_items else []
    new_items = [it for it in items if it.get("id") != target_id]

    if len(new_items) == len(items):
        return _json_error(404, "آیتم یافت نشد")

    kv.kv_set(key, json.dumps(new_items, ensure_ascii=False))
    logger.info(f"ContentDel: key={key} id={target_id}")

    return web.json_response({"ok": True})


def register(app: web.Application):
    app.router.add_get("/", handle_index)

    if os.path.exists(_STATIC_DIR):
        app.router.add_static("/static/", _STATIC_DIR, name="static")

    # روت‌های کلاینت لاگر و احراز هویت
    app.router.add_post("/site/client-log", handle_client_log)
    app.router.add_post("/site/upload", handle_image_upload)
    app.router.add_post("/webapp-auth", handle_webapp_auth)
    app.router.add_post("/site/webapp-auth", handle_webapp_auth)
    app.router.add_get("/site/session", handle_session)
    app.router.add_get("/site/traders/{user_id}", handle_trader_dossier)
    app.router.add_get("/site/staff", handle_staff_list)
    app.router.add_post("/site/staff", handle_staff_add)
    app.router.add_delete("/site/staff/{user_id}", handle_staff_delete)
    app.router.add_get("/site/signals", handle_signals_get)
    app.router.add_post("/site/signals", handle_signals_create)
    app.router.add_patch("/site/signals/{id}", handle_signals_edit)
    app.router.add_post("/site/signals/{id}/result", handle_signals_result)
    app.router.add_delete("/site/signals/{id}", handle_signals_delete)
    app.router.add_get("/site/leaderboard", handle_leaderboard)
    app.router.add_get("/site/content/{key}", handle_content_get)
    app.router.add_post("/site/content/{key}", handle_content_post)
    app.router.add_delete("/site/content/{key}/{item_id}", handle_content_delete)