"""
تنظیمات مرکزی ربات — همه‌ی مقادیر قابل‌تغییر یک‌جا اینجا هستن.
⚠️ هیچ مقدار حساسی (توکن، کلید API) اینجا هاردکد نشه — همه از .env خونده می‌شه.
"""
import os
import sys
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv نصب نیست؛ باید متغیرهای محیطی رو خودت export کنی

# ══════════════════════════════════════════════════════════
#  مقادیر حساس — از فایل .env (هیچ‌وقت مستقیم اینجا ننویس)
# ══════════════════════════════════════════════════════════
TOKEN           = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS       = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
NOWPAYMENTS_API = os.environ.get("NOWPAYMENTS_API_KEY", "")
SUCCESS_URL     = os.environ.get("SUCCESS_URL", "")
CHANNEL_ID      = os.environ.get("CHANNEL_ID", "")   # کانال برای پست خودکار (یا خالی بذار "")
DB_FILE         = os.environ.get("DB_FILE", "signals.db")
# قبلاً هیچ persistence روی Application تنظیم نشده بود — یعنی chat_data/user_data
# فقط تو RAM بودن و با هر ری‌استارت بات (دیپلوی، کرش) وسط یه فلوی چندمرحله‌ای
# (مثلاً منتظر عکس تو ثبت سیگنال) گم می‌شدن. کاربر فقط با پیام «اول از منو ثبت
# سیگنال رو بزن» مواجه می‌شد — نه دیتا خراب می‌شد، نه کرش، ولی گیج‌کننده بود.
PERSISTENCE_FILE = os.environ.get("PERSISTENCE_FILE", "bot_state.pkl")

# سینک با سایت (Memeland Hub). از پیوت به SQLite (بات مستقیم رو دیتابیس
# سایت می‌نویسه، site_sync.py دیگه HTTP call نمی‌زنه)، این دو تا زیر عملاً
# مرده‌ن — نگه‌شون داشتم چون SITE_SUPABASE_URL هنوز لازمه (image_upload.py
# برای آپلود عکس رو Supabase Storage استفاده می‌کنه، اون بخش هنوز مهاجرت
# نکرده)، ولی خودِ ANON_KEY/API_KEY دیگه جایی استفاده نمی‌شن. می‌تونی خالی
# بذاریشون، هیچ رفتاری عوض نمی‌شه.
SITE_SUPABASE_URL       = os.environ.get("SITE_SUPABASE_URL", "")
SITE_SUPABASE_ANON_KEY  = os.environ.get("SITE_SUPABASE_ANON_KEY", "")  # ⚠️ دیگه استفاده نمی‌شه، بعد از پیوت SQLite
SITE_API_KEY            = os.environ.get("SITE_API_KEY", "")  # ⚠️ دیگه استفاده نمی‌شه، بعد از پیوت SQLite

# ⚠️ فاز ۳-ب: کلید جدا برای آپلود Storage — عمداً از SITE_SUPABASE_ANON_KEY
# جداست چون anon کلید عمومیه (تو HTML سایت هم دیده می‌شه) و بعد از فاز ۳-ب
# دیگه اجازه‌ی آپلود نداره. این باید Service Role Key باشه (Supabase →
# Settings → API → service_role) و فقط همین‌جا، تو .env بات، بمونه — هیچ‌وقت
# تو کد سمت مرورگر/HTML قرار نگیره.
SITE_SUPABASE_SERVICE_KEY = os.environ.get("SITE_SUPABASE_SERVICE_KEY", "")

# آدرس عمومی Memeland Hub (HTTPS الزامیه — پیش‌نیاز دکمه‌ی web_app تلگرام).
# قبلاً همچین متغیری اصلاً وجود نداشت؛ بات هیچ راهی برای اشاره به آدرس عمومی
# سایت نداشت. اگه خالی بمونه، دکمه‌ی سایت تو منو نشون داده نمی‌شه (نه کرش).
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")

# یوزرنیم بات (بدون @) برای Telegram Login Widget — قبلاً فقط تو خودِ HTML
# دستی ادیت می‌شد؛ حالا routes.py:handle_index موقع سرو کردن جاش می‌ذاره.
# خالی = ویجت رندر نمی‌شه (نه کرش). باید با BotFather /setdomain هماهنگ باشه.
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")

# ⚠️ پین‌های سایت — تا الان هیچ‌جا از .env خونده نمی‌شدن (site/auth.set_pin
# هیچ‌جا صدا زده نمی‌شد)، یعنی هیچ نقشی (admin/caller/subscriber/community/
# unlock) عملاً قابل claim نبود. main.py سر استارت با اینا bootstrap_pins_from_env
# رو صدا می‌زنه. خالی‌بودن یعنی همون نقش هنوز غیرفعاله، بدون کرش.
ADMIN_PIN      = os.environ.get("ADMIN_PIN", "")
CALLER_PIN     = os.environ.get("CALLER_PIN", "")
SUBSCRIBER_PIN = os.environ.get("SUBSCRIBER_PIN", "")
COMMUNITY_PIN  = os.environ.get("COMMUNITY_PIN", "")
UNLOCK_PIN     = os.environ.get("UNLOCK_PIN", "")

