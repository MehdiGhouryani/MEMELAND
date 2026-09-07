/**
 * MemeLand Core Controller (Ultra-Lightweight v5.8.0)
 */

const App = {
  state: {
    currentTab: 'signals',
    signalSubTab: 'active',
    category: 'all',
    searchQuery: '',
    session: null,
    signals: [],
    leaderboardType: 'callers',
    leaderboardData: { callers: [], signal_givers: [] },
    academyTab: 'strategies',
    strategies: [],
    articles: [],
    staffList: []
  },

  async init() {
    if (window.TGBridge) TGBridge.init();
    this.startSplashTicker();
    const safetyTimer = setTimeout(() => this.hideSplash(), 3000);

    try {
      let session = null;
      try {
        session = await API.authenticateWebApp();
        if (!session) session = await API.getSession();
      } catch (e) {}
      this.state.session = session;

      await this.loadSignals();
      this.updateUserInterface();
      Views.renderCurrent();

      if (window.PullRefresh && typeof PullRefresh.init === 'function') {
        PullRefresh.init('#tab-signals', async (isSilent) => {
          await App.loadSignals();
          Views.renderSignalsList();
          if (!isSilent) {
            const fresh = await API.getSession();
            if (fresh) {
              App.state.session = fresh;
              App.updateUserInterface();
            }
          }
        });
      }
    } catch (err) {
      console.error('Init error:', err);
    } finally {
      clearTimeout(safetyTimer);
      setTimeout(() => this.hideSplash(), 300);
    }
  },

  startSplashTicker() {
    const statusEl = document.getElementById('splashStatusText');
    if (!statusEl) return;
    const steps = ['در حال اتصال به شبکه آلفا...', 'اسکن پامپ‌های دکس...', 'همگام‌سازی سهمیه...'];
    let idx = 0;
    this._splashInterval = setInterval(() => {
      idx = (idx + 1) % steps.length;
      statusEl.textContent = steps[idx];
    }, 700);
  },

  hideSplash() {
    if (this._splashInterval) clearInterval(this._splashInterval);
    const splash = document.getElementById('splashScreen');
    if (splash) splash.classList.add('fade-out');
  },

  updateUserInterface() {
    const s = this.state.session;
    const headerName = document.getElementById('headerUserName');
    const headerAdmin = document.getElementById('headerAdminBadge');
    const profileName = document.getElementById('profileFullName');
    const profileUser = document.getElementById('profileUsername');
    const profileId = document.getElementById('profileTelegramId');
    const profileRole = document.getElementById('profileRoleText');
    const profileQuota = document.getElementById('profileQuotaText');
    const adminSec = document.getElementById('adminPanelSection');
    const adminFab = document.getElementById('adminFabBtn');
    const avatarFrame = document.getElementById('profileAvatarFrame');
    const avatarContainer = document.getElementById('avatarSvgContainer');
    const avatarMiniBadge = document.getElementById('avatarMiniBadge');

    const tid = s ? (s.telegram_id || s.user?.id || window.Telegram?.WebApp?.initDataUnsafe?.user?.id) : null;
    const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
    const displayName = s?.display_name || s?.user?.first_name || s?.first_name || tgUser?.first_name || 'کاربر تلگرام';
    const username = s?.username || s?.user?.username || tgUser?.username || null;
    const isAdmin = Boolean(s && (s.role === 'admin' || s.is_admin === true));
    const quota = s?.quota || null;

    let roleKey = 'rookie';
    if (isAdmin) roleKey = quota?.is_super_admin ? 'super_admin' : 'admin';
    else if (quota?.role_key) roleKey = quota.role_key;
    else if (s?.role === 'admin') roleKey = 'admin';

    if (avatarContainer && window.AvatarRenderer) {
      avatarContainer.innerHTML = AvatarRenderer.getAvatarSvg(roleKey);
    }
    if (avatarMiniBadge && window.AvatarRenderer) {
      avatarMiniBadge.textContent = AvatarRenderer.getRoleMiniBadge(roleKey);
    }
    if (avatarFrame) {
      avatarFrame.className = `avatar-frame theme-${roleKey}`;
    }

    if (s && (tid || s.token)) {
      if (headerName) headerName.textContent = displayName;
      if (profileName) profileName.textContent = displayName;
      if (profileUser) profileUser.textContent = username ? `@${username.replace('@', '')}` : '—';
      if (profileId) profileId.textContent = tid ? String(tid) : '—';
      if (profileRole && quota) profileRole.textContent = quota.display_role || 'عضو رسمی';
      if (profileQuota && quota) profileQuota.textContent = `${quota.signals_today || 0} از ${quota.daily_limit || 5} مصرف شده`;

      if (headerAdmin) headerAdmin.style.display = isAdmin ? 'inline-block' : 'none';
      if (adminSec) adminSec.style.display = isAdmin ? 'block' : 'none';
      if (adminFab) adminFab.style.display = isAdmin ? 'flex' : 'none';
    }
  },

  switchTab(tabName) {
    if (window.TGBridge) TGBridge.haptic('selection');
    this.state.currentTab = tabName;
    document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.bottom-nav .nav-btn').forEach(el => el.classList.remove('active'));

    const activeView = document.getElementById(`tab-${tabName}`);
    if (activeView) activeView.classList.add('active');

    const tabMap = { signals: 0, leaderboard: 1, academy: 2, profile: 3 };
    const navBtn = document.querySelectorAll('.bottom-nav .nav-btn')[tabMap[tabName]];
    if (navBtn) navBtn.classList.add('active');

    if (window.TGBridge) TGBridge.syncBackButton(tabName !== 'signals');
    Views.renderCurrent();
  },

  setSignalSubTab(subTab) {
    if (window.TGBridge) TGBridge.haptic('selection');
    this.state.signalSubTab = subTab;
    document.getElementById('subTabActive')?.classList.toggle('active', subTab === 'active');
    document.getElementById('subTabClosed')?.classList.toggle('active', subTab === 'closed');
    Views.renderSignalsList();
  },

  setCategory(cat) {
    if (window.TGBridge) TGBridge.haptic('selection');
    this.state.category = cat;
    document.querySelectorAll('#catFilterChips .chip').forEach(c => {
      c.classList.toggle('active', c.getAttribute('onclick')?.includes(`'${cat}'`));
    });
    Views.renderSignalsList();
  },

  onSearchInput(val) {
    this.state.searchQuery = (val || '').trim().toLowerCase();
    Views.renderSignalsList();
  },

  async loadSignals() {
    try {
      this.state.signals = await API.getSignals();
      const openCount = (this.state.signals || []).filter(s => s.outcome_status === 'open').length;
      const countBadge = document.getElementById('activeCountBadge');
      if (countBadge) countBadge.textContent = openCount;
    } catch (e) {
      this.state.signals = [];
    }
  }
};

window.addEventListener('DOMContentLoaded', () => App.init());