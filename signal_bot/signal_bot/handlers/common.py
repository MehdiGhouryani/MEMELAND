"""
هندلرهای مشترک بین همه‌ی دامنه‌ها:
- start
- cmd_help: دستور /help عمومی (برای همه‌ی کاربران، گروه یا دایرکت)
- guard_callback: preamble مشترک همه‌ی CallbackQueryHandlerها (answer + چک بلاک)
- ناوبری مشترک: back_main و cancel
- unhandled_callback: fallback دفاعی برای callback_data ناشناخته
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from signal_bot.config.settings import SEP
from signal_bot.db import users_repo, signals_repo
from signal_bot.services import scoring, access
from signal_bot.keyboards.keyboards import main_menu_kb, caller_menu_kb, back_main_kb
from signal_bot.utils import esc


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_repo.register_user(user.id, user.username, user.full_name)
    if users_repo.is_blocked(user.id):
        await update.message.reply_text("⛔️  دسترسی شما مسدود شده.")
        return

    # تو گروه، منوی دکمه‌ای (تعاملی) نشون داده نمی‌شه — چون دکمه‌هاش از طریق
    # guard_callback فقط تو دایرکت جواب می‌دن (رجوع کن به کامنت guard_callback).
    # به‌جاش یه راهنمای کوتاه گروه‌محور می‌فرستیم.
    if update.effective_chat.type != "private":
        bot_username = context.bot.username or ""
        dm_hint = f"@{esc(bot_username)}" if bot_username else "بهم دایرکت پیام بده"
        await update.message.reply_html(
            f"سلام <b>{esc(user.first_name)}</b>! 👋\n\n"
            f"منوی کامل (پروفایل، لیدربورد، استخر جایزه، پنل ادمین و...) فقط "
            f"تو دایرکت کار می‌کنه — {dm_hint} رو با /start پیام بده.\n\n"
            f"همینجا تو گروه هم می‌تونی مستقیم سیگنال ثبت کنی:\n"
            f"<code>/fastcall کوین [long/short]</code>\n"
            f"<code>/fullsignal [کوین] [جهت] [توضیح]</code>"
        )
        return

    is_admin      = access.is_admin(user.id)
    is_vip_helper = access.is_vip_helper(user.id)
    is_signal_giver = signals_repo.has_any_signal(user.id)
    pts   = users_repo.get_total_pts(user.id)
    level = scoring.get_level(pts)
    role_label = access.get_role_label(users_repo.get_role(user.id))
    await update.message.reply_html(
        f"سلام <b>{esc(user.first_name)}</b>! 👋\n\n"
        f"به <b>Signal Master</b> خوش اومدی 🎯\n"
        f"🎖  درجه: {role_label}\n"
        f"📶  سطح فعلی: {level}\n\n"
        f"{SEP}\n"
        f"📡  سیگنال ثبت کن — امتیاز بگیر\n"
        f"🏆  در لیدربورد بالا برو\n"
        f"💎  از استخر جایزه سهیم شو\n"
        f"🔥  استریک بساز — بونوس بگیر\n"
        f"{SEP}\n\n"
        f"از منو زیر شروع کن 👇",
        reply_markup=main_menu_kb(is_admin, is_vip_helper, is_signal_giver)
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help — برای همه‌ی کاربران، هم تو گروه هم دایرکت. صرفاً اطلاع‌رسانیه،
    پس برخلاف بقیه‌ی دستورها حتی برای کاربر بلاک‌شده هم نمایش داده می‌شه
    (هیچ اقدامی انجام نمی‌ده، فقط متن نشون می‌ده).
    """
    user = update.effective_user
    users_repo.register_user(user.id, user.username, user.full_name)
    role_lines = access.get_role_limits_lines()
    await update.message.reply_html(
        f"<b>📖  راهنمای Signal Master</b>\n{SEP}\n\n"
        f"📸  <b>Full Signal</b> — عکس تحلیلت رو بفرست (یا بدون عکس، متنی بنویس)\n"
        f"⚡  <b>Fast Call</b> — فقط معرفی سریع یه کوین/توکن، بدون Entry/TP\n"
        f"{SEP}\n"
        f"💬  <b>دستور (تو گروه یا دایرکت)</b>\n"
        f"<code>/fastcall کوین [long/short]</code>\n"
        f"مثال: <code>/fastcall PEPE long</code>\n\n"
        f"<code>/fullsignal [کوین] [جهت] [توضیح]</code>\n"
        f"یا عکس رو با کپشن <code>/fullsignal</code> بفرست\n"
        f"{SEP}\n"
        f"📋  <b>قوانین</b>\n"
        f"•  سیگنال Rookie/Explorer قبل از انتشار باید Admin یا VIP Helper تأییدش کنه\n"
        f"•  سیگنال Guardian و بالاتر مستقیم منتشر می‌شه (بدون نیاز به تأیید)\n"
        f"•  محدودیت ثبت روزانه بر اساس درجه‌ته (درجه‌ی بالاتر = سقف بیشتر)\n"
        f"•  نتیجه‌ی برد/باخت رو خودت (از «🎯 ثبت نتیجه سیگنالم») یا ادمین ثبت می‌کنه\n"
        f"{SEP}\n"
        f"🎖  <b>سقف سیگنال روزانه هر درجه</b>\n"
        f"{role_lines}\n"
        f"درجه‌ها فقط دستی و توسط ادمین ارتقا پیدا می‌کنن.\n"
        f"{SEP}\n"
        f"👤  برای منوی کامل (پروفایل، لیدربورد، استخر جایزه و...) بهم پیام بده: /start"
    )


