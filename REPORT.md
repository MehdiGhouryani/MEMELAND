# گزارش بررسی و اصلاح MEMELAND

تاریخ: ۲۰ سپتامبر ۲۰۲۶ · نسخه‌ی بیلد: `2026-09-20.1`

---

## ۱. علت ریشه‌ای دو مشکل گزارش‌شده

هر دو مشکل — «وب‌اپ منو ادمین نمی‌شناسه» و «سیگنال‌ها نشون داده نمی‌شن» — **یک علت واحد** دارند.

### باگ

```js
const API = { ... };     // api.js
const Views = { ... };   // views.js
const TGBridge = { ... };// telegram.js
const App = { ... };     // app.js
const Modals = { ... };  // modals.js
const Dossier = { ... }; // dossier.js
```

در یک **classic script** (بدون `type="module"`)، اعلان `const`/`let` در بالاترین سطح فقط یک
binding *لغوی* در global scope می‌سازد و **هرگز به `window` اضافه نمی‌شود**. این با `var`
فرق دارد.

نتیجه: `API` کار می‌کرد، ولی `window.API` همیشه `undefined` بود — و کل `app.js` قبل از هر
فراخوانی دقیقاً `window.API` را چک می‌کند:

```js
if (window.API && typeof API.authenticateWebApp === 'function') { ... }
```

### زنجیره‌ی دقیق تا علائم

```
window.API === undefined
   └─> گارد authenticateWebApp رد می‌شود
          └─> هیچ درخواست احراز هویتی به سرور زده نمی‌شود
                 └─> session = null
                        ├─> isAdmin = false  ⇒  پنل ادمین + FAB + بج ADMIN مخفی
                        └─> گارد getSignals هم رد می‌شود
                               └─> state.signals = []  ⇒  total=0
```

### شواهد در لاگ خودتان

```
[BOOT] guardFail check=API.getSession       hasAPI=false
[BOOT] guardFail check=API.authenticateWebApp hasAPI=false
[BOOT] guardFail check=TGBridge.init        hasTGBridge=false
[BOOT] guardFail check=window.Views
[APP]  ready sessUid=none tgUid=2088114041 adm=false sigCount=0
```

`tgUid` پر است ولی `sessUid` خالی — یعنی SDK تلگرام سالم لود شده و آیدی را می‌دهد،
ولی هیچ‌وقت سشنی از سرور گرفته نشده.

**امضای قطعی:** در لاگ شما `avatars.js` و `pull_refresh.js` هیچ‌وقت `guardFail` ندادند —
و اتفاقاً فقط همین دو فایل `window.X = X` را صریح می‌نویسند.

### اثبات تجربی

`tests/harness_globals.js` هر ۹ فایل را در یک realm جدا اجرا می‌کند:

| | API | Views | Modals | TGBridge | Dossier | App | PullRefresh | AvatarRenderer |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **قبل** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **بعد** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### چرا در چت معمولی مشکلی نبود

آنجا اصلاً جاوااسکریپتی در کار نیست. `handlers/admin.py` مستقیم
`access.is_admin(user_id)` → `user_id in settings.ADMIN_IDS` را چک می‌کند.

### فیکس

یک خط در انتهای هر ماژول:

```js
window.API = API;   // و مشابه برای Views / Modals / TGBridge / Dossier / App
```

در `app.js` این خط **قبل از** `App.init()` قرار گرفته، چون `TGBridge.init()` به
`window.App` نگاه می‌کند.

---

## ۲. آسیب‌پذیری‌های امنیتی (بحرانی — قبل از هر چیز دیگری دیپلوی کنید)

این‌ها با اکسپلویت واقعی روی کد فعلی شما اجرا و تأیید شدند
(`tests/exploit_demo.py`). **هیچ اعتبارنامه‌ای لازم نیست** — فقط یک هدر HTTP که هر
کسی می‌تواند بنویسد.

### ۲.۱ ارتقای کامل دسترسی ادمین (شدیدترین)

```bash
curl -H "X-Telegram-User-Id: 2088114041" https://<دامنه>/site/staff
```

خروجی روی کد فعلی:

