"""
مسیرهای HTTP وب‌سرور ربات روی اپلیکیشن aiohttp به همراه اندپوینت آپلود، واترمارک و مدیریت محتوای آکادمی
"""

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

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


def _path_int(request: web.Request, key: str):
    """
    ⚠️ فیکس: چند هندلر مستقیم `int(request.match_info["id"])` صدا می‌زدن
    بدون try. یه درخواست به `/site/signals/abc` باعث ValueError مدیریت‌نشده
    و پاسخ ۵۰۰ می‌شد (به‌علاوه‌ی یه traceback توی لاگ) به‌جای یه ۴۰۰ تمیز.
    """
    raw = request.match_info.get(key, "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _get_session_from_request(request: web.Request):
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[len("Bearer "):].strip()
        if token and token not in ("null", "undefined", "none"):
            return token
    return None


def _resolve_user_session(request: web.Request, body_data: dict = None):
    from signal_bot.config import settings

    token = _get_session_from_request(request)
    if token:
        session = auth.get_session(token)
        if session:
            return session

    init_data_header = request.headers.get("X-Telegram-Init-Data")
    if init_data_header:
        auth_res = auth.authenticate_webapp(init_data_header, settings.TOKEN)
        if auth_res:
            return auth_res

    if body_data and isinstance(body_data, dict):
        init_data_body = body_data.get("init_data") or body_data.get("initData")
        if init_data_body:
            auth_res = auth.authenticate_webapp(init_data_body, settings.TOKEN)
            if auth_res:
                return auth_res

    user_id_hdr = request.headers.get("X-Telegram-User-Id")
    # ⚠️ فیکس مقاوم‌سازی (شبکه): قبلاً فقط هدر چک می‌شد. کلاینت (api.js) از
    # قبل user_id رو تو بدنه‌ی همون درخواست هم می‌فرسته، ولی این‌جا هیچ‌وقت
    # خونده نمی‌شد. اگه یه پروکسی جلوی سرور (مثلاً nginx بدون تنظیم صریح
    # proxy_set_header) هدرهای سفارشی رو حذف کنه — یه اشتباه پیکربندی خیلی
    # رایج — بدنه‌ی POST همیشه دست‌نخورده می‌رسه، پس این fallback دقیقاً
    # برای همین سناریو لازمه.
    if not user_id_hdr and body_data and isinstance(body_data, dict):
        body_uid = body_data.get("user_id")
        if body_uid:
            user_id_hdr = str(body_uid)

    if user_id_hdr and user_id_hdr.isdigit():
        # 🚨 مسیر «تأییدنشده»: هدر/بدنه‌ی X-Telegram-User-Id هیچ اعتبارسنجی
        # رمزنگاری‌شده‌ای نداره — هرکسی با یه curl ساده می‌تونه ادعا کنه
        # آیدی‌ش هرچیزیه (آیدی تلگرام محرمانه نیست؛ از پیام‌های فوروارد‌شده
        # یا کانال‌های عمومی قابل‌کشفه). پس این مسیر فقط برای شناسایی سطح
        # «عضو عادی» مجازه. دو باگ جدی که اینجا باقی مونده بود:
        #
        #   ۱. 🚨 ارتقای دسترسی: اینجا is_admin سطح بالا False می‌شد، ولی یه
        #      توکن سشن واقعی *صادر* می‌شد. دفعه‌ی بعد که همون توکن با هدر
        #      Authorization برمی‌گشت، auth.get_session() دوباره از صفر
        #      is_admin رو از روی telegram_id حساب می‌کرد و True برمی‌گردوند.
        #      یعنی: curl با آیدی یه ادمین ⇒ توکن ⇒ دسترسی کامل ادمین. کل
        #      محافظت این بلوک با یه رفت‌وبرگشت دور زده می‌شد.
        #      فیکس: توی این مسیر اصلاً توکنی صادر نمی‌شه. هویت تأییدنشده
        #      برای هر درخواست دوباره از همون هدر حل می‌شه و هیچ‌وقت به یه
        #      اعتبارنامه‌ی ماندگار تبدیل نمی‌شه.
        #
        #   ۲. 🚨 نشت از طریق quota: دیکشنری quota دست‌نخورده برگردونده
        #      می‌شد و داخلش is_admin/is_super_admin/display_role واقعی بود.
        #      کلاینت (app.js → updateUserInterface) دقیقاً
        #      `quota?.is_admin === true` رو هم چک می‌کنه ⇒ پنل ادمین برای
        #      هویت اثبات‌نشده باز می‌شد.
        #      فیکس: elevate=False، پس quota از پایه بدون ارتقا ساخته می‌شه.
        #
        # برای دسترسی واقعی ادمین فقط دو راه امن هست: توکن سشن معتبر
        # (که فقط از مسیر امضاشده صادر می‌شه) یا initData امضاشده‌ی تلگرام.
        uid = int(user_id_hdr)
        prof = auth.get_profile(uid)

        return {
            "telegram_id": uid,
            "display_name": prof.get("display_name") or f"User_{uid}",
            "role": "member",
            "is_admin": False,
            "is_super_admin": False,
            "quota": auth.get_user_role_and_quota(uid, elevate=False),
            "unverified": True,
        }

    return None


def _require_verified(session) -> bool:
    """
    هویت «اثبات‌شده» یعنی یکی از این دو:
      • توکن سشن معتبر (که فقط از مسیر initData امضاشده صادر می‌شه)
      • خودِ initData امضاشده‌ی تلگرام توی همین درخواست
    مسیر X-Telegram-User-Id هیچ‌کدوم نیست — فقط یه ادعای خام و قابل‌جعله.
    """
    return bool(session) and not session.get("unverified")


def _require_admin(request: web.Request, body_data: dict = None):
    session = _resolve_user_session(request, body_data)
    if not session:
        return None

    # 🚨🚨 مهم‌ترین فیکس امنیتی این پچ.
    #
    # بلوک قبلی، بعد از این‌که چک اول رد می‌شد، دوباره *فقط بر اساس
    # telegram_id* دسترسی ادمین می‌داد:
    #
    #     if telegram_id in ADMIN_IDS or telegram_id in auth.get_admin_ids():
    #         session["is_admin"] = True
    #         return session
    #
    # و روی مسیر تأییدنشده، telegram_id مستقیماً از هدر
    # X-Telegram-User-Id میاد — یعنی کاملاً تحت کنترل درخواست‌دهنده.
    # نتیجه‌ی عملی:
    #
    #     curl -H "X-Telegram-User-Id: <آیدی ادمین>" https://.../site/staff
    #
    # ...دسترسی کامل ادمین می‌داد. همین برای /site/signals (حذف)،
    # /site/staff (افزودن ادمین جدید) و /site/content هم صادق بود.
    # آیدی عددی تلگرام محرمانه نیست؛ از هر پیام فوروارد‌شده‌ای قابل‌کشفه.
    # این باگ، تمام محافظت‌های داخل _resolve_user_session رو دور می‌زد،
    # چون *بعد* از اون اجرا می‌شد.
    #
    # فیکس: هیچ مسیری به دسترسی ادمین ختم نمی‌شه مگر هویت اثبات‌شده باشه.
    if not _require_verified(session):
        logger.warning(
            f"AdminDenyUnverified: uid={session.get('telegram_id')} path={request.path}"
        )
        return None

    if session.get("is_admin") or session.get("is_super_admin"):
        return session

    # شبکه‌ی ایمنی: اگه get_user_role_and_quota به‌خاطر خطای دیتابیس is_admin
    # رو از دست داده باشه، ADMIN_IDS از .env هنوز معتبره — ولی فقط و فقط
    # برای یه سشن اثبات‌شده (چک بالا).
    from signal_bot.config.settings import ADMIN_IDS
    telegram_id = session.get("telegram_id")
    if telegram_id and (int(telegram_id) in [int(x) for x in ADMIN_IDS] or int(telegram_id) in auth.get_admin_ids()):
        session["is_admin"] = True
        return session

    return None


def _require_owner_or_admin(request: web.Request, signal_id: int, body_data: dict = None):
    # ⚠️ فیکس: قبلاً body_data رو مثل _require_admin پاس نمی‌داد؛ یعنی اگه
    # کلاینتی init_data رو فقط تو بدنه‌ی JSON بفرسته (نه هدر Authorization/
    # X-Telegram-Init-Data)، این تابع همیشه رد می‌کرد حتی برای صاحب واقعی سیگنال.
    session = _resolve_user_session(request, body_data)
    # 🚨 همون خانواده‌ی باگ: چک مالکیت، telegram_id سشن رو با owner سیگنال
    # مقایسه می‌کنه. روی مسیر تأییدنشده اون آیدی از هدر میاد، پس هرکسی
    # می‌تونست ادعا کنه صاحب هر سیگنالیه و نتیجه‌ش رو عوض کنه (win/loss) —
    # که مستقیماً روی لیدربورد و امتیاز کالرها اثر می‌ذاره.
    if not _require_verified(session):
        return None
    if session.get("is_admin") or session.get("is_super_admin"):
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


# ================= لاگ کلاینت =================
#
# 🚨 مشکلات نسخه‌ی قبلی:
#   • هیچ سقف طولی نداشت ⇒ یه POST با ۱۰ مگابایت متن، مستقیم می‌رفت توی
#     فایل لاگ.
#   • \n رو فیلتر نمی‌کرد ⇒ هر کاربری می‌تونست خطوط لاگ *جعلی* بسازه که
#     دقیقاً شبیه خروجی خود سرور به‌نظر برسن (log injection).
#   • هیچ محدودیت نرخی نداشت ⇒ یه حلقه‌ی ساده می‌تونست لاگ رو پر کنه و با
#     rotation، شواهد واقعی رو از بین ببره.
#   • هر خط لاگ یه درخواست جدا بود (توی لاگ خودتون: ۱۴ درخواست در ۴۰ ثانیه
#     فقط برای loadSignalsOK).
#   • همه‌چی با سطح INFO ثبت می‌شد، حتی خطاهای JS ⇒ فیلتر کردن ممکن نبود.
# الان: batch، سقف طول، پاک‌سازی، محدودیت نرخ per-IP، و سطح واقعی.

_CLIENT_LOG_MAX_LEN = 300
_CLIENT_LOG_MAX_EVENTS = 25
_CLIENT_LOG_WINDOW = 10.0          # ثانیه
_CLIENT_LOG_MAX_PER_WINDOW = 60    # رویداد روتین در هر پنجره، به ازای هر IP
_CLIENT_LOG_ERROR_CAP = 200        # سقف سخت، حتی برای batch هایی که خطا دارن
_CLIENT_LOG_BUCKETS = {}

_CLIENT_LEVELS = {"E": logging.ERROR, "W": logging.WARNING,
                  "I": logging.INFO, "D": logging.DEBUG}

# رویدادهای روتینی که ارزش نگه‌داری ندارن.
_CLIENT_LOG_DROP = ("PTR_INIT", "PTR: Triggered", "IMG_OK")


def _client_ip(request: web.Request) -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote or "?"


def _client_log_allowed(ip: str, count: int, has_error: bool = False) -> bool:
    """
    سهمیه‌ی مبتنی بر بودجه، per-IP.

    ⚠️ تصمیم طراحی: رویدادهای سطح ERROR هیچ‌وقت به‌خاطر محدودیت نرخ دور
    ریخته نمی‌شن (تا سقف سخت‌گیرانه‌تر). هدف این محدودیت، جلوگیری از پر شدن
    لاگ با رویدادهای روتینه — نه بلعیدن دقیقاً همون خطایی که داریم دنبالش
    می‌گردیم. یه کرش پشت‌سرهم دقیقاً وقتی اتفاق می‌افته که نرخ لاگ بالاست.
    """
    now = time.monotonic()
    start, used = _CLIENT_LOG_BUCKETS.get(ip, (now, 0))
    if now - start > _CLIENT_LOG_WINDOW:
        start, used = now, 0

    cap = _CLIENT_LOG_ERROR_CAP if has_error else _CLIENT_LOG_MAX_PER_WINDOW
    if used + count > cap:
        _CLIENT_LOG_BUCKETS[ip] = (start, used)
        return False
    _CLIENT_LOG_BUCKETS[ip] = (start, used + count)
    # جلوگیری از رشد بی‌نهایت دیکشنری باکت‌ها.
    if len(_CLIENT_LOG_BUCKETS) > 500:
        cutoff = now - _CLIENT_LOG_WINDOW * 2
        for k in [k for k, v in _CLIENT_LOG_BUCKETS.items() if v[0] < cutoff]:
            _CLIENT_LOG_BUCKETS.pop(k, None)
    return True


def _sanitize_log(msg: str) -> str:
    """خطوط جدید و کاراکترهای کنترلی رو حذف می‌کنه تا کلاینت نتونه خط لاگ جعلی بسازه."""
    clean = re.sub(r"[\r\n\t\x00-\x1f\x7f]+", " ", str(msg)).strip()
    if len(clean) > _CLIENT_LOG_MAX_LEN:
        clean = clean[:_CLIENT_LOG_MAX_LEN] + "…"
    return clean


async def handle_client_log(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False}, status=400)

    if not isinstance(data, dict):
        return web.json_response({"ok": False}, status=400)

    # فرمت جدید (batch) و فرمت قدیمی (تک‌پیام) هر دو پشتیبانی می‌شن، تا
    # مرورگرهایی که هنوز نسخه‌ی کش‌شده‌ی قدیمی رو دارن ساکت نشن.
    events = data.get("events")
    if not isinstance(events, list):
        events = [{"lv": "I", "msg": data.get("msg", "")}]

    events = events[:_CLIENT_LOG_MAX_EVENTS]
    has_error = any(
        isinstance(e, dict) and str(e.get("lv", "")).upper().startswith("E")
        for e in events
    )
    if not _client_log_allowed(_client_ip(request), len(events), has_error):
        return web.json_response({"ok": True, "throttled": True})

    sid = _sanitize_log(data.get("sid", ""))[:12] or "?"
    build = _sanitize_log(data.get("build", ""))[:24] or "?"

    for ev in events:
        if not isinstance(ev, dict):
            continue
        msg = _sanitize_log(ev.get("msg", ""))
        if not msg or any(tag in msg for tag in _CLIENT_LOG_DROP):
            continue
        level = _CLIENT_LEVELS.get(str(ev.get("lv", "I")).upper()[:1], logging.INFO)
        logger.log(level, f"[JS:{sid}] {msg}")

    return web.json_response({"ok": True})

