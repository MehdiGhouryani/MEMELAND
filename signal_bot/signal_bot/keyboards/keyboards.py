"""همه‌ی کیبوردهای inline ربات، یک‌جا."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from signal_bot.config.settings import RESULT_LABEL, POINT_TABLE, ROLES, SITE_URL, CHANNELS


def btn(text, cb, style=None):
    # نکته: تلگرام از رنگی‌کردن دکمه‌های inline پشتیبانی نمی‌کنه.
    # پارامتر style قبلاً مستقیم به InlineKeyboardButton پاس داده می‌شد
    # که با TypeError کرش می‌کرد. امضای تابع رو نگه داشتیم (برای سازگاری با
    # همه‌ی call siteهای موجود)، ولی دیگه style به تلگرام پاس داده نمی‌شه.
    return InlineKeyboardButton(text, callback_data=cb)


def main_menu_kb(is_admin=False, is_vip_helper=False, is_signal_giver=False):
    """⚠️ فاز ۲: استخر جایزه/سیگنال‌هام/ثبت‌نتیجه از این منو به caller_menu_kb
    منتقل شدن — طبق گفته‌ی شریک، اینا فقط برای کسی معنی دارن که سیگنال
    می‌ده، و منوی اصلی باید رو «استفاده از سیگنال‌های موجود» تمرکز کنه، نه
    «تو هم می‌تونی سیگنال بدی». callback_data هرکدوم دست‌نخورده مونده، پس
    هندلرهای موجودشون بدون تغییر کار می‌کنن.
    is_signal_giver: هر کاربری که حداقل یه سیگنال ثبت کرده (یا ادمینه) —
    فقط اونا دکمه‌ی «منوی سیگنال‌دهنده» رو می‌بینن."""
    # فاز ۰ (بازبینی UX): «ثبت سیگنال» از اولین/برجسته‌ترین دکمه به ردیف
    # پایین‌تر منتقل شد — چون این دکمه برای همه (حتی کسی که فقط مصرف‌کننده‌ی
    # سیگنالِ دیگرانه) نمایش داده می‌شه، و اولین برخورد کاربر با منو باید
    # «مصرف سیگنال‌های موجود» باشه نه «تو هم سیگنال بده» (طبق همون فلسفه‌ای
    # که فاز ۲ برای جدا کردن caller_menu_kb ازش استفاده کرد).
    # فاز ۱ (بازبینی UX): «لیدربورد» به یه هاب مشترک تبدیل شد که تابلوی
    # افتخار/پاداش‌های من/استخر جایزه رو هم به‌صورت تب زیر خودش داره
    # (رجوع کن به ranking_hub_kb) — پس دیگه لازم نیست این‌ها ردیف‌های
    # جدا و غیرمجاور تو منوی اصلی باشن.
    kb = [
        [btn("📶  سیگنال‌های فعال","menu_activesignals","success"),
         btn("🏆  رتبه‌بندی و جوایز",   "menu_leader", "primary")],
    ]
    # دکمه‌ی WebApp فقط تو چت خصوصی کار می‌کنه (محدودیت خودِ تلگرام) — مشکلی
    # نیست چون main_menu_kb از قبل فقط تو DM صدا زده می‌شه (رجوع کن به
    # guard_callback). اگه SITE_URL خالی باشه (تنظیم نشده)، دکمه اصلاً نشون
    # داده نمی‌شه، نه این‌که با URL خالی کرش کنه.
    # عمداً InlineKeyboardButton مستقیم، نه btn() — چون btn() همیشه callback_data
    # ست می‌کنه و تلگرام اجازه نمی‌ده یه دکمه هم callback_data هم web_app داشته باشه.
    if SITE_URL:
        kb.append([InlineKeyboardButton("🌐  ورود به Memeland Hub", web_app=WebAppInfo(url=SITE_URL))])
    kb += [
        [btn("📊  آمار من",    "menu_stats",  "primary"),
         btn("👤  پروفایل",    "menu_profile","primary")],
        [btn("📡  ثبت سیگنال", "menu_signal", "success"),
         btn("🤝  حمایت از ما","menu_donate", "success")],
    ]
    if is_signal_giver or is_admin:
        kb.append([btn("🎙️  منوی سیگنال‌دهنده", "menu_caller_hub", "primary")])
    if is_admin:
        kb.append([btn("⚙️  پنل ادمین", "menu_admin", "danger")])
    elif is_vip_helper:
        kb.append([btn("📋  بررسی سیگنال‌ها (VIP Helper)", "adm_pending", "primary")])
    return InlineKeyboardMarkup(kb)


def caller_menu_kb():
    """فاز ۲: منوی مخصوص کسی که سیگنال می‌ده — استخر جایزه/سیگنال‌هام/
    ثبت‌نتیجه که قبلاً تو منوی اصلی بودن، الان اینجان."""
    return InlineKeyboardMarkup([
        [btn("📜  سیگنال‌هام", "menu_mysignals", "primary"),
         btn("🎯  ثبت نتیجه سیگنالم","menu_myresults","success")],
        [btn("💎  استخر جایزه","menu_prize",  "primary")],
        [btn("🔙  بازگشت", "back_main", "secondary")],
    ])


def back_main_kb():
    return InlineKeyboardMarkup([[btn("🔙  برگشت به منو", "back_main", "primary")]])


def cancel_kb():
    """برای مراحل میانی یک فلو (مثلاً منتظر عکس/متن) — بر خلاف back_main، state رو هم پاک می‌کنه."""
    return InlineKeyboardMarkup([[btn("🔙  لغو", "cancel", "primary")]])


def signal_menu_kb():
    return InlineKeyboardMarkup([
        [btn("📸  Full Signal", "sigtype_full", "success")],
        [btn("⚡  Fast Call",   "sigtype_fast", "primary")],
        [btn("🔙  برگشت",       "back_main",    "primary")],
    ])


def channel_picker_kb():
    """قدم تازه‌ی انتخاب کانال — بین انتخاب نوع سیگنال (sigtype_full/fast) و
    پرسیدن محتوا/کوین قرار می‌گیره. callback_dataها با ch_ شروع می‌شن."""
    rows = [[btn(label, f"ch_{key}", "primary")] for key, label in CHANNELS]
    rows.append([btn("🔙  لغو", "cancel", "primary")])
    return InlineKeyboardMarkup(rows)


def direction_kb():
    """انتخاب جهت برای Fast Call — اختیاری، قابل رد کردن."""
    return InlineKeyboardMarkup([
        [btn("🟢  LONG  (خرید)", "dir_LONG",  "success"),
         btn("🔴  SHORT (فروش)", "dir_SHORT", "danger")],
        [btn("⏭  رد کردن جهت", "fastcall_skipdir", "primary")],
        [btn("🔙  لغو", "cancel", "primary")],
    ])


def admin_kb():
    return InlineKeyboardMarkup([
        [btn("📋 سیگنال‌های در انتظار","adm_pending","primary"),
         btn("🎯 ثبت نتیجه",           "adm_result", "success")],
        [btn("🔧 اصلاح نتیجه (با شماره)","adm_fixresult","primary")],
        [btn("💰 واریزهای اخیر",      "adm_donations","primary"),
         btn("📢 پیام همگانی",         "adm_broadcast","primary")],
        [btn("📊 آمار کلی",           "adm_stats",   "primary"),
         btn("👥 مدیریت کاربران",     "adm_users",   "primary")],
        [btn("🏆 پایان دوره و جایزه", "adm_endseason","danger"),
         btn("📤 خروجی اکسل",         "adm_export",  "primary")],
        [btn("🆕 شروع فصل جدید",      "adm_newseason","primary"),
         btn("❓ راهنما",              "adm_help",    "primary")],
        [btn("💜 ولت سولانا",         "adm_solana_wallet","primary")],
        [btn("🔙 برگشت","back_main","primary")],
    ])


def approve_reject_kb(sid):
    return InlineKeyboardMarkup([[
        btn("✅  تأیید", f"approve_{sid}", "success"),
        btn("❌  رد",    f"reject_{sid}",  "danger"),
    ]])


def signal_result_kb(signal_id, prefix="setresult"):
    """
    prefix پیش‌فرض «setresult» برای مسیر ادمینه؛ مسیر خودگزارش‌دهی (سیگنال.py)
    همین تابع رو با prefix="selfresult" صدا می‌زنه — تا کیبورد نتیجه دقیقاً
    یک‌بار تعریف بشه و بین دو مسیر ناهماهنگ نشه.
    """
    styles = {"win_10x":"success","win_5x":"success","win_2x":"success",
              "win_sl":"primary","loss":"danger"}
    rows = []
    for key, label in RESULT_LABEL.items():
        if key == "open":
            continue
        pt   = POINT_TABLE[key]
        sign = "+" if pt >= 0 else ""
        rows.append([btn(f"{label}  ({sign}{pt}pt)",
                         f"{prefix}_{signal_id}_{key}",
                         styles.get(key,"primary"))])
    rows.append([btn("🔙 لغو","cancel","primary")])
    return InlineKeyboardMarkup(rows)


def my_results_list_kb(rows):
    """
    rows: خروجی signals_repo.get_self_reportable_signals — هر آیتم
    (id, coin, direction, signal_type, result, points, created_at).
    """
    kb = []
    for sid, coin, direction, signal_type, result, points, created in rows:
        dir_emoji = ("🟢" if direction == "LONG" else "🔴") if direction else ""
        label = f"#{sid}  {coin or '—'}{dir_emoji}"
        if result and result != "open":
            label += f"  ({RESULT_LABEL.get(result, result)})"
        kb.append([btn(label, f"myresult_{sid}", "primary")])
    kb.append([btn("🔙 برگشت","back_main","primary")])
    return InlineKeyboardMarkup(kb)


def donate_amount_kb():
    from signal_bot.site.kv import kv_get
    solana_wallet = kv_get("settings:solana_donate_wallet")
    kb = [
        [btn("5$","donate_5","primary"),   btn("10$","donate_10","primary"),
         btn("20$","donate_20","primary")],
        [btn("50$","donate_50","success"), btn("100$","donate_100","success"),
         btn("200$","donate_200","success")],
        [btn("✏️  مبلغ دلخواه","donate_custom","primary")],
    ]
    if solana_wallet:
        kb.append([btn("💜  واریز مستقیم با ولت سولانا","donate_solana_wallet","primary")])
    kb.append([btn("🔙  برگشت","back_main","primary")])
    return InlineKeyboardMarkup(kb)


def payment_link_kb(invoice_url: str, donate_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳  پرداخت آنلاین", url=invoice_url)],
        [btn("🔄  چک وضعیت پرداخت",f"checkpay_{donate_id}","primary")],
        [btn("🔙  برگشت به منو","back_main","primary")],
    ])


def caller_support_amount_kb(recipient_id):
    amounts = [5, 10, 20, 50]
    rows = [[btn(f"{a}$", f"csupport_{recipient_id}_{a}", "primary") for a in amounts[:2]],
            [btn(f"{a}$", f"csupport_{recipient_id}_{a}", "success") for a in amounts[2:]],
            [btn("✏️  مبلغ دلخواه", f"csupport_{recipient_id}_custom", "primary")],
            [btn("🔙  لغو", "cancel", "primary")]]
    return InlineKeyboardMarkup(rows)


def caller_support_payment_link_kb(invoice_url: str, donate_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳  پرداخت آنلاین", url=invoice_url)],
        [btn("🔄  چک وضعیت پرداخت", f"checkcsupport_{donate_id}", "primary")],
        [btn("🔙  برگشت به منو", "back_main", "primary")],
    ])


def profile_headline_kb():
    """فاز ۲: کیبورد نسخه‌ی خلاصه‌ی پروفایل — یه دکمه برای رفتن به جزئیات کامل."""
    return InlineKeyboardMarkup([
        [btn("🔍  جزئیات بیشتر", "menu_profile_details", "primary")],
        [btn("🔙  برگشت به منو","back_main","primary")],
    ])


def ranking_hub_kb(active_tab="leader", period="week"):
    """
    فاز ۱ (بازبینی UX): قبلاً «لیدربورد»، «تابلوی افتخار» و «پاداش‌های من»
    سه دکمه‌ی جدا و غیرمجاور تو منوی اصلی بودن با هم‌پوشانی مفهومی زیاد.
    الان زیر یه هاب مشترک با تب جمع شدن. «استخر جایزه» هم به‌عنوان تب
    چهارم اضافه شد تا تناقض قبلی رفع بشه: قبلاً برنده‌های استخر جایزه
    (تابلوی افتخار) برای همه دیده می‌شد ولی وضعیت فعلیِ خودِ استخر فقط
    برای کسی که سیگنال داده — یعنی کاربر عادی که تو «حمایت از ما» پول
    واریز می‌کنه (که مستقیم همین استخره)، هیچ‌راهی برای دیدن وضعیتش نداشت.

    callback_data هرکدوم دست‌نخورده مونده (menu_leader/menu_halloffame/
    menu_myrewards/menu_prize) — پس هندلرهای موجودشون بدون تغییر routing
    کار می‌کنن؛ فقط کیبورد خروجی‌شون یکی شده.
    """
    tabs = [
        [btn(f"🏆 لیدربورد{' ✓' if active_tab=='leader' else ''}", "menu_leader",
             "success" if active_tab=="leader" else "primary"),
         btn(f"🎖 افتخار{' ✓' if active_tab=='halloffame' else ''}", "menu_halloffame",
             "success" if active_tab=="halloffame" else "primary")],
        [btn(f"🎁 پاداش من{' ✓' if active_tab=='myrewards' else ''}", "menu_myrewards",
             "success" if active_tab=="myrewards" else "primary"),
         btn(f"💎 استخر جایزه{' ✓' if active_tab=='prize' else ''}", "menu_prize",
             "success" if active_tab=="prize" else "primary")],
    ]
    if active_tab == "leader":
        tabs.append(
            [btn(f"📅 هفتگی{'✓' if period=='week' else ''}",  "leader_week",  "success" if period=="week"  else "primary"),
             btn(f"🗓 ماهانه{'✓' if period=='month' else ''}", "leader_month", "success" if period=="month" else "primary"),
             btn(f"🌟 همه وقت{'✓' if period=='all' else ''}",  "leader_all",   "success" if period=="all"   else "primary")]
        )
    tabs.append([btn("🔙  برگشت به منو","back_main","primary")])
    return InlineKeyboardMarkup(tabs)


def mysignals_filter_kb():
    return InlineKeyboardMarkup([
        [btn("⏳ باز","mysig_open","primary"),
         btn("✅ تأیید","mysig_approved","success"),
         btn("❌ رد شده","mysig_rejected","danger")],
        [btn("🔙 برگشت","back_main","primary")],
    ])


def user_manage_kb(target_id, is_blocked_now, is_vip_helper_now=False):
    block_text = "🔓 آنبلاک" if is_blocked_now else "🔒 بلاک"
    block_cb   = f"unblock_{target_id}" if is_blocked_now else f"block_{target_id}"
    block_style= "success" if is_blocked_now else "danger"
    vip_text   = "🔻 حذف VIP Helper" if is_vip_helper_now else "💎 ارتقا به VIP Helper"
    vip_cb     = f"vip_remove_{target_id}" if is_vip_helper_now else f"vip_add_{target_id}"
    return InlineKeyboardMarkup([
        [btn(block_text, block_cb, block_style),
         btn("⭐ تنظیم امتیاز", f"setpts_{target_id}", "primary")],
        [btn("🎖 تغییر درجه", f"setrole_{target_id}", "primary")],
        [btn("🎁 اعطای پاداش", f"grantreward_{target_id}", "success")],
        [btn(vip_text, vip_cb, "primary")],
        [btn("🔙 برگشت","adm_users","primary")],
    ])


def role_picker_kb(target_id):
    rows = [[btn(label, f"role_{target_id}_{key}", "primary")] for key, label in ROLES]
    rows.append([btn("🔙 لغو", "cancel", "primary")])
    return InlineKeyboardMarkup(rows)