# ⚠️ فرض فعلی (طبق گفته‌ی کارفرما): واترمارک از قبل، بیرون از این پایپ‌لاین،
# رو عکس‌ها اعمال می‌شه. اگه این فرض عوض شد (مثلاً یه API واترمارک باید صدا
# زده بشه)، این رو False کن تا سایت لایه‌ی CSS واترمارک خودش رو غیرفعال نکنه.
IMAGES_PREWATERMARKED = True

NOWPAYMENTS_BASE = "https://api.nowpayments.io/v1"
SEP  = "━━━━━━━━━━━━━━━━━━━━━━━━"
SEP2 = "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"

# ══════════════════════════════════════════════════════════
#  تنظیمات قابل‌تغییر بازی/امتیازدهی
#  (فاز بعدی: این‌ها به یک فایل/جدول تنظیمات جدا و ادیت‌پذیر
#   از پنل ادمین منتقل می‌شن — همون‌طور که در بند ۱۷ نیازمندی‌ها اومده)
# ══════════════════════════════════════════════════════════

# سطح‌بندی کاربران (بر اساس امتیاز خام — مجزا از «رول»ی که در فاز ۲ اضافه می‌شه)
LEVELS = [
    (0,    "🪨 مبتدی"),
    (50,   "⚔️ معامله‌گر"),
    (150,  "💫 حرفه‌ای"),
    (300,  "💎 الماس"),
    (500,  "👑 لجند"),
    (1000, "🔱 گرندماستر"),
]

# امتیازدهی نتیجه سیگنال
POINT_TABLE = {
    "win_10x": 10,
    "win_5x":   5,
    "win_2x":   3,
    "win_sl":   2,
    "loss":    -1,
}
RESULT_LABEL = {
    "win_10x": "🚀 بالای ۱۰ایکس",
    "win_5x":  "💎 ۵ تا ۱۰ایکس",
    "win_2x":  "✅ ۲ تا ۵ایکس",
    "win_sl":  "🎯 SL/TP عالی",
    "loss":    "❌ ضرر",
    "open":    "⏳ باز",
}

# استریک بونوس: {تعداد استریک متوالی: امتیاز بونوس}
STREAK_BONUS = {3: 2, 5: 5, 10: 15}

# محدودیت روزانه ثبت سیگنال — پیش‌فرض/fallback (وقتی رول کاربر در ROLE_DAILY_LIMITS نباشه)
DAILY_LIMIT = 5

# ══════════════════════════════════════════════════════════
#  رول‌های کاربری (Roles) — بند ۲ و ۳ نیازمندی‌ها
#  ⚠️ این‌ها کاملاً مجزا از «سطح» (LEVELS) بالا هستن:
#     سطح خودکار و بر اساس امتیازه، رول فقط دستی و توسط ادمین تغییر می‌کنه
#     و محدودیت ثبت سیگنال رو تعیین می‌کنه.
# ══════════════════════════════════════════════════════════
ROLES = [
    ("rookie",   "🐣 Memeland Rookie"),
    ("explorer", "🐸 Memeland Explorer"),
    ("guardian", "🦈 Memeland Guardian"),
    ("alpha",    "🚀 Memeland Alpha Master"),
    ("og",       "👑 Memeland OG"),
]
ROLE_LABELS = dict(ROLES)          # {"rookie": "🐣 Memeland Rookie", ...}
DEFAULT_ROLE = "rookie"

# کانال/دسته‌ی سیگنال — باید دقیقاً با ۴ دسته‌ی سایت (Memeland Hub) یکی باشه؛
# قبلاً این مفهوم اصلاً تو ویزارد ثبت سیگنال بات وجود نداشت، برای همین هر
# سیگنالی که به سایت سینک می‌شد همیشه با channel="alt" هاردکد می‌رفت، فارغ از
# این‌که واقعاً دکس بود یا بورس. کلیدها عیناً از سایت گرفته شدن (rowToSignalObj).
CHANNELS = [
    ("alt",      "🪙 آلت‌کوین"),
    ("dex",      "🦄 دکس"),
    ("stock",    "📈 بورس جهانی"),
    ("irbourse", "🇮🇷 بورس ایران"),
]
CHANNEL_LABELS = dict(CHANNELS)
DEFAULT_CHANNEL = "alt"    # همون پیش‌فرض قبلی site_sync.py — رفتار سیگنال‌های قدیمی عوض نمی‌شه

# محدودیت روزانه ثبت سیگنال به‌ازای هر رول — رول‌های بالاتر محدودیت کمتر (آزادتر) دارن.
# قابل تغییره بدون دست‌زدن به منطق کد (فاز بعدی: قابل ادیت از پنل تنظیمات).
ROLE_DAILY_LIMITS = {
    "rookie":   3,
    "explorer": 5,
    "guardian": 8,
    "alpha":    15,
    "og":       50,
}

