/**
 * MemeLand API Service & Session Manager (v7.6.0 - Robust Token Sanitization & Direct Array Parser)
 */

// ⚠️ لاگر: تعریف fallback تکراری که قبلاً اینجا بود حذف شد. تنها منبع
// حقیقت حالا /static/js/logger.js هست که *قبل از* این فایل لود می‌شه، و
// index.html هم یه shim قبل-از-بوت داره. دو تعریف موازی از logEvent باعث
// می‌شد رفتار throttle بین فایل‌ها فرق کنه و دیباگ گمراه‌کننده بشه.

// ⚠️ خط اثر انگشت بوت: همین لحظه‌ی parse شدن فایل، نه داخل یه تابع. اگه این
// خط تو لاگ سرور نبود، یعنی این نسخه از api.js اصلاً رو مرورگر لود نشده
// (مشکل دیپلوی/کش)، نه یه باگ منطقی داخل کد.
try {
  window.logEvent('BOOT', 'api.js', { build: window.__MH_BUILD || '?' });
} catch (e) {}

// ⚠️ فیکس امنیتی (XSS ذخیره‌شده): تمام دیتای آزادِ کاربر (توضیحات سیگنال، اسم
// کالر، عنوان مقاله، لینک خرید و ...) قبلاً مستقیم با innerHTML و بدون escape
// رندر می‌شد. سمت بات این escape از قبل با تابع esc() انجام می‌شد ولی سمت
// سایت هیچ‌وقت اعمال نشده بود. این دو تابع سراسری همون کار رو این‌جا انجام
// می‌دن و باید دور *هر* متن/لینک آزاد کاربر که وارد innerHTML می‌شه بذاریمشون.
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// برای href/src که کاربر آزاد پرشون می‌کنه (لینک خرید و ...)؛ فقط http/https
// رو رد می‌کنه و جلوی javascript:/data: URI رو می‌گیره.
function safeUrl(url) {
  if (!url) return '';
  const trimmed = String(url).trim();
  if (/^https?:\/\//i.test(trimmed)) return escapeHtml(trimmed);
  return '';
}

const API = {
  baseUrl: '/site',

  getToken() {
    const t = localStorage.getItem('mh_session_token') || 
              localStorage.getItem('ml_token') || 
              sessionStorage.getItem('ml_token') || '';
    if (!t || t === 'undefined' || t === 'null') return '';
    return t;
  },

  setToken(token) {
    if (!token || token === 'undefined' || token === 'null') return;
    try {
      localStorage.setItem('mh_session_token', token);
      localStorage.setItem('ml_token', token);
    } catch (e) {}
  },

  clearToken() {
    try {
      localStorage.removeItem('mh_session_token');
      localStorage.removeItem('ml_token');
      sessionStorage.removeItem('ml_token');
      localStorage.removeItem('memeland_session');
    } catch (e) {}
  },

  getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const initData = window.Telegram?.WebApp?.initData || '';
    if (initData) {
      headers['X-Telegram-Init-Data'] = initData;
    }

    const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
    if (tgUser && tgUser.id) {
      headers['X-Telegram-User-Id'] = String(tgUser.id);
    }

    return headers;
  },

  async authenticateWebApp() {
    const tg = window.Telegram?.WebApp;
    const initData = tg?.initData || '';
    const tgUser = tg?.initDataUnsafe?.user;
    const uid = tgUser?.id ? String(tgUser.id) : '';

    // ⚠️ تشخیصی: این خط دقیقاً می‌گه موقع تلاش لاگین، initData امضاشده
    // اصلاً وجود داشته یا نه (طول رشته‌ش رو نشون می‌ده، نه خودش رو، برای
    // امنیت) و آیدی تلگرام از کجا خونده شده. با این، دفعه‌ی بعد که مشکل
    // لاگین پیش بیاد، می‌فهمیم مشکل سمت کلاینته (initData اصلاً خالیه) یا
    // سمت سرور (initData هست ولی رد می‌شه).
    window.logEvent('AUTH', 'attempt', { hasTg: Boolean(tg), initLen: initData.length, tgUid: uid || 'none' });

    const payload = {
      init_data: initData,
      user_id: uid,
      user: tgUser || null
    };

    const endpoints = ['/site/auth', '/site/webapp-auth', '/webapp-auth'];
    let authData = null;

    for (const url of endpoints) {
      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: this.getHeaders(),
          body: JSON.stringify(payload)
        });
        if (resp.ok) {
          authData = await resp.json();
          window.logEvent('AUTH', 'success', { url: url, uid: authData.telegram_id || uid, adm: Boolean(authData.is_admin) });
          break;
        } else {
          // ⚠️ فیکس: قبلاً این حالت (سرور جواب داد ولی status خطا بود، مثلاً
          // ۴۰۰/۴۰۱) اصلاً لاگ نمی‌شد — یعنی هیچ ردی از این‌که چرا لاگین رد
          // شده باقی نمی‌موند. الان status و متن خطای واقعی سرور ثبت می‌شه.
          const errBody = await resp.text().catch(() => '');
          window.logEvent('AUTH', 'httpFail', { url: url, status: resp.status, body: errBody.slice(0, 150) });
        }
      } catch (err) {
        // ⚠️ فیکس: قبلاً هر خطای شبکه/fetch (مثلاً CORS، قطعی اتصال، آدرس
        // اشتباه) کاملاً بی‌صدا نادیده گرفته می‌شد — دقیقاً همون چیزی که
        // باعث می‌شد نتونیم بفهمیم چرا لاگین همیشه شکست می‌خوره.
        window.logEvent('AUTH', 'fetchErr', { url: url, err: err.message || err });
      }
    }

    if (authData) {
      // ⚠️ فیکس: قبلاً فقط وقتی توکن بود authData برگردونده می‌شد. بعد از
      // سخت‌سازی سمت سرور، مسیر «تأییدنشده» (initData نداریم، فقط آیدی
      // تلگرام) عمداً دیگه توکن صادر نمی‌کنه — ولی هویت و نام نمایشی رو
      // برمی‌گردونه. بدون این فیکس، یه رفت‌وبرگشت اضافه به /site/session
      // می‌خورد که همون جواب رو می‌داد.
      if (authData.token) this.setToken(authData.token);
      return authData;
    }

    return await this.getSession();
  },

  async getSession() {
    const headers = this.getHeaders();
    try {
      const resp = await fetch(`${this.baseUrl}/session`, { headers });
      if (resp.status === 401) {
        this.clearToken();
        window.logEventThrottled('AUTH', 'sessionExpired', {}, 60000);
        return null;
      }
      if (!resp.ok) {
        // ⚠️ فیکس: قبلاً این حالت (نه ۴۰۱، ولی بازم ناموفق — مثلاً ۵۰۰) کاملاً
        // بی‌صدا null برمی‌گردوند.
        window.logEvent('AUTH', 'sessionHttpFail', { status: resp.status });
        return null;
      }
      const data = await resp.json();
      if (data && data.token) {
        this.setToken(data.token);
      }
      return data;
    } catch (e) {
      // ⚠️ فیکس: خطای شبکه/fetch اینجا هم قبلاً کاملاً بی‌صدا بود.
      window.logEvent('AUTH', 'sessionErr', { err: e.message || e });
      return null;
    }
  },

  async getSignals() {
    const startMs = Date.now();
    try {
      const resp = await fetch(`${this.baseUrl}/signals?limit=200`, { headers: this.getHeaders() });
      if (!resp.ok) {
        window.logEvent('SIGNALS', 'httpFail', { status: resp.status });
        return [];
      }
      const data = await resp.json();

      let list = [];
      if (Array.isArray(data)) {
        list = data;
      } else if (data && typeof data === 'object') {
        list = data.items || data.signals || data.feed || data.data || [];
      }

      // ⚠️ throttled: این تابع مکرر صدا زده می‌شه (لود اولیه، pull-refresh)؛
      // اگه نتیجه عوض نشده باشه، خط جدید نمی‌فرسته، فقط شمارش می‌کنه —
      // دقیقاً همون چیزی که جلوی له‌شدن لاگ‌های مهم زیر ۱۴ بار
      // loadSignalsOK تو ۴۰ ثانیه رو می‌گیره.
      window.logEventThrottled('SIGNALS', 'fetch', { status: 'OK', count: list.length, ms: Date.now() - startMs }, 30000);
      return list;
    } catch (e) {
      window.logEvent('SIGNALS', 'fetchErr', { err: e.message || e });
      return [];
    }
  },

  async getLeaderboard() {
    try {
      const resp = await fetch(`${this.baseUrl}/leaderboard?period=week`, { headers: this.getHeaders() });
      if (!resp.ok) {
        window.logEvent('LEADERBOARD', 'httpFail', { status: resp.status });
        return { callers: [], signal_givers: [] };
      }
      return await resp.json();
    } catch (e) {
      window.logEvent('LEADERBOARD', 'fetchErr', { err: e.message || e });
      return { callers: [], signal_givers: [] };
    }
  },

  async getContent(key) {
    try {
      const resp = await fetch(`${this.baseUrl}/content/${key}`, { headers: this.getHeaders() });
      if (!resp.ok) {
        window.logEvent('CONTENT', 'httpFail', { key: key, status: resp.status });
        return [];
      }
      return await resp.json();
    } catch (e) {
      window.logEvent('CONTENT', 'fetchErr', { key: key, err: e.message || e });
      return [];
    }
  },

  async createSignal(payload) {
    return await fetch(`${this.baseUrl}/signals`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
  },

  async updateSignalResult(id, result, status) {
    return await fetch(`${this.baseUrl}/signals/${id}/result`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ result, outcome_status: status })
    });
  },

  async deleteSignal(id) {
    return await fetch(`${this.baseUrl}/signals/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders()
    });
  },

  async getTraderProfile(userId) {
    try {
      const resp = await fetch(`${this.baseUrl}/traders/${userId}`, { headers: this.getHeaders() });
      return resp.ok ? await resp.json() : null;
    } catch (e) {
      return null;
    }
  }
};

/* ══════════════════════════════════════════════════════════════════════
 * 🚨 فیکس ریشه‌ای: `const API = {...}` توی یه classic script هیچ‌وقت
 *   `window.API` نمی‌سازه (فقط binding لغوی global). تمام گاردهای
 *   `if (window.API && ...)` توی app.js به همین دلیل رد می‌شدن و
 *   احراز هویت/لود سیگنال اصلاً اجرا نمی‌شد.
 *   escapeHtml/safeUrl چون function declaration ان از قبل روی window
 *   می‌نشستن، ولی برای خوانایی صریح شدن.
 * ══════════════════════════════════════════════════════════════════════ */
window.API = API;
window.escapeHtml = escapeHtml;
window.safeUrl = safeUrl;
if (window.MHLog) MHLog.info('BOOT', 'api.js ready', { build: window.__MH_BUILD });