async def handle_webapp_auth(request: web.Request) -> web.Response:
    from signal_bot.config import settings

    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    init_data = payload.get("init_data") or payload.get("initData")
    # ⚠️ تشخیصی: این خط دقیقاً می‌گه سرور چی گرفته (طول init_data، وجود هدرهای
    # تلگرام، user_id تو بدنه) — با مقایسه‌ش با لاگ AuthAttempt سمت کلاینت،
    # می‌فهمیم اگه initData خالی می‌رسه، مشکل قبل از رسیدن به سرور بوده
    # (یعنی خودِ کلاینت خالی فرستاده) یا رسیده ولی همینجا رد شده.
    logger.info(
        f"WebAppAuthReq: path={request.path} initDataLen={len(init_data or '')} "
        f"hasInitHeader={bool(request.headers.get('X-Telegram-Init-Data'))} "
        f"hdrUserId={request.headers.get('X-Telegram-User-Id')} "
        f"bodyUserId={payload.get('user_id')}"
    )

    if not init_data:
        session = _resolve_user_session(request, payload)
        if session:
            return web.json_response(session)
        return _json_error(400, "init_data الزامی است")

    auth_result = auth.authenticate_webapp(init_data, settings.TOKEN)
    if not auth_result:
        session = _resolve_user_session(request, payload)
        if session:
            return web.json_response(session)
        return _json_error(401, "داده‌های تلگرام نامعتبر است")

    return web.json_response(auth_result)