```
GET  /site/staff                  → 200   🔓 نشت لیست کامل ادمین‌ها
POST /site/staff (ادمین جدید)     → 200   🔓 مهاجم خودش را ادمین کرد
DEL  /site/signals/1              → 200   🔓 سیگنال حذف شد
POST /site/content/articles       → 200   🔓 محتوا منتشر شد
```

**علت:** `_require_admin` در `routes.py` بعد از چک اول، دوباره *فقط بر اساس
`telegram_id`* دسترسی می‌دهد:

```python
if telegram_id and (int(telegram_id) in ADMIN_IDS or int(telegram_id) in auth.get_admin_ids()):
    session["is_admin"] = True
    return session
```

و روی مسیر تأییدنشده، `telegram_id` مستقیماً از هدر `X-Telegram-User-Id` می‌آید.
این بلوک **بعد از** `_resolve_user_session` اجرا می‌شود، پس تمام محافظت‌های داخل آن
را دور می‌زند — از جمله همان کامنت «فیکس امنیتی بحرانی» که بالایش نوشته شده.

آیدی عددی تلگرام محرمانه نیست؛ از هر پیام فوروارد‌شده‌ای قابل‌کشف است.

**فیکس:** `_require_verified()` — هیچ مسیری به دسترسی ادمین ختم نمی‌شود مگر هویت با
یکی از این دو اثبات شده باشد: توکن سشن معتبر، یا `initData` امضاشده‌ی تلگرام.

### ۲.۲ ارتقا از طریق توکن (مسیر دوم به همان مقصد)

مسیر تأییدنشده `is_admin=False` برمی‌گرداند ولی **یک توکن سشن واقعی صادر می‌کرد**.
دفعه‌ی بعد که همان توکن با `Authorization: Bearer` برگردد،
`auth.get_session()` دوباره از صفر `is_admin` را از روی `telegram_id` حساب می‌کند:

```
توکن صادرشده از همان مسیر، دوباره فرستاده شد → is_admin=True  🔓 ارتقای کامل
```

**فیکس:** در مسیر تأییدنشده اصلاً توکنی صادر نمی‌شود. هویت اثبات‌نشده هرگز به یک
اعتبارنامه‌ی ماندگار تبدیل نمی‌شود.

### ۲.۳ نشت دسترسی از طریق `quota`

```
/site/session → is_admin=False   ولی   quota.is_admin=True
                                        quota.display_role='👑 Super Admin'
```

`app.js` در `updateUserInterface` دقیقاً این را هم چک می‌کند:

```js
const isAdmin = Boolean(isSuper || s?.is_admin === true || quota?.is_admin === true || ...);
```

⇒ پنل ادمین برای هویت اثبات‌نشده باز می‌شد.

**فیکس:** پارامتر `elevate=False` در `get_user_role_and_quota` — دیکشنری quota از پایه
بدون ارتقا ساخته می‌شود.

### ۲.۴ ادعای جعلی مالکیت سیگنال

`_require_owner_or_admin` مالکیت را با مقایسه‌ی `telegram_id` سشن می‌سنجد. روی مسیر
تأییدنشده آن آیدی از هدر می‌آید ⇒ هر کسی می‌توانست ادعا کند صاحب هر سیگنالی است و
نتیجه‌اش را به `win` تغییر دهد. مستقیماً روی لیدربورد و اعتبار کالرهای واقعی اثر دارد.

### ۲.۵ آپلود فایل بدون هیچ احراز هویتی

```python
session = _resolve_user_session(request)   # ← نتیجه هیچ‌وقت چک نمی‌شد
```

نتیجه: `WebUploadOK: uid=anon` — هر غریبه‌ای می‌توانست فایل ۱۰ مگابایتی دلخواه در
`/static/uploads` بنویسد (پسوند `.jpg` می‌شود ولی محتوا اعتبارسنجی نمی‌شود). هم پر شدن
دیسک، هم میزبانی فایل دلخواه روی دامنه‌ی خودتان.

### ۲.۶ تزریق لاگ

`/site/client-log` باز، بدون سقف طول، بدون محدودیت نرخ، و بدون حذف `\n`:

