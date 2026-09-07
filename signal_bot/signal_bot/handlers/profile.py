"""
دامنه پروفایل/لیدربورد: لیدربورد هفتگی/ماهانه/کل، آمار من، پروفایل، تابلوی افتخار، پاداش‌های من.
پترن ثبت‌نام: ^(menu_leader|leader_week|leader_month|leader_all|menu_stats|menu_profile|menu_profile_details|menu_halloffame|menu_myrewards)$

فاز ۱ (بازبینی UX): لیدربورد/تابلوی افتخار/پاداش‌های من (+ استخر جایزه، تو
payments.py) الان همه از یه کیبورد مشترک تب‌دار (ranking_hub_kb) استفاده
می‌کنن تا از هرکدوم بشه مستقیم به بقیه رفت، نه فقط برگشت به منوی اصلی.
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from signal_bot.formatters.texts import leaderboard_text, user_stats_text, hall_of_fame_text, my_rewards_text, profile_headline_text
from signal_bot.keyboards.keyboards import ranking_hub_kb, back_main_kb, profile_headline_kb
from signal_bot.handlers.common import guard_callback


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guard = await guard_callback(update, context)
    if guard is None:
        return
    q, user, is_admin, is_vip_helper = guard
    data = q.data

    if data in ("menu_leader", "leader_week"):
        await q.edit_message_text(leaderboard_text("week", user.id), reply_markup=ranking_hub_kb("leader", "week"), parse_mode=ParseMode.HTML)
    elif data == "leader_month":
        await q.edit_message_text(leaderboard_text("month", user.id), reply_markup=ranking_hub_kb("leader", "month"), parse_mode=ParseMode.HTML)
    elif data == "leader_all":
        await q.edit_message_text(leaderboard_text("all", user.id), reply_markup=ranking_hub_kb("leader", "all"), parse_mode=ParseMode.HTML)
    elif data in ("menu_stats", "menu_profile"):
        await q.edit_message_text(profile_headline_text(user.id), reply_markup=profile_headline_kb(), parse_mode=ParseMode.HTML)
    elif data == "menu_profile_details":
        await q.edit_message_text(user_stats_text(user.id), reply_markup=back_main_kb(), parse_mode=ParseMode.HTML)
    elif data == "menu_halloffame":
        await q.edit_message_text(hall_of_fame_text(), reply_markup=ranking_hub_kb("halloffame"), parse_mode=ParseMode.HTML)
    elif data == "menu_myrewards":
        await q.edit_message_text(my_rewards_text(user.id), reply_markup=ranking_hub_kb("myrewards"), parse_mode=ParseMode.HTML)
