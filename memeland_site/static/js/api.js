/**
 * MemeLand API Service & Session Manager (v7.1.0 - Smart Diagnostic & Multi-Route Auth)
 */

const API = {
  baseUrl: '/site',

  log(msg) {
    if (window.sendRemoteLog) {
      window.sendRemoteLog(`[API] ${msg}`);
    }
  },

  getToken() {
    return localStorage.getItem('mh_session_token') || 
           localStorage.getItem('ml_token') || 
           sessionStorage.getItem('ml_token') || '';
  },

  setToken(token) {
    if (!token) return;
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
    const uid = tg?.initDataUnsafe?.user?.id || 'none';

    if (!initData) {
      this.log(`AuthSkip: initData empty (uid=${uid})`);
      return await this.getSession();
    }

    // مسیرهای محتمل بک‌اند به ترتیب اولویت
    const endpoints = ['/site/auth', '/site/webapp-auth', '/webapp-auth'];
    let authData = null;
    let lastStatus = 0;

    for (const url of endpoints) {
      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData })
        });
        lastStatus = resp.status;
        if (resp.ok) {
          authData = await resp.json();
          this.log(`AuthSuccess: endpoint=${url} uid=${authData.telegram_id || uid} adm=${Boolean(authData.is_admin)}`);
          break;
        }
      } catch (err) {
        // ادامه تست روت بعدی در صورت بروز خطای شبکه
      }
    }

    if (authData && authData.token) {
      this.setToken(authData.token);
      return authData;
    }

    this.log(`AuthFailed: All routes failed. LastHTTP=${lastStatus}`);
    return await this.getSession();
  },

  async getSession() {
    const token = this.getToken();
    const headers = this.getHeaders();
    try {
      const resp = await fetch(`${this.baseUrl}/session`, { headers });
      if (resp.status === 401) {
        this.clearToken();
        this.log('SessExpired: HTTP 401');
        return null;
      }
      if (!resp.ok) {
        this.log(`SessFailed: HTTP ${resp.status}`);
        return null;
      }
      const data = await resp.json();
      if (data && data.token) {
        this.setToken(data.token);
      }
      this.log(`SessActive: uid=${data.telegram_id} adm=${Boolean(data.is_admin)}`);
      return data;
    } catch (e) {
      this.log(`SessNetErr: ${e.message}`);
      return null;
    }
  },

  async getSignals() {
    try {
      const resp = await fetch(`${this.baseUrl}/signals?limit=200`, { headers: this.getHeaders() });
      if (!resp.ok) {
        this.log(`SignalsErr: HTTP ${resp.status}`);
        return [];
      }
      const data = await resp.json();
      const items = Array.isArray(data) ? data : (data && data.items ? data.items : (data.signals || []));
      this.log(`SignalsLoaded: count=${items.length}`);
      return items;
    } catch (e) {
      this.log(`SignalsNetErr: ${e.message}`);
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