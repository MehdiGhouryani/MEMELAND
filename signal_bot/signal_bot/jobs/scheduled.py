"""جاب‌های زمان‌بندی‌شده (JobQueue)."""
from datetime import datetime, timedelta

from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from signal_bot.config.settings import CHANNEL_ID
from signal_bot.db import signals_repo
from signal_bot.formatters.texts import leaderboard_text
from signal_bot.services.notify import safe_send_message
from signal_bot.services.price_feed import get_current_prices
from signal_bot.site import signals as site_signals


async def daily_leaderboard_post(context: ContextTypes.DEFAULT_TYPE):
    """هر شب ساعت ۲۲ لیدربورد توی کانال پست میشه"""
    if not CHANNEL_ID:
        return
    text = leaderboard_text("week")
    await safe_send_message(context.bot, chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)


async def check_entry_alerts(context: ContextTypes.DEFAULT_TYPE):
    """هر ۴۵ ثانیه: سیگنال‌های باز با chain+contract_address+entry_price رو چک
    می‌کنه، قیمت لحظه‌ای می‌گیره (services/price_feed — GeckoTerminal اصلی،
    DexScreener پشتیبان)، و اگه قیمت به ورود رسیده باشه یه‌بار تو CHANNEL_ID
    آلارم می‌ده (entry_alert_sent جلوی تکرار رو می‌گیره).
    direction='long' یعنی ورود = خرید افت‌قیمت → آلارم وقتی قیمت <= entry.
    direction='short' برعکس → آلارم وقتی قیمت >= entry.
    خطای هر API/عدم تنظیم CHANNEL_ID فقط لاگ می‌شه، جاب کرش نمی‌کنه."""
    if not CHANNEL_ID:
        return
    eligible = site_signals.get_alert_eligible_signals()
    if not eligible:
        return
    prices = await get_current_prices(eligible)
    for sig in eligible:
        price = prices.get((sig["chain"], sig["contract_address"].lower()))
        if price is None:
            continue
        entry = sig["entry_price"]
        # direction نبود/چیز دیگه‌ای بود -> پیش‌فرض 'long' (رایج‌ترین حالت تو این پروژه).
        hit = price >= entry if sig["direction"] == "short" else price <= entry
        if not hit:
            continue
        text = (f"🔔 <b>{sig['coin'] or 'سیگنال'}</b> به قیمت ورود رسید!\n"
                f"قیمت لحظه‌ای: <code>{price}</code> — ورود: <code>{entry}</code>")
        if await safe_send_message(context.bot, chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML):
            site_signals.mark_entry_alert_sent(sig["id"])


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
