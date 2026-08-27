"""
دامنه پروفایل/لیدربورد: لیدربورد هفتگی/ماهانه/کل، آمار من، پروفایل، تابلوی افتخار، پاداش‌های من.
پترن ثبت‌نام: ^(menu_leader|leader_week|leader_month|leader_all|menu_stats|menu_profile|menu_halloffame|menu_myrewards)$
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from signal_bot.formatters.texts import leaderboard_text, user_stats_text, hall_of_fame_text, my_rewards_text
from signal_bot.keyboards.keyboards import leader_kb, back_main_kb
from signal_bot.handlers.common import guard_callback


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guard = await guard_callback(update, context)
    if guard is None:
        return
    q, user, is_admin, is_vip_helper = guard
    data = q.data

    if data in ("menu_leader", "leader_week"):
        await q.edit_message_text(leaderboard_text("week"), reply_markup=leader_kb("week"), parse_mode=ParseMode.HTML)
    elif data == "leader_month":
        await q.edit_message_text(leaderboard_text("month"), reply_markup=leader_kb("month"), parse_mode=ParseMode.HTML)
    elif data == "leader_all":
        await q.edit_message_text(leaderboard_text("all"), reply_markup=leader_kb("all"), parse_mode=ParseMode.HTML)
    elif data in ("menu_stats", "menu_profile"):
        await q.edit_message_text(user_stats_text(user.id), reply_markup=back_main_kb(), parse_mode=ParseMode.HTML)
    elif data == "menu_halloffame":
        await q.edit_message_text(hall_of_fame_text(), reply_markup=back_main_kb(), parse_mode=ParseMode.HTML)
    elif data == "menu_myrewards":
        await q.edit_message_text(my_rewards_text(user.id), reply_markup=back_main_kb(), parse_mode=ParseMode.HTML)