```
# لاگ تولیدشده روی کد فعلی — خط کاملاً مستقل، غیرقابل‌تشخیص از خروجی واقعی سرور:
09-20 20:09:51 [I] AuthOK: uid=999000111 adm=True super=True
```

به‌علاوه: پیام ۲۰هزار کاراکتری بدون برش نوشته می‌شد، و ۲۰۰ خط flood همه ثبت می‌شدند —
یعنی یک حلقه‌ی ساده می‌توانست با rotation، شواهد واقعی را از بین ببرد.

بعد از فیکس:
```
09-20 17:16:49 [I] [JS:?] boot ok 09-20 20:09:51 [I] AuthOK: uid=999000111 ...
                        └─ یک خط، علامت‌خورده به‌عنوان محتوای کلاینت
```

---

## ۳. زیرساخت لاگ

### ۳.۱ دو سیستم لاگ موازی

| | مقصد | چه کسی می‌نوشت |
|---|---|---|
| `settings.setup_logging()` | `./bot.log` | `logging.info(...)` — ipn_server، site_sync، traders، connection |
| `logger.py` | `logs/bot.log` | `logger.info(...)` — routes، auth، ratings |

و `/logs` **فقط دومی** را می‌خواند.

اندازه‌گیری واقعی روی همان اکسپلویت:

```
logs/bot.log  : 27359 بایت   (چیزی که /logs نشان می‌دهد)
./bot.log     : 64066 بایت   (نامرئی برای /logs)
```

**۷۰٪ حجم لاگ اصلاً دیده نمی‌شد.** به‌علاوه چون `propagate` روی logger «memeland» روشن
بود، خطوطش در هر دو فایل و دوبار در کنسول می‌آمدند.

**فیکس:** هندلرها فقط روی root نصب می‌شوند؛ logger نام‌دار هیچ هندلری ندارد و propagate
می‌کند. بعد از فیکس: `./bot.log = 0 بایت`، همه‌چیز یک‌جا، بدون تکرار.

### ۳.۲ لاگ دروغگو

```js
if (window.API && typeof API.getSignals === 'function') { ... }   // ساکت رد می‌شد
// ...
window.logEventThrottled('APP', 'loadSignalsOK', { total: 0, open: 0 });
```

یعنی لاگ می‌گفت «موفق، صفر سیگنال» در حالی که **اصلاً درخواستی زده نشده بود**. همین یک
خط، چند دور دیباگ را به بیراهه برده. حالا:

```
[APP] loadSignalsSkipped reason=API missing        ← سطح ERROR
```

### ۳.۳ لاگر جدید کلاینت (`static/js/logger.js`)

| قبل | بعد |
|---|---|
| هر خط = یک `fetch` جدا (۱۴ درخواست در ۴۰ ثانیه) | batch: هر ۲.۵ ثانیه / ۸ رویداد / فوری برای خطا |
| همه‌چیز INFO، حتی خطای JS | سطوح `E/W/I/D` — سرور با levelname درست ثبت می‌کند |
| `sid` و `build` در هر خط تکرار می‌شد | یک‌بار در هر batch ⇒ حجم تقریباً نصف |
| دو تعریف موازی (inline + fallback در `api.js`) | یک فایل، یک تعریف |
| throttle: تعداد سرکوب‌شده گم می‌شد | flush زمان‌دار با `repeated=N` |
| لاگ لحظه‌ی خروج/کرش گم می‌شد | `sendBeacon` روی `pagehide` + `visibilitychange` |
| — | ring buffer محلی: `MHLog.tail(40)` در کنسول |

### ۳.۴ ابزارهای تشخیص جدید

**`/diag` در ربات** — یک عکس فوری، بدون خواندن لاگ:

```
🩺 وضعیت سیستم
هویت شما:  آیدی · در ADMIN_IDS ✅/❌ · در جدول staff ✅/❌
دیتابیس:   مسیر بات · مسیر سایت · تعداد سیگنال فید · سشن‌های فعال
وب‌اپ:     index.html ✅ · تعداد فایل JS · logger.js دیپلوی شده ✅ · SITE_URL
لاگ:       حجم · تعداد خطا · تعداد هشدار
```