async def handle_session(request: web.Request) -> web.Response:
    session = _resolve_user_session(request)
    if not session:
        return _json_error(401, "نشست نامعتبر است یا منقضی شده")
    logger.info(
        f"SessOK: uid={session.get('telegram_id')} adm={session.get('is_admin')} "
        f"verified={0 if session.get('unverified') else 1} role={session.get('role')}"
    )
    return web.json_response(session)


# ================= آپلود تصویر =================

async def handle_image_upload(request: web.Request) -> web.Response:
    session = _resolve_user_session(request)
    # 🚨 فیکس: قبلاً نتیجه‌ی این فراخوانی هیچ‌وقت چک نمی‌شد — یعنی یه غریبه‌ی
    # کاملاً ناشناس می‌تونست هر فایل ۱۰ مگابایتی رو توی /static/uploads بنویسه
    # (اسمش .jpg می‌شد ولی محتواش اصلاً اعتبارسنجی نمی‌شه). هم پر شدن دیسک،
    # هم میزبانی فایل دلخواه روی دامنه‌ی خودتون.
    if not _require_verified(session):
        return _json_error(401, "برای آپلود باید از داخل تلگرام وارد شده باشی")

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

    # ⚠️ فال‌بک محلی حالا داخل image_upload._upload_bytes متمرکز شده (نگاه
    # کن به services/image_upload.py) — این تابع دیگه لازم نیست بدونه
    # Supabase تنظیم هست یا نه؛ فقط صدا می‌زنه و نتیجه رو چک می‌کنه.
    public_url = await image_upload.upload_web_image(raw_bytes, filename)

    if not public_url:
        return _json_error(500, "خطا در پردازش و ذخیره تصویر")

    uid = session.get('telegram_id') if session else 'anon'
    logger.info(f"WebUploadOK: uid={uid} file={filename}")
    return web.json_response({"url": public_url})


