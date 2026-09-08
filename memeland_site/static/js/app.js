/**
 * MemeLand Core Controller (v7.0.0 - Stealth Design & Native Haptics)
 */

window.sendRemoteLog = function(msg) {
  // Only send critical runtime errors to prevent server log inflation
  if (!msg || (!msg.startsWith('JS-ERR:') && !msg.startsWith('AUTH_CRIT:'))) return;
  try {
    fetch('/site/client-log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ msg: msg })
    }).catch(() => {});
  } catch (e) {}
};

window.addEventListener('error', function(e) {
  window.sendRemoteLog(`JS-ERR: ${e.message} @ ${e.filename || 'app.js'}:${e.lineno}`);
});

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

  haptic(type = 'light') {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === 'selection') window.Telegram.WebApp.HapticFeedback.selectionChanged();
      else if (type === 'success' || type === 'error') window.Telegram.WebApp.HapticFeedback.notificationOccurred(type);
      else window.Telegram.WebApp.HapticFeedback.impactOccurred(type);
    } else if (window.TGBridge) {
      TGBridge.haptic(type);
    }
  },

  async init() {
    if (window.TGBridge) TGBridge.init();
    this.startSplashTicker();
    const safetyTimer = setTimeout(() => this.hideSplash(), 2800);

    try {
      let session = null;
      try {
        if (window.API && typeof API.authenticateWebApp === 'function') {
          session = await API.authenticateWebApp();
        }
        if (!session && window.API && typeof API.getSession === 'function') {
          session = await API.getSession();
        }
      } catch (e) {
        console.warn('Session fetch warning:', e);
      }
      this.state.session = session;

      await this.loadSignals();
      this.updateUserInterface();
      Views.renderCurrent();

      if (window.PullRefresh && typeof PullRefresh.init === 'function') {
        PullRefresh.init('#tab-signals', async (isSilent) => {
          await App.loadSignals();
          Views.renderSignalsList();
          if (!isSilent && window.API && typeof API.getSession === 'function') {
            const fresh = await API.getSession();
            if (fresh) {
              App.state.session = fresh;
              App.updateUserInterface();
            }
          }
        });
      }
    } catch (err) {
      window.sendRemoteLog(`JS-ERR: Init ${err.message || err}`);
    } finally {
      clearTimeout(safetyTimer);
      setTimeout(() => this.hideSplash(), 250);
    }
  },

  startSplashTicker() {
    const statusEl = document.getElementById('splashStatusText');
    if (!statusEl) return;
    const steps = ['در حال همگام‌سازی شبکه آلفا...', 'اسکن پامپ‌های دکس...', 'دریافت وضعیت سهمیه...'];
    let idx = 0;
    this._splashInterval = setInterval(() => {
      idx = (idx + 1) % steps.length;
      statusEl.textContent = steps[idx];
    }, 650);
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

    const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
    const tid = s ? (s.telegram_id || s.user?.id || tgUser?.id) : tgUser?.id;
    const displayName = s?.display_name || s?.user?.first_name || s?.first_name || tgUser?.first_name || 'کاربر تلگرام';
    const username = s?.username || s?.user?.username || tgUser?.username || null;
    const quota = s?.quota || null;
    const photoUrl = s?.photo_url || s?.user?.photo_url || tgUser?.photo_url || null;

    // تشخیص قاطع وضعیت ادمین
    const isSuper = Boolean(s?.is_super_admin === true || quota?.is_super_admin === true);
    const isAdmin = Boolean(isSuper || s?.is_admin === true || quota?.is_admin === true || s?.role === 'admin');

    let roleKey = 'rookie';
    if (isSuper) roleKey = 'super_admin';
    else if (isAdmin) roleKey = 'admin';
    else if (quota?.role_key && quota.role_key !== 'rookie') roleKey = quota.role_key;

    // رندر هوشمند آواتار
    if (avatarContainer) {
      if (photoUrl) {
        avatarContainer.innerHTML = `<img src="${photoUrl}" alt="${displayName}" style="width:100%; height:100%; object-fit:cover; border-radius:50%; display:block;" onerror="this.outerHTML=window.AvatarRenderer ? AvatarRenderer.getAvatarSvg('${roleKey}') : ''">`;
      } else if (window.AvatarRenderer) {
        avatarContainer.innerHTML = AvatarRenderer.getAvatarSvg(roleKey);
      }
    }

    if (avatarMiniBadge && window.AvatarRenderer) {
      avatarMiniBadge.textContent = AvatarRenderer.getRoleMiniBadge(roleKey);
    }
    if (avatarFrame) {
      avatarFrame.className = `avatar-frame theme-${roleKey}`;
    }

    if (headerName) headerName.textContent = displayName;
    if (profileName) profileName.textContent = displayName;
    if (profileUser) profileUser.textContent = username ? `@${username.replace('@', '')}` : '—';
    if (profileId) profileId.textContent = tid ? String(tid) : '—';
    if (profileRole) profileRole.textContent = quota?.display_role || (isAdmin ? '👑 مدیر ارشد' : 'عضو رسمی');
    if (profileQuota) profileQuota.textContent = `${quota?.signals_today || 0} از ${quota?.daily_limit || (isAdmin ? 999 : 5)} مصرف شده`;

    if (headerAdmin) headerAdmin.style.display = isAdmin ? 'inline-block' : 'none';
    if (adminSec) adminSec.style.display = isAdmin ? 'block' : 'none';
    if (adminFab) adminFab.style.display = isAdmin ? 'flex' : 'none';
  },

  switchTab(tabName) {
    this.haptic('selection');
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
    this.haptic('selection');
    this.state.signalSubTab = subTab;
    document.getElementById('subTabActive')?.classList.toggle('active', subTab === 'active');
    document.getElementById('subTabClosed')?.classList.toggle('active', subTab === 'closed');
    Views.renderSignalsList();
  },

  setCategory(cat) {
    this.haptic('selection');
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
      if (window.API && typeof API.getSignals === 'function') {
        this.state.signals = await API.getSignals();
      }
      const openCount = (this.state.signals || []).filter(s => s.outcome_status === 'open').length;
      const countBadge = document.getElementById('activeCountBadge');
      if (countBadge) countBadge.textContent = openCount;
    } catch (e) {
      this.state.signals = [];
    }
  }
};

window.addEventListener('DOMContentLoaded', () => App.init());