**`/logs` با فیلتر:**

```
/logs            ۳۰ خط آخر
/logs 80         ۸۰ خط آخر
/logs err        فقط ERROR
/logs warn       WARNING و بالاتر
/logs js         فقط لاگ‌های کلاینت وب‌اپ
/logs auth       هر خطی شامل «auth»
/logs err 60     ۶۰ خط آخر از ERROR ها
/logs file       فایل کامل
```

**`GET /site/diag`** (فقط ادمین) — همان اطلاعات به‌صورت JSON، از داخل وب‌اپ.

### ۳.۵ کاهش نویز

`httpx` در سطح INFO برای هر polling تلگرام یک خط می‌نویسد. این‌ها (به‌همراه
`telegram`, `apscheduler`, `aiohttp.access`, `asyncio`, `urllib3`) به WARNING منتقل شدند.

---

## ۴. سایر باگ‌های یافت‌شده

### ۴.۱ نشت جدول `sessions`

`_resolve_user_session` به ازای **هر درخواست** یک ردیف سشن جدید می‌ساخت. اندازه‌گیری:

```
۲۰ درخواست ساده‌ی فید → ردیف sessions: 5 ⟶ 25
```

هر لود صفحه ≥۲ درخواست می‌زند، pull-refresh هم همین‌طور، و هیچ‌وقت چیزی پاک نمی‌شد.
هر توکن ۳۰ روز اعتبار دارد.

**فیکس:** استفاده‌ی مجدد از توکن زنده (`find_active_token`) + جاب پاک‌سازی روزانه
(`purge_expired_sessions`) + حذف کامل صدور توکن در مسیر تأییدنشده.
بعد از فیکس: `0 ⟶ 0`.

### ۴.۲ واگرایی دو دیتابیس

ربات کادر را در `staff` دیتابیس **خودش** (`signals.db`) می‌نویسد؛ سایت `staff` دیتابیس
**سایت** (`site.db`) را می‌خواند. یعنی هر VIP Helper که از داخل ربات اضافه شود، در
وب‌اپ ادمین نیست. فقط `ADMIN_IDS` (از `.env`) اتفاقی در هر دو کار می‌کرد.

**فیکس:** `_is_staff_admin` هر دو دیتابیس را چک می‌کند.

### ۴.۳ رول کاربر همیشه `rookie`

`get_user_role_and_quota` جدول `users` را در `site.db` می‌جست — جدولی که آنجا **وجود
ندارد** (فقط در `signals.db` است). چون کد اول با `sqlite_master` وجود جدول را چک
می‌کرد، هیچ خطایی نمی‌داد و **بی‌صدا** همیشه `rookie` برمی‌گرداند.

اثر عملی: سقف سهمیه‌ی روزانه‌ی همه‌ی کاربران روی ۳ گیر کرده بود، صرف‌نظر از رول
واقعی‌شان (`explorer`=۵، `guardian`=۸، `alpha`=۱۵، `og`=۵۰).

> `traders.py` دقیقاً همین باگ را قبلاً برای `username` فیکس کرده بود، ولی اینجا جا
> مانده بود.

### ۴.۴ پنجره‌ی زمانی لیدربورد

`created_at` همه‌جا با `datetime.utcnow()` نوشته می‌شود، ولی `handle_leaderboard` از
`datetime.now()` (ساعت محلی سرور) استفاده می‌کرد. روی سرور با ساعت ایران، پنجره‌ی
«هفته» ۳:۳۰ ساعت جابه‌جا می‌شد و سیگنال‌های مرزی از لیدربورد می‌افتادند.

### ۴.۵ خطای ۵۰۰ به‌جای ۴۰۰

`int(request.match_info["id"])` بدون `try` در سه هندلر. یک درخواست به
`/site/signals/abc` باعث `ValueError` مدیریت‌نشده، پاسخ ۵۰۰ و یک traceback در لاگ می‌شد.

### ۴.۶ ویرایش سیگنال شکننده

