/**
 * MemeLand API Service & Session Manager (v7.6.0 - Robust Token Sanitization & Direct Array Parser)
 */

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

  log(msg) {
    if (window.sendRemoteLog) {
      window.sendRemoteLog(`[API] ${msg}`);
    }
  },

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
    this.log(`AuthAttempt: hasTg=${Boolean(tg)} initDataLen=${initData.length} tgUserId=${uid || 'none'}`);

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
          this.log(`AuthSuccess: url=${url} uid=${authData.telegram_id || uid} adm=${Boolean(authData.is_admin)}`);
          break;
        } else {
          // ⚠️ فیکس: قبلاً این حالت (سرور جواب داد ولی status خطا بود، مثلاً
          // ۴۰۰/۴۰۱) اصلاً لاگ نمی‌شد — یعنی هیچ ردی از این‌که چرا لاگین رد
          // شده باقی نمی‌موند. الان status و متن خطای واقعی سرور ثبت می‌شه.
          const errBody = await resp.text().catch(() => '');
          this.log(`AuthHTTPFail: url=${url} status=${resp.status} body=${errBody.slice(0, 200)}`);
        }
      } catch (err) {
        // ⚠️ فیکس: قبلاً هر خطای شبکه/fetch (مثلاً CORS، قطعی اتصال، آدرس
        // اشتباه) کاملاً بی‌صدا نادیده گرفته می‌شد — دقیقاً همون چیزی که
        // باعث می‌شد نتونیم بفهمیم چرا لاگین همیشه شکست می‌خوره.
        this.log(`AuthFetchErr: url=${url} err=${err.message || err}`);
      }
    }

    if (authData && authData.token) {
      this.setToken(authData.token);
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
        return null;
      }
      if (!resp.ok) {
        // ⚠️ فیکس: قبلاً این حالت (نه ۴۰۱، ولی بازم ناموفق — مثلاً ۵۰۰) کاملاً
        // بی‌صدا null برمی‌گردوند.
        this.log(`GetSessionHTTPFail: status=${resp.status}`);
        return null;
      }
      const data = await resp.json();
      if (data && data.token) {
        this.setToken(data.token);
      }
      return data;
    } catch (e) {
      // ⚠️ فیکس: خطای شبکه/fetch اینجا هم قبلاً کاملاً بی‌صدا بود.
      this.log(`GetSessionErr: ${e.message || e}`);
      return null;
    }
  },

  async getSignals() {
    try {
      const resp = await fetch(`${this.baseUrl}/signals?limit=200`, { headers: this.getHeaders() });
      if (!resp.ok) {
        this.log(`SignalsHTTPFail: status=${resp.status}`);
        return [];
      }
      const data = await resp.json();
      
      let list = [];
      if (Array.isArray(data)) {
        list = data;
      } else if (data && typeof data === 'object') {
        list = data.items || data.signals || data.feed || data.data || [];
      }

      this.log(`SignalsFetched: count=${list.length}`);
      return list;
    } catch (e) {
      this.log(`SignalsCatchErr: ${e.message}`);
      return [];
    }
  },

  async getLeaderboard() {
    try {
      const resp = await fetch(`${this.baseUrl}/leaderboard?period=week`, { headers: this.getHeaders() });
      return resp.ok ? await resp.json() : { callers: [], signal_givers: [] };
    } catch (e) {
      return { callers: [], signal_givers: [] };
    }
  },

  async getContent(key) {
    try {
      const resp = await fetch(`${this.baseUrl}/content/${key}`, { headers: this.getHeaders() });
      return resp.ok ? await resp.json() : [];
    } catch (e) {
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