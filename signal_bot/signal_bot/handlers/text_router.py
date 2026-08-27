"""
تنها MessageHandler متنی ربات. چون مسیر تشخیص مرحله (step) از context.chat_data
میاد نه از خود متن پیام، نمی‌شه مثل CallbackQueryHandlerها با pattern جداشون کرد؛
به‌جاش یک dict-dispatch تمیز به‌جای if/elif غول‌پیکر قبلی استفاده شده — هر مرحله
دقیقاً به تابع صاحب دامنه‌ی خودش (signals/payments/admin) delegate می‌شه.

⚠️ عمداً از context.chat_data استفاده می‌شه، نه context.user_data — چون user_data
بین همه‌ی چت‌های یک کاربر (دایرکت + هر گروهی) مشترکه و باعث نشتِ state بین چت‌های
غیرمرتبط می‌شه (برای جزئیات، کامنت بالای handlers/signals.py رو ببین).
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from signal_bot.config.settings import ADMIN_IDS
from signal_bot.db import users_repo

logger = logging.getLogger(__name__)
from signal_bot.handlers import signals as signals_handlers
from signal_bot.handlers import payments as payments_handlers
from signal_bot.handlers import support as support_handlers
from signal_bot.handlers import admin as admin_handlers

STEP_HANDLERS = {
    # Full Signal متنی (بند ۴ — وقتی به‌جای عکس، متن می‌فرسته)
    "full_content":       signals_handlers.handle_step_full_content,
    # Fast Call (بند ۴ — بدون Entry/TP)
    "fast_coin":          signals_handlers.handle_step_fast_coin,
    # پرداخت
    "donate_custom":      payments_handlers.handle_step_donate_custom,
    # حمایت مستقیم از تحلیلگر (بند ۱۳)
    "support_custom":     support_handlers.handle_step_support_custom,
    # ادمین
    "broadcast":          admin_handlers.handle_step_broadcast,
    "find_user":          admin_handlers.handle_step_find_user,
    "set_pts":            admin_handlers.handle_step_set_pts,
    "grant_reward":       admin_handlers.handle_step_grant_reward,
    "endseason_confirm":  admin_handlers.handle_step_endseason_confirm,
    "admin_fix_result_id": admin_handlers.handle_step_admin_fix_result_id,
}


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_repo.register_user(user.id, user.username, user.full_name)
    if users_repo.is_blocked(user.id) and user.id not in ADMIN_IDS:
        return

    step = context.chat_data.get("signal_step") or context.chat_data.get("step")
    text = update.message.text.strip()

    handler_fn = STEP_HANDLERS.get(step)
    if handler_fn:
        await handler_fn(update, context, user, text)
    elif step:
        # step ست شده ولی تو STEP_HANDLERS نیست (مثلاً تایپوی آینده تو یه هندلر) —
        # برخلاف unhandled_callback که این حالت رو لاگ می‌کرد، این‌جا قبلاً کاملاً
        # بی‌صدا بود. عمداً step=None (یعنی هیچ فلوی فعالی نیست، رایج‌ترین حالته) رو
        # لاگ نمی‌کنیم تا لاگ شلوغ نشه.
        logger.warning(f"unhandled text step: {step!r} (user_id={user.id})")