# رول‌هایی که سیگنالشون بدون نیاز به تأیید Admin/VIP Helper مستقیم منتشر می‌شه
# (طبق خواسته‌ی کارفرما: «به افراد مشخص دسترسی بدم که تو همون سهمیه‌شون بدون
# تأیید ادمین بذارن» — این یعنی Guardian و بالاتر). همچنان محدودیت روزانه‌ی
# ROLE_DAILY_LIMITS بالا رعایت می‌شه؛ فقط مرحله‌ی بررسی دستی حذف می‌شه.
# ⚠️ کاملاً مستقل و قابل‌تغییر بدون اثر روی بقیه‌ی منطق — کافیه این مجموعه رو عوض کنی.
AUTO_PUBLISH_ROLES = {"guardian", "alpha", "og"}

# رول‌های مدیریتی — Admin از ADMIN_IDS (env) میاد، VIP Helper از جدول staff در دیتابیس
# (تا ادمین بتونه بدون دست‌زدن به .env، هر وقت خواست کمک‌ادمین اضافه/حذف کنه).
ADMIN_ROLE_ADMIN      = "admin"
ADMIN_ROLE_VIP_HELPER = "vip_helper"
ADMIN_ROLE_LABELS = {
    ADMIN_ROLE_ADMIN:      "👑 Admin",
    ADMIN_ROLE_VIP_HELPER: "💎 VIP Helper",
}

# ══════════════════════════════════════════════════════════
#  انواع سیگنال — بند ۴ نیازمندی‌ها (فاز ۳)
# ══════════════════════════════════════════════════════════
SIGNAL_TYPE_LABELS = {
    "full": "📸 Full Signal",
    "fast": "⚡ Fast Call",
}

# تعداد سیگنال نمایش‌داده‌شده در فید عمومی «سیگنال‌های فعال»
PUBLIC_FEED_LIMIT = 10

# ══════════════════════════════════════════════════════════
#  Alpha Score — بند ۸ نیازمندی‌ها (فاز ۴)
#  z = 1.96 یعنی بازه اطمینان ۹۵٪ (استاندارد رایج آماری برای Wilson score).
#  اگه بعداً خواستی محافظه‌کارتر/آزادتر بشه، فقط همین عدد رو عوض کن.
# ══════════════════════════════════════════════════════════
ALPHA_SCORE_CONFIDENCE_Z = 1.96

# ══════════════════════════════════════════════════════════
#  Prize Pool Webhook (IPN) — فاز ۵
#  اگه IPN_SECRET خالی باشه، وب‌هوک اصلاً استارت نمی‌شه و فقط چک دستی کار می‌کنه
#  (برگشت امن به رفتار قبلی، بدون کرش).
# ══════════════════════════════════════════════════════════
NOWPAYMENTS_IPN_SECRET = os.environ.get("NOWPAYMENTS_IPN_SECRET", "")
IPN_CALLBACK_URL       = os.environ.get("IPN_CALLBACK_URL", "")   # آدرس عمومی HTTPS، مثل https://yourdomain.com/nowpayments-ipn
IPN_WEBHOOK_HOST       = os.environ.get("IPN_WEBHOOK_HOST", "0.0.0.0")
IPN_WEBHOOK_PORT       = int(os.environ.get("IPN_WEBHOOK_PORT", "8443"))
IPN_WEBHOOK_PATH       = "/nowpayments-ipn"

# مسیر تأیید initData تلگرام WebApp — رو همون سرور aiohttp بالا (که قبلاً فقط
# IPN سرور بود، الان یه سرور وب عمومی‌تره). برخلاف IPN_WEBHOOK_PATH که رمزش
# تو NOWPAYMENTS_IPN_SECRET‌ه، این مسیر خودش هیچ رمزی نداره چون امنیتش از
# طریق تأیید HMAC خودِ initDataست، نه یه شِرد سکرت.
WEBAPP_AUTH_PATH        = "/webapp-auth"


def setup_logging():
    """راه‌اندازی logging — فقط یک‌بار از main.py صدا زده می‌شه."""
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def validate():
    """
    بررسی صحت تنظیمات ضروری قبل از استارت واقعی ربات.

    عمداً این چک در زمان import این فایل اجرا نمی‌شه (برخلاف نسخه فاز ۰)،
    چون import کردن این ماژول (مثلاً برای تست یا اسکریپت مهاجرت دیتابیس)
    نباید صرفاً به‌خاطر نبود .env با sys.exit متوقف بشه. این تابع رو
    main.py صراحتاً و فقط موقع اجرای واقعی ربات صدا می‌زنه.
    """
    if not TOKEN:
        sys.exit("❌  BOT_TOKEN تنظیم نشده! فایل .env رو بر اساس .env.example پر کن.")
    if not ADMIN_IDS:
        logging.warning("⚠️  ADMIN_IDS خالیه — هیچ‌کس دسترسی ادمین نداره تا وقتی تنظیمش کنی.")
    if SITE_URL and not SITE_URL.startswith("https://"):
        logging.warning(
            f"⚠️  SITE_URL باید HTTPS باشه (الان: {SITE_URL!r}) — تلگرام دکمه‌ی "
            "web_app رو با آدرس غیر-HTTPS باز نمی‌کنه، بدون هیچ خطای قابل‌مشاهده‌ای."
        )
