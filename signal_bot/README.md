# Signal Master Bot + Memeland Hub

بات تلگرام مدیریت سیگنال ترید + وب‌سایت همراهش (Memeland Hub) — هم‌محل،
یه SQLite مشترک. جزئیات تاریخچه/تصمیم‌های معماری تو `CHANGELOG.md`.

## ساختار پروژه

```
signal_bot/              ← این پوشه (پروژه‌ی بات)
├── main.py
├── requirements.txt
├── .env.example
└── signal_bot/           ← پکیج پایتون
    ├── config/            تنظیمات (settings.py)
    ├── db/                دیتابیس خودِ بات (signals.db)
    ├── site/               بک‌اند سایت (site.db) — auth, signals, ratings, kv, routes
    ├── handlers/          هندلرهای تلگرام
    ├── keyboards/         کیبوردهای inline
    ├── services/          سرویس‌های مشترک (site_sync, image_upload, ...)
    ├── formatters/        متن‌های نمایشی
    ├── jobs/              کارهای زمان‌بندی‌شده
    └── web/               سرور aiohttp (IPN + webapp-auth + بک‌اند سایت)
memeland_site/            ← کنارِ signal_bot/، sibling (نه داخلش)
└── memeland-hub_UPDATED.html
```

⚠️ `memeland_site/` باید **کنار** `signal_bot/` باشه (sibling)، نه داخلش —
`site/routes.py` مسیر فایل HTML رو نسبت به همین چیدمان محاسبه می‌کنه.

## نصب و اجرا

```bash
cd signal_bot
pip install -r requirements.txt
cp .env.example .env      # حداقل BOT_TOKEN رو پر کن
python main.py
```

با اجرا، هم بات (polling تلگرام) هم سرور وب بالا میان. سرور وب رو
`IPN_WEBHOOK_HOST:IPN_WEBHOOK_PORT` (پیش‌فرض `0.0.0.0:8443`) گوش می‌ده و
هم خودِ سایت رو سرو می‌کنه (`GET /`) هم API بک‌اندش رو (`/site/...`).

## تنظیمات کلیدی (`.env`)

| متغیر | لازم؟ | توضیح |
|---|---|---|
| `BOT_TOKEN` | ✅ اجباری | از @BotFather |
| `ADMIN_IDS` | توصیه‌شده | بدونش هیچ‌کس دسترسی ادمین نداره |
| `SITE_URL` | برای دکمه‌ی WebApp | باید HTTPS باشه؛ خالی = دکمه نشون داده نمی‌شه |
| `NOWPAYMENTS_IPN_SECRET` | اختیاری | بدونش فقط وب‌هوک IPN غیرفعاله، بقیه کار می‌کنه |
| `SITE_SUPABASE_URL` + `SITE_SUPABASE_SERVICE_KEY` | اختیاری | فقط برای آپلود عکس (Supabase Storage) — تنها بخشی که هنوز مهاجرت نکرده |
| `SITE_DB_FILE` | اختیاری | پیش‌فرض `site.db` کنار `signals.db` |

`SITE_SUPABASE_ANON_KEY`/`SITE_API_KEY` دیگه استفاده نمی‌شن (میراث دوران
Postgres) — می‌تونی خالی بذاریشون یا از `.env` پاک کنی.

## کارهای باقی‌مونده / پیش‌نیازهای قبل از دیپلوی واقعی

- `memeland-hub_UPDATED.html`: `TELEGRAM_BOT_USERNAME` هنوز پلیس‌هولدره — با یوزرنیم واقعی بات پر کن (بدونش فقط Login Widget غایبه، بقیه کار می‌کنه).
- آپلود عکس هنوز رو Supabase Storage‌ه (کار جدا، هروقت خواستی به SQLite/دیسک محلی هم می‌شه منتقلش کرد).
