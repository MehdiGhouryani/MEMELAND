/**
 * MemeLand API Service & Session Manager (v7.0.0)
 * هماهنگ با چندلایه احراز هویت تلگرام و توکن‌های نشست
 */

const API = {
  baseUrl: '/site',

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

    if (!initData) {
      return await this.getSession();
    }

    try {
      let resp = await fetch('/webapp-auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ init_data: initData })
      });

      if (!resp.ok) {
        resp = await fetch(`${this.baseUrl}/webapp-auth`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData })
        });
      }

      if (!resp.ok) return null;

      const data = await resp.json();
      if (data && data.token) {
        this.setToken(data.token);
      }
      return data;
    } catch (e) {
      console.warn('WebApp Auth Request Failed:', e);
      return null;
    }
  },

  async getSession() {
    try {
      const resp = await fetch(`${this.baseUrl}/session`, { headers: this.getHeaders() });
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
      if (!resp.ok) return [];
      const data = await resp.json();
      if (Array.isArray(data)) return data;
      return (data && data.items) ? data.items : [];
    } catch (e) {
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