کل بدنه به `edit_signal(**body)` پاس داده می‌شد. هر کلید اضافه‌ای که فرانت‌اند بفرستد
(مثل `id` یا `token`) باعث `ValueError` و پاسخ ۴۰۰ برای یک ویرایش کاملاً معتبر می‌شد.

### ۴.۷ SQLite بدون WAL

`site.db` با `timeout` پیش‌فرض (۵ ثانیه) و `journal_mode=DELETE`. وب‌سرور و ربات در یک
پروسه و یک event loop اجرا می‌شوند و همه‌ی فراخوانی‌های sqlite3 همگام‌اند.

> نشانه‌ی این‌که واقعاً رخ می‌داده: `site_sync.py` یک retry اختصاصی برای
> `"database is locked"` دارد.

**فیکس:** `WAL` + `synchronous=NORMAL` + `busy_timeout=8000` + `timeout=8.0`.

---

## ۵. اعتبارسنجی

### ۵.۱ تست یکپارچه — ۴۷ مورد، همه موفق

```
۱  احراز هویت با initData معتبر (HMAC واقعی)      ۴ مورد ✅
۲  استفاده‌ی مجدد از سشن                          ۱ مورد ✅
۳  مسیر تأییدنشده                                 ۵ مورد ✅
۴  رد کردن initData جعلی                          ۱ مورد ✅
۵  ارتقای دسترسی (۵ مسیر مختلف)                   ۸ مورد ✅
۶  فید سیگنال + قفل VIP                           ۲ مورد ✅
۷  لاگ کلاینت (batch/سطح/تزریق/نرخ)               ۵ مورد ✅
۸  ورودی‌های بد ⇒ ۴۰۰ نه ۵۰۰                       ۳ مورد ✅
۹  آپلود بدون احراز هویت                          ۱ مورد ✅
۱۰ /site/diag                                     ۴ مورد ✅
۱۱ سیستم لاگ یکپارچه                              ۷ مورد ✅
۱۲ ادعای جعلی مالکیت                              ۲ مورد ✅
۱۳ خواندن عمومی هنوز باز است                      ۳ مورد ✅
```

اجرا: `cd signal_bot && python3 tests/test_integration.py`

> دو مورد از این تست‌ها در اولین اجرا **شکست خوردند** و باگ‌های ۲.۱ و ۲.۴ را پیدا کردند
> — باگ‌هایی که با خواندن کد پیدا نکرده بودم. تست‌ها را نگه دارید.

### ۵.۲ نمایش اکسپلویت

`tests/exploit_demo.py` روی هر دو نسخه اجرا می‌شود و تفاوت را نشان می‌دهد.

### ۵.۳ harness گلوباله‌ها

`tests/harness_globals.js` — اثبات مستقل باگ ریشه‌ای، بدون نیاز به مرورگر.

---

## ۶. فایل‌های تغییریافته

| فایل | خطوط تغییر |
|---|---:|
| `memeland_site/static/js/logger.js` | **جدید** — ۲۱۵ |
| `memeland_site/index.html` | ۱۳۱ |
| `memeland_site/static/js/app.js` | ۷۱ |
| `memeland_site/static/js/api.js` | ۵۳ |
| `memeland_site/static/js/{views,modals,telegram,dossier}.js` | ۲۲ هرکدام |
| `signal_bot/signal_bot/site/routes.py` | ۳۲۸ |
| `signal_bot/signal_bot/logger.py` | ۱۸۴ |
| `signal_bot/signal_bot/site/auth.py` | ۱۸۲ |
| `signal_bot/main.py` | ۱۳۶ |
| `signal_bot/signal_bot/site/db.py` | ۲۷ |
| `signal_bot/signal_bot/config/settings.py` | ۲۰ |

هیچ تغییری در schema دیتابیس لازم نیست (فقط یک ایندکس `IF NOT EXISTS` اضافه شده).

---

## ۷. دیپلوی

```bash
# ۱. بکاپ
cp -r MEMELAND-main MEMELAND-backup-$(date +%F)

# ۲. اعمال پچ
cp -r memeland-patch/memeland_site/*  MEMELAND-main/memeland_site/
cp -r memeland-patch/signal_bot/*     MEMELAND-main/signal_bot/

# ۳. ری‌استارت
# (ری‌استارت معمول خودتان)
```

