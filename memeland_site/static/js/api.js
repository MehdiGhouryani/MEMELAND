/**
 * MemeLand API Service & Session Manager (v7.6.0 - Robust Token Sanitization & Direct Array Parser)
 */

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
        }
      } catch (err) {}
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
      if (!resp.ok) return null;
      const data = await resp.json();
      if (data && data.token) {
        this.setToken(data.token);
      }
      return data;
    } catch (e) {
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