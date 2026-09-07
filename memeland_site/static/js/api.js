/**
 * API Service & Session Manager
 * نسخه اصلاح‌شده و پایدار
 */

const API = {
  baseUrl: '/site',

  getToken() {
    return localStorage.getItem('mh_session_token') || '';
  },

  getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const token = this.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
  },

  async authenticateWebApp() {
    const tg = window.Telegram?.WebApp;
    if (!tg || !tg.initData) return null;

    try {
      const resp = await fetch('/webapp-auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ init_data: tg.initData })
      });
      if (!resp.ok) return null;
      const data = await resp.json();
      if (data && data.token) {
        localStorage.setItem('mh_session_token', data.token);
      }
      return data;
    } catch (e) {
      console.warn('WebApp Auth Request Failed:', e);
      return null;
    }
  },

  async getSession() {
    const token = this.getToken();
    if (!token) return null;
    try {
      const resp = await fetch(`${this.baseUrl}/session`, { headers: this.getHeaders() });
      if (resp.status === 401) {
        localStorage.removeItem('mh_session_token');
        return null;
      }
      if (!resp.ok) return null;
      return await resp.json();
    } catch (e) {
      return null;
    }
  },

  async getSignals() {
    const resp = await fetch(`${this.baseUrl}/signals?limit=200`, { headers: this.getHeaders() });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    // پشتیبانی هم‌زمان از ساختار آبجکت یا آرایه خام
    if (Array.isArray(data)) return data;
    return (data && data.items) ? data.items : [];
  },

  async getLeaderboard() {
    try {
      const resp = await fetch(`${this.baseUrl}/leaderboard?period=week`);
      return resp.ok ? await resp.json() : { callers: [], signal_givers: [] };
    } catch (e) {
      return { callers: [], signal_givers: [] };
    }
  },

  async getContent(key) {
    try {
      const resp = await fetch(`${this.baseUrl}/content/${key}`);
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
  },
};