async def guard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    preamble مشترک همه‌ی هندلرهای دکمه: answer کردن کوئری + چک کاربر بلاک‌شده +
    چک نوع چت. خروجی: (q, user, is_admin, is_vip_helper) در صورت مجاز بودن، یا
    None اگه کاربر بلاک باشه یا تو گروه بزنه (که در این حالت خودش پیام رد
    دسترسی/راهنما رو نشون داده و هندلر فراخواننده باید فوراً return کنه).

    ⚠️ چرا چک گروه لازم بود (باگ امنیتی واقعی): تمام مراحل میانیِ فلوهای
    چندمرحله‌ای (منتظر عکس، منتظر مبلغ دلخواه، منتظر پیام همگانی و...) توی
    context.chat_data ذخیره می‌شن که *مخصوص یک چته، نه یک کاربر*. یعنی تو یک
    گروه، اگه کاربر A روی «📸 Full Signal» بزنه، chat_data["signal_step"] برای
    *کل گروه* ست می‌شه — و اگه کاربر B (کاملاً بی‌ربط) بلافاصله بعدش هر پیامی
    بفرسته، به‌اشتباه به‌عنوان ادامه‌ی فلوی کاربر A پردازش می‌شه (و امتیاز/سیگنال
    به نام B ثبت می‌شه، نه A). راه‌حل ریشه‌ای (نه پچ‌کردن هر فلو جداگانه): کل
    منوی تعاملی (دکمه‌محور) رو فقط تو دایرکت فعال کردیم؛ تو گروه فقط دستورهای
    یک‌پیامیِ بدون state (/fastcall، /fullsignal) کار می‌کنن که این ریسک رو
    اصلاً ندارن.
    """
    q    = update.callback_query
    await q.answer()
    user = q.from_user
    is_admin      = access.is_admin(user.id)
    is_vip_helper = access.is_vip_helper(user.id)
    if users_repo.is_blocked(user.id) and not is_admin:
        await q.answer("⛔️ دسترسی شما مسدود شده!", show_alert=True)
        return None
    if update.effective_chat.type != "private":
        await q.answer("💬  این منو فقط تو دایرکت کار می‌کنه — بهم پیام بده: /start",
                       show_alert=True)
        return None
    return q, user, is_admin, is_vip_helper


async def common_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر back_main، cancel، و menu_caller_hub — پترن: ^(back_main|cancel|menu_caller_hub)$"""
    guard = await guard_callback(update, context)
    if guard is None:
        return
    q, user, is_admin, is_vip_helper = guard
    data = q.data

    if data == "back_main":
        is_signal_giver = signals_repo.has_any_signal(user.id)
        await q.edit_message_text(
            "🏠  <b>منوی اصلی</b>\n\nیه گزینه انتخاب کن 👇",
            reply_markup=main_menu_kb(is_admin, is_vip_helper, is_signal_giver), parse_mode=ParseMode.HTML
        )
    elif data == "menu_caller_hub":
        # فاز ۲: قبلاً استخر جایزه/سیگنال‌هام/ثبت‌نتیجه مستقیم تو منوی اصلی
        # بودن؛ حالا این‌جا جمع شدن — چون فقط برای کسی معنی دارن که سیگنال
        # می‌ده. is_admin هم می‌تونه ببینتش (رجوع کن به main_menu_kb).
        await q.edit_message_text(
            "🎙️  <b>منوی سیگنال‌دهنده</b>\n\nیه گزینه انتخاب کن 👇",
            reply_markup=caller_menu_kb(), parse_mode=ParseMode.HTML
        )
    elif data == "cancel":
        context.chat_data.clear()
        await q.edit_message_text("لغو شد ❌", reply_markup=back_main_kb())


async def unhandled_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    fallback دفاعی: اگه دکمه‌ای callback_data داشته باشه که با هیچ‌کدوم از
    پترن‌های ثبت‌شده مچ نشه (مثلاً یه فیچر جدید که هندلرش هنوز اضافه نشده)،
    حداقل کرش نمی‌کنه و توی لاگ ثبت می‌شه.
    """
    q = update.callback_query
    await q.answer()
    logging.warning(f"callback_data ناشناخته: {q.data!r} از کاربر {q.from_user.id}")