# ================= مدیریت کادر =================

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


# ================= مسیرهای فید سیگنال‌ها =================

async def handle_signals_get(request: web.Request) -> web.Response:
    # ⚠️ فیکس امنیتی: قبلاً وقتی session معتبر نبود، به یه ادمین ساختگی
    # fallback می‌کرد (احتمالاً یه shortcut دیباگ که به‌اشتباه commit شده بود)
    # و کل پی‌وال VIP رو برای هر بازدیدکننده‌ی ناشناس دور می‌زد. viewer=None
    # دقیقاً همون چیزیه که signals.get_feed()/​_viewer_has_vip_access از قبل
    # برای مهمانِ بدون دسترسی طراحی شده بودن که باهاش کار کنن.
    viewer = _resolve_user_session(request)

    try:
        limit = min(int(request.query.get("limit", 200)), 200)
        offset = max(int(request.query.get("offset", 0)), 0)
    except (ValueError, TypeError):
        limit, offset = 200, 0

    try:
        feed_data = signals.get_feed(limit=limit, offset=offset, viewer=viewer)
    except Exception as e:
        logger.error(f"SignalsFeedErr: {e}")
        feed_data = {}

    if isinstance(feed_data, dict):
        raw_list = feed_data.get("items", [])
    elif isinstance(feed_data, list):
        raw_list = feed_data
    else:
        raw_list = []

    # ⚠️ اضافه شدن هویت بیننده: وقتی فید خالی برمی‌گرده، تنها سؤال مهم اینه
    # که «خالیه چون دیتابیس خالیه، یا چون بیننده دسترسی نداره؟». بدون uid و
    # total این خط چیزی رو مشخص نمی‌کرد.
    logger.info(
        f"FeedDeliver: count={len(raw_list)} total={feed_data.get('total') if isinstance(feed_data, dict) else '?'} "
        f"uid={(viewer or {}).get('telegram_id', 'anon')} adm={(viewer or {}).get('is_admin', False)}"
    )
    return web.json_response(raw_list)


