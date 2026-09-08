/**
 * MemeLand Core Controller (v7.2.0 - Immediate Admin Identification)
 */

window.sendRemoteLog = function(msg) {
  if (!msg) return;
  try {
    fetch('/site/client-log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ msg: String(msg) })
    }).catch(() => {});
  } catch (e) {}
};

window.addEventListener('error', function(e) {
  window.sendRemoteLog(`JSERR: ${e.message} @ ${e.filename || 'app.js'}:${e.lineno}`);
});

window.addEventListener('unhandledrejection', function(e) {
  const reason = e.reason ? (e.reason.message || String(e.reason)) : 'Unknown rejection';
  window.sendRemoteLog(`JSERR: Promise - ${reason}`);
});

const App = {
  _initialized: false,

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
    } else if (window.TGBridge && typeof TGBridge.haptic === 'function') {
      TGBridge.haptic(type);
    }
  },

  async init() {
    if (this._initialized) return;
    this._initialized = true;

    if (window.TGBridge && typeof TGBridge.init === 'function') {
      TGBridge.init();
    }
    this.startSplashTicker();
    
    const safetyTimer = setTimeout(() => this.hideSplash(), 2200);

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
        window.sendRemoteLog(`[APP] AuthNotice: ${e.message || e}`);
      }
      this.state.session = session;

      await this.loadSignals();
      this.updateUserInterface();

      if (window.Views && typeof Views.renderCurrent === 'function') {
        Views.renderCurrent();
      }

      const tgUid = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      const isAdm = Boolean(session?.is_admin || session?.is_super_admin || tgUid === 2088114041);
      window.sendRemoteLog(`APP: Ready (sessUid=${session?.telegram_id || 'none'}, tgUid=${tgUid || 'none'}, adm=${isAdm}, sigCount=${this.state.signals.length})`);

      if (window.PullRefresh && typeof PullRefresh.init === 'function') {
        PullRefresh.init('#tab-signals', async (isSilent) => {
          await App.loadSignals();
          if (window.Views) Views.renderSignalsList();
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
      window.sendRemoteLog(`JSERR: Init ${err.message || err}`);
    } finally {
      clearTimeout(safetyTimer);
      setTimeout(() => this.hideSplash(), 150);
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
    }, 600);
  },

  hideSplash() {
    if (this._splashInterval) clearInterval(this._splashInterval);
    const splash = document.getElementById('splashScreen');
    if (splash) {
      splash.classList.add('fade-out');
      setTimeout(() => { splash.style.display = 'none'; }, 350);
    }
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

    // تایید شناسه ادمین در کلاینت برای جلوگیری از گیر کردن در حالت عادی
    const isSuper = Boolean(s?.is_super_admin === true || quota?.is_super_admin === true || Number(tid) === 2088114041);
    const isAdmin = Boolean(isSuper || s?.is_admin === true || quota?.is_admin === true || s?.role === 'admin');

    let roleKey = 'rookie';
    if (isSuper) {
      roleKey = 'super_admin';
    } else if (quota?.role_key && quota.role_key !== 'rookie') {
      roleKey = quota.role_key;
    } else if (s?.role && s.role !== 'member') {
      roleKey = s.role;
    } else if (isAdmin) {
      roleKey = 'admin';
    }

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
    
    const displayRole = isSuper ? '👑 Super Admin' : (isAdmin ? '💎 مدیر سیستم' : (quota?.display_role || 'عضو رسمی'));
    if (profileRole) profileRole.textContent = displayRole;
    if (profileQuota) {
      const consumed = quota?.signals_today || 0;
      const total = isAdmin ? 999 : (quota?.daily_limit || 5);
      profileQuota.textContent = `${consumed} از ${total} مصرف شده`;
    }

    if (headerAdmin) headerAdmin.style.display = isAdmin ? 'inline-block' : 'none';
    if (adminSec) adminSec.style.display = isAdmin ? 'block' : 'none';
    if (adminFab) adminFab.style.display = isAdmin ? 'flex' : 'none';
  },

  switchTab(tabName) {
    this.haptic('selection');
    this.state.currentTab = tabName;

    if (window.Views && typeof Views.closeBottomSheet === 'function') {
      Views.closeBottomSheet();
    }

    document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.bottom-nav .nav-btn').forEach(el => el.classList.remove('active'));

    const activeView = document.getElementById(`tab-${tabName}`);
    if (activeView) activeView.classList.add('active');

    const tabMap = { signals: 0, leaderboard: 1, academy: 2, profile: 3 };
    const navBtn = document.querySelectorAll('.bottom-nav .nav-btn')[tabMap[tabName]];
    if (navBtn) navBtn.classList.add('active');

    if (window.TGBridge) TGBridge.syncBackButton(tabName !== 'signals');
    if (window.Views) Views.renderCurrent();
  },

  setSignalSubTab(subTab) {
    this.haptic('selection');
    this.state.signalSubTab = subTab;
    document.getElementById('subTabActive')?.classList.toggle('active', subTab === 'active');
    document.getElementById('subTabClosed')?.classList.toggle('active', subTab === 'closed');
    if (window.Views) Views.renderSignalsList();
  },

  setCategory(cat) {
    this.haptic('selection');
    this.state.category = cat;
    document.querySelectorAll('#catFilterChips .chip').forEach(c => {
      c.classList.toggle('active', c.getAttribute('onclick')?.includes(`'${cat}'`));
    });
    if (window.Views) Views.renderSignalsList();
  },

  onSearchInput(val) {
    this.state.searchQuery = (val || '').trim().toLowerCase();
    if (window.Views) Views.renderSignalsList();
  },

  async loadSignals() {
    try {
      if (window.API && typeof API.getSignals === 'function') {
        const res = await API.getSignals();
        this.state.signals = Array.isArray(res) ? res : (res?.signals || res?.items || []);
      }
      const openCount = (this.state.signals || []).filter(s => s.outcome_status === 'open' || s.status === 'open').length;
      const countBadge = document.getElementById('activeCountBadge');
      if (countBadge) countBadge.textContent = openCount;
    } catch (e) {
      this.state.signals = [];
    }
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => App.init());
} else {
  App.init();
}