### تأیید بعد از دیپلوی — به همین ترتیب

**گام ۱ — در ربات:**
```
/diag
```
هر چهار مورد باید ✅ باشند. اگر «logger.js دیپلوی شده ❌» بود، فایل‌های استاتیک
به‌درستی کپی نشده‌اند.

**گام ۲ — وب‌اپ را باز کنید، بعد:**
```
/logs 40
```
باید ببینید:
```
[BOOT] index.html build=2026-09-20.1
[BOOT] logger.js build=2026-09-20.1
[BOOT] modules build=2026-09-20.1 API=1 Views=1 Modals=1 TGBridge=1 Dossier=1
       PullRefresh=1 AvatarRenderer=1 tgSdk=1 initLen=<عددی بزرگ‌تر از صفر>
[AUTH] attempt hasTg=true initLen=... tgUid=2088114041
WebAppAuthReq: path=/site/auth initDataLen=... 
AuthOK: uid=2088114041 adm=True super=True
[APP] ready sessUid=2088114041 tgUid=2088114041 adm=true verified=1 role=admin sigCount=N
```

**نکته‌ی کلیدی:** خط `[BOOT] modules` جایگزین همه‌ی `guardFail`های پراکنده شده. اگر
هر کدام `=0` بود، آن فایل لود نشده (مشکل دیپلوی یا کش) — نه باگ منطقی.

**گام ۳ — اگر هنوز `adm=false` بود**, دو حالت ممکن است:

| نشانه در لاگ | معنی | راه‌حل |
|---|---|---|
| `verified=0` | `initData` خالی رسیده — سرور عمداً دسترسی نمی‌دهد | مقدار `initLen` را ببینید؛ اگر ۰ است، مشکل از سمت تلگرام/وب‌ویو است نه کد |
| `verified=1` ولی `adm=false` | هویت اثبات شده ولی آیدی در لیست ادمین نیست | `/diag` → «در ADMIN_IDS» را چک کنید |
| `AuthFail: TMA init_data invalid` | `BOT_TOKEN` سرور با توکن ربات میزبان وب‌اپ یکی نیست | `.env` را چک کنید |

---

## ۸. تغییرات رفتاری که باید بدانید

1. **ثبت سیگنال، آپلود تصویر و همه‌ی عملیات ادمین حالا `initData` امضاشده لازم دارند.**
   داخل وب‌اپ تلگرام همیشه موجود است. ولی اگر صفحه را مستقیم در مرورگر باز کنید،
   دیگر نمی‌توانید بنویسید. این مصالحه عمدی است — بدون آن، هدر جعلی کافی بود.
   خواندن (فید، لیدربورد، مقالات) همچنان عمومی است.

2. **`?v=8.0.0`** روی تمام فایل‌های استاتیک برای ابطال کش وب‌ویو تلگرام.

3. **`window.__MH_BUILD`** هنوز دستی است. پیشنهاد: از CI یا `git rev-parse --short HEAD`
   پرش کنید تا دیگر یادتان نرود.

---

## ۹. آنچه بررسی نشده

برای صداقت گزارش — این‌ها را **بررسی نکرده‌ام**:

- `handlers/` (۲۳۰۰ خط: admin، signals، payments، support) — فقط برای فهمیدن منطق
  تشخیص ادمین خوانده شدند، نه ممیزی کامل.
- `services/` جز `webapp_auth` و `site_sync` — مخصوصاً `price_feed`,
  `alpha_score`, `payments`, `watermark`.
- `web/ipn_server.py` — فقط ثبت مسیرها خوانده شد. مسیر IPN
  (وب‌هوک پرداخت) ممیزی نشده و پول در جریان است؛ ارزش یک بررسی جدا را دارد.
- CSS — اصلاً باز نشده.
- عملکرد واقعی روی دستگاه/وب‌ویوی تلگرام — همه‌ی تست‌ها headless بودند.

پیشنهاد بعدی، به ترتیب اولویت: مسیر IPN، سپس `handlers/payments.py`.
