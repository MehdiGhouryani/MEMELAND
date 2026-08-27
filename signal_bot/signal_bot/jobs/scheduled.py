"""جاب‌های زمان‌بندی‌شده (JobQueue)."""
from datetime import datetime, timedelta

from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from signal_bot.config.settings import CHANNEL_ID
from signal_bot.db import signals_repo
from signal_bot.formatters.texts import leaderboard_text
from signal_bot.services.notify import safe_send_message


async def daily_leaderboard_post(context: ContextTypes.DEFAULT_TYPE):
    """هر شب ساعت ۲۲ لیدربورد توی کانال پست میشه"""
    if not CHANNEL_ID:
        return
    text = leaderboard_text("week")
    await safe_send_message(context.bot, chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)


async def notify_rank_changes(context: ContextTypes.DEFAULT_TYPE):
    """
    هر ۶ ساعت رتبه‌ها چک میشه.

    ⚠️ همون‌طور که در بررسی اولیه گفته شد: این جاب فعلاً فقط داده رو می‌خونه
    و هیچ مقایسه‌ای با وضعیت قبلی یا ارسال پیامی انجام نمی‌ده (این باگ از
    نسخه قبلی به همین شکل منتقل شده — چون فاز ۱ فقط ساختار رو عوض می‌کنه،
    نه رفتار رو). پیاده‌سازی واقعی این قابلیت به یکی از فازهای بعدی موکول شده.
    """
    since = (datetime.now() - timedelta(days=7)).isoformat()
    signals_repo.get_rank_changes_since(since)
