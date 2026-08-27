"""
سرور وب داخلی بات (aiohttp) — سه مسیر: وب‌هوک IPN نوپیمنتس، تأیید initData
تلگرام WebApp (services/webapp_auth.py)، و کل بک‌اند سایت (site/routes.py:
سرو کردن HTML + auth + CRUD سیگنال/امتیاز/محتوا).

⚠️ اسم فایل (ipn_server.py) میراث دورانیه که فقط IPN بود؛ عمداً rename نشده
که diff بزرگ نشه — فقط توابعش عمومی‌تر شدن (create_web_app/start_web_server).

فقط مسیر IPN شرطیه (اگه NOWPAYMENTS_IPN_SECRET خالی باشه، فقط IPN غیرفعاله).
بک‌اند سایت/webapp-auth همیشه فعالن — به هیچ سرویس بیرونی نیاز ندارن، چون
SQLite محلیه.
"""
import json
import logging

from aiohttp import web

from signal_bot.config import settings
from signal_bot.services import webapp_auth
from signal_bot.site import auth as site_auth
from signal_bot.site import routes as site_routes
from signal_bot.db import prize_repo, caller_donations_repo
from signal_bot.services.ipn_signature import verify_signature
from signal_bot.services.notify import safe_send_message

STATUS_MAP = {"finished": "paid", "confirmed": "paid", "sending": "paid",
              "expired": "failed", "failed": "failed"}


async def _handle_pool_payment(bot, order_id, payment_id, new_status):
    row = prize_repo.get_donation_by_order_id(order_id)
    if not row:
        logging.warning(f"IPN: سفارش استخر جایزه با order_id={order_id} پیدا نشد")
        return False
    donate_id, user_id, current_status = row
    if payment_id:
        prize_repo.set_payment_id(donate_id, payment_id)
    if new_status == "paid" and current_status != "paid":
        prize_repo.set_donation_paid(donate_id)
        await safe_send_message(bot, chat_id=user_id,
            text="✅  <b>پرداخت شما به استخر جایزه تأیید شد!</b>\n\nممنون از حمایتت 🙏",
            parse_mode="HTML")
        for admin_id in settings.ADMIN_IDS:
            await safe_send_message(bot, chat_id=admin_id,
                text=f"💰  <b>پرداخت خودکار تأیید شد (وب‌هوک)!</b>\n👤 {user_id}\nسفارش: {order_id}",
                parse_mode="HTML")
    return True


async def _handle_support_payment(bot, order_id, payment_id, new_status):
    row = caller_donations_repo.get_donation_by_order_id(order_id)
    if not row:
        logging.warning(f"IPN: سفارش حمایت مستقیم با order_id={order_id} پیدا نشد")
        return False
    donate_id, donor_id, recipient_id, amount, current_status = row
    if payment_id:
        caller_donations_repo.set_payment_id(donate_id, payment_id)
    if new_status == "paid" and current_status != "paid":
        caller_donations_repo.set_donation_paid(donate_id)
        await safe_send_message(bot, chat_id=donor_id,
            text=f"✅  <b>حمایت {amount}$ شما تأیید شد!</b>\n\nممنون 🙏", parse_mode="HTML")
        await safe_send_message(bot, chat_id=recipient_id,
            text=f"💝  <b>یه نفر ازت حمایت کرد!</b>\n💵 {amount}$\n\nهمینطوری ادامه بده! 🚀",
            parse_mode="HTML")
        for admin_id in settings.ADMIN_IDS:
            await safe_send_message(bot, chat_id=admin_id,
                text=f"💝  <b>حمایت مستقیم تأیید شد (وب‌هوک)!</b>\nسفارش: {order_id}", parse_mode="HTML")
    return True


