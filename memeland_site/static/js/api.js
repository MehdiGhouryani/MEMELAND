/**
 * API Service & Session Manager
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
      if (data.token) {
        localStorage.setItem('mh_session_token', data.token);
      }
      return data;
    } catch (e) {
      console.error('WebApp Auth Failed:', e);
      return null;
    }
  },

  async getSession() {
    const token = this.getToken();
    if (!token) return null;
    try {
      const resp = await fetch(`${this.baseUrl}/session`, { headers: this.getHeaders() });
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
    return data.items || [];
  },

  async getLeaderboard() {
    const resp = await fetch(`${this.baseUrl}/leaderboard?period=week`);
    return resp.ok ? await resp.json() : { callers: [], signal_givers: [] };
  },

  async getRatings() {
    const resp = await fetch(`${this.baseUrl}/ratings/all`);
    return resp.ok ? await resp.json() : [];
  },

  async getContent(key) {
    const resp = await fetch(`${this.baseUrl}/content/${key}`);
    return resp.ok ? await resp.json() : [];
  },

  async setContent(key, data) {
    return await fetch(`${this.baseUrl}/content/${key}`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data)
    });
  },

  async claimRole(role, pin) {
    const resp = await fetch(`${this.baseUrl}/claim-role`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ role, pin })
    });
    return resp.ok;
  },

  async updateProfileName(displayName) {
    const resp = await fetch(`${this.baseUrl}/profile`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ display_name: displayName })
    });
    return resp.ok ? await resp.json() : null;
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
  }
};