async def handle_signals_create(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    session = _resolve_user_session(request, body)
    if not session:
        return _json_error(401, "اول باید با تلگرام وارد شده باشی")
    # 🚨 بدون این چک، یه هدر جعلی کافی بود تا سیگنال به اسم هر کاربری ثبت
    # بشه (owner_telegram_id از همون سشن پر می‌شه) — یعنی آلوده کردن آمار و
    # اعتبار کالرهای واقعی، و دور زدن سهمیه با عوض کردن آیدی.
    if not _require_verified(session):
        return _json_error(403, "برای ثبت سیگنال باید از داخل تلگرام وارد شده باشی")

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
    except TypeError as e:
        return _json_error(400, str(e))

    # 🚨 سینک دوطرفه: بدون این، سیگنالِ ثبت‌شده در وب‌اپ هیچ‌وقت وارد
    # دیتابیس ربات نمی‌شد و در بخش چت اصلاً دیده نمی‌شد. مقصر اصلی یکی از
    # دو علامتی بود که گزارش شد.
    from signal_bot.services import site_sync
    synced = site_sync.push_signal_from_site(
        site_signal_id=sid,
        owner_telegram_id=payload["owner_telegram_id"],
        coin=payload.get("coin"),
        direction=payload.get("direction"),
        note=payload.get("note", ""),
        channel=payload.get("channel", "alt"),
        risk_level=body.get("risk_level", "low"),
        created_at=payload.get("created_at"),
        display_name=session.get("display_name"),
        username=session.get("username"),
    )
    logger.info(
        f"SigNew: sid={sid} coin={payload.get('coin')} img={bool(payload.get('before_img'))} "
        f"by={payload['owner_telegram_id']} botSync={'ok' if synced else 'FAIL'}"
    )
    return web.json_response({"id": sid, "bot_synced": synced})


async def handle_signals_edit(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    if not _require_admin(request, body):
        return _json_error(403, "دسترسی فقط برای ادمین")

    signal_id = _path_int(request, "id")
    if signal_id is None:
        return _json_error(400, "شناسه سیگنال نامعتبر است")

    # ⚠️ فیکس: قبلاً کل بدنه به edit_signal پاس داده می‌شد. هر کلید اضافه‌ای
    # (مثل id یا token که فرانت‌اند ممکنه بفرسته) باعث ValueError و پاسخ ۴۰۰
    # برای یه ویرایش کاملاً معتبر می‌شد. الان فقط فیلدهای مجاز رد می‌شن.
    clean = {k: v for k, v in body.items() if k in signals._EDITABLE_FIELDS}
    if not clean:
        return _json_error(400, "هیچ فیلد قابل‌ویرایشی ارسال نشده")

    try:
        ok = signals.edit_signal(signal_id, **clean)
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
    signal_id = _path_int(request, "id")
    if signal_id is None:
        return _json_error(400, "شناسه سیگنال نامعتبر است")
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "invalid json")

    if not _require_owner_or_admin(request, signal_id, body):
        return _json_error(403, "فقط صاحب سیگنال یا ادمین")

    try:
        result_text = body.get("result", "")
        status = body.get("outcome_status", "open")
        ok = signals.set_result(signal_id, result_text, status)
    except (ValueError, AttributeError) as e:
        return _json_error(400, str(e))

    # نتیجه هم باید به ربات برسه، وگرنه امتیاز/استریک/لیدربورد ربات از
    # وب‌اپ عقب می‌مونه و دو طرف واگرا می‌شن.
    bot_synced = False
    if ok:
        from signal_bot.services import site_sync
        bot_synced = site_sync.push_result_from_site(signal_id, result_text, status)
    logger.info(
        f"SigResult: sid={signal_id} res={result_text} stat={status} "
        f"botSync={'ok' if bot_synced else 'skip'}"
    )

    # ⚠️ bot_synced قبلاً فقط تو لاگ سرور بود، نه تو پاسخ. اضافه کردنش به
    # پاسخ باعث می‌شه فرانت‌اند (و تست‌ها) بدون نیاز به خواندن لاگ سرور
    # بفهمن آیا سینک واقعاً انجام شده یا نه.
    return web.json_response({"ok": ok, "bot_synced": bot_synced}) if ok else _json_error(404, "signal not found")


async def handle_signals_delete(request: web.Request) -> web.Response:
    session = _require_admin(request)
    if not session:
        # ⚠️ لاگ تشخیصی: اگه حذف "کار نمی‌کنه" ولی هیچ خط SigDel ای تو لاگ
        # نیست، یعنی درخواست اصلاً به این نقطه نرسیده (مشکل سمت کلاینت —
        # مثلاً دیالوگ تأییدِ حذف نتونسته resolve بشه) نه اینکه سرور ردش کرده.
        # این خط اون دو حالت رو از هم جدا می‌کنه.
        logger.warning(f"SigDelDenied: path={request.path} hasAuthHeader={bool(request.headers.get('Authorization'))}")
        return _json_error(403, "دسترسی فقط برای ادمین")

    signal_id = _path_int(request, "id")
    if signal_id is None:
        return _json_error(400, "شناسه سیگنال نامعتبر است")
    from signal_bot.services import site_sync
    bot_del = site_sync.delete_from_site(signal_id)   # قبل از حذف سایت، تا لینک هنوز موجود باشه
    ok = signals.delete_signal(signal_id)
    logger.info(f"SigDel: sid={signal_id} ok={ok} botDel={'ok' if bot_del else 'FAIL'} by={session.get('telegram_id')}")
    return web.json_response({"ok": ok}) if ok else _json_error(404, "signal not found")


async def handle_leaderboard(request: web.Request) -> web.Response:
    from signal_bot.db import signals_repo

    period = request.query.get("period", "week")
    # ⚠️ فیکس منطقه‌ی زمانی: created_at همه‌جا با datetime.utcnow() نوشته
    # می‌شه، ولی این خط از datetime.now() (ساعت محلی سرور) استفاده می‌کرد.
    # روی یه سرور با ساعت محلی ایران (+۳:۳۰) پنجره‌ی «هفته» سه‌ساعت‌ونیم
    # جابه‌جا می‌شد و سیگنال‌های مرزی از لیدربورد می‌افتادن بیرون.
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    since = (now_utc - timedelta(days=7)).isoformat() if period == "week" else "2000-01-01"

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
    callers = ratings.get_top_callers(limit=10)
    # ⚠️ لاگ تشخیصی فشرده: اگه لیدربورد یه‌روز خالی یا عجیب دیده شد، این یه
    # خط کافیه بفهمی مشکل از «داده‌ای نیست» بوده یا «فیلتر since اشتباهه» —
    # بدون این، باید مستقیم رو دیتابیس کوئری می‌زدی.
    logger.info(f"LeaderboardDeliver: period={period} since={since} givers={len(signal_givers)} callers={len(callers)}")
    return web.json_response({
        "callers": callers,
        "signal_givers": signal_givers,
    })


# ================= مدیریت محتوای آکادمی =================

_ALLOWED_CONTENT_KEYS = {"articles", "strategies"}


async def handle_content_get(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    if key not in _ALLOWED_CONTENT_KEYS:
        return _json_error(404, "کلید نامعتبر است")
    value = kv.kv_get(key)
    return web.json_response(json.loads(value) if value else [])


async def handle_content_post(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    if key not in _ALLOWED_CONTENT_KEYS:
        return _json_error(404, "کلید نامعتبر است")

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error(400, "داده ارسالی نامعتبر است")

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


# ================= تشخیص و سلامت =================

async def handle_diag(request: web.Request) -> web.Response:
    """
    یه عکس فوری از وضعیت سیستم — فقط برای ادمین.

    چرا لازمه: تا حالا برای جواب دادن به سؤال ساده‌ی «چرا وب‌اپ منو ادمین
    نمی‌شناسه؟» باید لاگ‌ها رو دستی می‌خوندیم و حدس می‌زدیم. این اندپوینت
    همون سؤال رو با داده جواب می‌ده: سرور چه initData ای گرفته، آیدی رو از
    کجا خونده، این آیدی توی کدوم لیست ادمین هست، و فید چندتا ردیف داره.
    از داخل وب‌اپ با /site/diag و از داخل ربات با دستور /diag در دسترسه.
    """
    session = _require_admin(request)
    if not session:
        return _json_error(403, "دسترسی فقط برای ادمین")

    from signal_bot.config import settings
    from signal_bot.logger import log_stats

    uid = session.get("telegram_id")
    try:
        feed = signals.get_feed(limit=1)
        feed_total = feed.get("total", 0) if isinstance(feed, dict) else 0
    except Exception as e:
        feed_total = f"err: {e}"

    return web.json_response({
        "viewer": {
            "telegram_id": uid,
            "is_admin": session.get("is_admin"),
            "is_super_admin": session.get("is_super_admin"),
            "verified": not session.get("unverified"),
            "role": session.get("role"),
            "in_env_admin_ids": uid in [int(x) for x in settings.ADMIN_IDS],
            "in_staff_table": auth._is_staff_admin(int(uid)) if uid else False,
        },
        "request": {
            "has_bearer": bool(_get_session_from_request(request)),
            "has_init_header": bool(request.headers.get("X-Telegram-Init-Data")),
            "init_header_len": len(request.headers.get("X-Telegram-Init-Data", "")),
            "has_uid_header": bool(request.headers.get("X-Telegram-User-Id")),
        },
        "server": {
            "admin_ids_count": len(settings.ADMIN_IDS),
            "bot_token_set": bool(settings.TOKEN),
            "site_db": os.path.abspath(getattr(__import__("signal_bot.site.db", fromlist=["DB_FILE"]), "DB_FILE")),
            "bot_db": os.path.abspath(settings.DB_FILE),
            "sessions": auth.count_sessions(),
            "feed_total": feed_total,
            "html_path": _resolve_html_path(),
            "static_dir_exists": os.path.exists(_STATIC_DIR),
            "log": log_stats(),
        },
    })


def register(app: web.Application):
    app.router.add_get("/", handle_index)

    if os.path.exists(_STATIC_DIR):
        app.router.add_static("/static/", _STATIC_DIR, name="static")

    app.router.add_post("/site/client-log", handle_client_log)
    app.router.add_post("/site/upload", handle_image_upload)
    app.router.add_post("/webapp-auth", handle_webapp_auth)
    app.router.add_post("/site/auth", handle_webapp_auth)
    app.router.add_post("/site/webapp-auth", handle_webapp_auth)
    app.router.add_get("/site/session", handle_session)
    app.router.add_get("/site/diag", handle_diag)
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