async def _handle_webapp_auth(request: web.Request) -> web.Response:
    """initData رو تأیید می‌کنه و مستقیماً یه session تو SQLite سایت می‌سازه."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return web.Response(status=400, text="invalid json")

    init_data = body.get("init_data", "")
    user = webapp_auth.verify_init_data(init_data, settings.TOKEN)
    if not user:
        logging.warning("webapp-auth: initData نامعتبر یا امضای غلط — رد شد")
        return web.Response(status=401, text="invalid init_data")

    token = site_auth.create_session(
        user["id"], username=user.get("username"), first_name=user.get("first_name"),
        photo_url=user.get("photo_url"),
    )
    return web.json_response({"token": token})


def create_web_app(bot) -> web.Application:
    """ساخت اپلیکیشن aiohttp با ۳ دسته مسیر: IPN، webapp-auth، و کل بک‌اند
    سایت (site/routes.py — سرو کردن HTML + auth + CRUD سیگنال). site همیشه
    ثبت می‌شه (دیگه به هیچ کلید Supabase نیاز نداره)؛ IPN فقط اگه سکرتش ست باشه."""

    async def handle_ipn(request: web.Request) -> web.Response:
        raw_body = await request.read()
        signature = request.headers.get("x-nowpayments-sig", "")

        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.warning(f"IPN: بدنه‌ی نامعتبر JSON دریافت شد: {e}")
            return web.Response(status=400, text="invalid json")

        if not verify_signature(payload, signature, settings.NOWPAYMENTS_IPN_SECRET):
            logging.warning("IPN: امضای نامعتبر — درخواست رد شد (شاید جعلی یا سکرت اشتباه)")
            return web.Response(status=401, text="invalid signature")

        order_id   = str(payload.get("order_id", ""))
        payment_id = str(payload.get("payment_id", "")) or None
        raw_status = payload.get("payment_status", "")
        new_status = STATUS_MAP.get(raw_status, "pending")

        try:
            if order_id.startswith("pool_"):
                found = await _handle_pool_payment(bot, order_id, payment_id, new_status)
            elif order_id.startswith("support_"):
                found = await _handle_support_payment(bot, order_id, payment_id, new_status)
            else:
                logging.warning(f"IPN: order_id با پیشوند ناشناخته: {order_id!r}")
                return web.Response(status=200, text="ignored: unknown order_id prefix")
        except Exception as e:
            # هر خطای غیرمنتظره‌ای (DB، تلگرام و...) رو لاگ می‌کنیم ولی همچنان 200
            # برمی‌گردونیم تا NOWPayments دوباره و دوباره retry نکنه برای چیزی که
            # از سمت ما قابل حل نیست بدون بررسی دستی؛ خطا از لاگ قابل پیگیریه.
            logging.error(f"IPN: خطای غیرمنتظره در پردازش order_id={order_id}: {e}")
            return web.Response(status=200, text="error logged")

        if not found:
            return web.Response(status=200, text="ignored: order not found locally")
        return web.Response(status=200, text="OK")

    # ⚠️ پیش‌فرض aiohttp برای سایز بدنه‌ی درخواست ۱ مگابایته — تا قبل از فیچر
    # آپلود عکس قبل/بعد هیچ‌وقت مهم نبود (بقیه‌ی بدنه‌ها همه JSON کوچیکن). یه
    # عکس base64 (که ~۳۳٪ حجم بیشتر از باینری خامشه) به‌راحتی از ۱ مگابایت رد
    # می‌شه؛ با تست واقعی هم تأیید شد: بدون این خط، درخواست قبل از رسیدن به
    # چک ۶ مگابایتیِ خودمون تو routes.py، با خطای عمومی aiohttp رد می‌شد.
    app = web.Application(client_max_size=10 * 1024 * 1024)
    if settings.NOWPAYMENTS_IPN_SECRET:
        app.router.add_post(settings.IPN_WEBHOOK_PATH, handle_ipn)
    # بک‌اند سایت (HTML + auth + سیگنال‌ها) و webapp-auth همیشه ثبت می‌شن —
    # از وقتی پیوت به SQLite انجام شد، دیگه به هیچ کلید Supabase نیازی ندارن،
    # فقط site.db.init_db() لازمه که قبلش صدا زده شده باشه (main.py).
    app.router.add_post(settings.WEBAPP_AUTH_PATH, _handle_webapp_auth)
    site_routes.register(app)
    return app


async def start_web_server(bot):
    """
    از پیوت به SQLite به بعد، این سرور همیشه بالا میاد (بک‌اند سایت به هیچ
    سرویس بیرونی نیاز نداره) — فقط مسیر IPN شرطیه. فراخواننده (main.py)
    باید runner رو نگه داره تا موقع خاموش‌شدن ربات cleanup کنه.
    """
    ipn_on = bool(settings.NOWPAYMENTS_IPN_SECRET)
    if not ipn_on:
        logging.info("NOWPAYMENTS_IPN_SECRET تنظیم نشده — فقط IPN غیرفعاله، بک‌اند سایت/webapp-auth عادی فعالن.")

    app = create_web_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.IPN_WEBHOOK_HOST, settings.IPN_WEBHOOK_PORT)
    await site.start()
    routes = ["/", settings.WEBAPP_AUTH_PATH, "/site/*"]
    if ipn_on:
        routes.append(settings.IPN_WEBHOOK_PATH)
    logging.info(f"سرور وب بات روی {settings.IPN_WEBHOOK_HOST}:{settings.IPN_WEBHOOK_PORT} استارت شد — مسیرها: {routes}")
    return runner
