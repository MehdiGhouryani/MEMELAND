"""
تنظیمات مرکزی ربات و وب‌سرور Memeland
"""
import logging
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ══════════════════════════════════════════════════════════
#  مقادیر حساس و متغیرهای محیطی
# ══════════════════════════════════════════════════════════
TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# پارس ایمن و مقاوم در برابر کوتیشن و فاصله‌های اضافی
_raw_admin_ids = os.environ.get("ADMIN_IDS", "").split(",")
ADMIN_IDS = []
for _aid in _raw_admin_ids:
    _clean_aid = _aid.strip().strip('"').strip("'")
    if _clean_aid.isdigit():
        ADMIN_IDS.append(int(_clean_aid))

NOWPAYMENTS_API = os.environ.get("NOWPAYMENTS_API_KEY", "").strip()
SUCCESS_URL = os.environ.get("SUCCESS_URL", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
DB_FILE = os.environ.get("DB_FILE", "signals.db").strip()
PERSISTENCE_FILE = os.environ.get("PERSISTENCE_FILE", "bot_state.pkl").strip()

SITE_SUPABASE_URL = os.environ.get("SITE_SUPABASE_URL", "").strip()
SITE_SUPABASE_ANON_KEY = os.environ.get("SITE_SUPABASE_ANON_KEY", "").strip()
SITE_API_KEY = os.environ.get("SITE_API_KEY", "").strip()
SITE_SUPABASE_SERVICE_KEY = os.environ.get("SITE_SUPABASE_SERVICE_KEY", "").strip()

SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")

ADMIN_PIN = os.environ.get("ADMIN_PIN", "").strip()
CALLER_PIN = os.environ.get("CALLER_PIN", "").strip()
SUBSCRIBER_PIN = os.environ.get("SUBSCRIBER_PIN", "").strip()
COMMUNITY_PIN = os.environ.get("COMMUNITY_PIN", "").strip()
UNLOCK_PIN = os.environ.get("UNLOCK_PIN", "").strip()

IMAGES_PREWATERMARKED = True
NOWPAYMENTS_BASE = "https://api.nowpayments.io/v1"
SEP = "━━━━━━━━━━━━━━━━━━━━━━━━"
SEP2 = "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"

LEVELS = [
    (0, "🪨 مبتدی"),
    (50, "⚔️ معامله‌گر"),
    (150, "💫 حرفه‌ای"),
    (300, "💎 الماس"),
    (500, "👑 لجند"),
    (1000, "🔱 گرندماستر"),
]

POINT_TABLE = {
    "win_10x": 10,
    "win_5x": 5,
    "win_2x": 3,
    "win_sl": 2,
    "loss": -1,
}

RESULT_LABEL = {
    "win_10x": "🚀 بالای ۱۰ایکس",
    "win_5x": "💎 ۵ تا ۱۰ایکس",
    "win_2x": "✅ ۲ تا ۵ایکس",
    "win_sl": "🎯 SL/TP عالی",
    "loss": "❌ ضرر",
    "open": "⏳ باز",
}

STREAK_BONUS = {3: 2, 5: 5, 10: 15}
DAILY_LIMIT = 5

ROLES = [
    ("rookie", "🐣 Memeland Rookie"),
    ("explorer", "🐸 Memeland Explorer"),
    ("guardian", "🦈 Memeland Guardian"),
    ("alpha", "🚀 Memeland Alpha Master"),
    ("og", "👑 Memeland OG"),
]
ROLE_LABELS = dict(ROLES)
DEFAULT_ROLE = "rookie"

CHANNELS = [
    ("alt", "🪙 آلت‌کوین"),
    ("dex", "🦄 دکس"),
    ("stock", "📈 بورس جهانی"),
    ("irbourse", "🇮🇷 بورس ایران"),
]
CHANNEL_LABELS = dict(CHANNELS)
DEFAULT_CHANNEL = "alt"

ROLE_DAILY_LIMITS = {
    "rookie": 3,
    "explorer": 5,
    "guardian": 8,
    "alpha": 15,
    "og": 50,
}

AUTO_PUBLISH_ROLES = {"guardian", "alpha", "og"}

ADMIN_ROLE_ADMIN = "admin"
ADMIN_ROLE_VIP_HELPER = "vip_helper"
ADMIN_ROLE_LABELS = {
    ADMIN_ROLE_ADMIN: "👑 Admin",
    ADMIN_ROLE_VIP_HELPER: "💎 VIP Helper",
}

SIGNAL_TYPE_LABELS = {
    "full": "📸 Full Signal",
    "fast": "⚡ Fast Call",
}

PUBLIC_FEED_LIMIT = 10
ALPHA_SCORE_CONFIDENCE_Z = 1.96

NOWPAYMENTS_IPN_SECRET = os.environ.get("NOWPAYMENTS_IPN_SECRET", "").strip()
IPN_CALLBACK_URL = os.environ.get("IPN_CALLBACK_URL", "").strip()
IPN_WEBHOOK_HOST = os.environ.get("IPN_WEBHOOK_HOST", "0.0.0.0").strip()
IPN_WEBHOOK_PORT = int(os.environ.get("IPN_WEBHOOK_PORT", "8443"))
IPN_WEBHOOK_PATH = "/nowpayments-ipn"
WEBAPP_AUTH_PATH = "/webapp-auth"


def setup_logging():
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def validate():
    if not TOKEN:
        sys.exit("❌ BOT_TOKEN تنظیم نشده است!")
    if not ADMIN_IDS:
        logging.warning("⚠️ ADMIN_IDS خالی است — دسترسی ادمین برای هیچ شناسه‌ای فعال نیست.")
    if SITE_URL and not SITE_URL.startswith("https://"):
        logging.warning(f"⚠️ SITE_URL باید حتماً HTTPS باشد: {SITE_URL}")