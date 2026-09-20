/**
 * MemeLand Core Controller (v7.6.0 - Guaranteed Session Sync & Signals Feed)
 */

// ⚠️ فیکس مهم: قبلاً این فایل خودش یه sendRemoteLog جدا + دو تا error/
// unhandledrejection listener جداگانه داشت که رو نسخه‌ی index.html سوار
// می‌شدن (window.addEventListener اجازه می‌ده چندتا listener هم‌زمان باشن).
// نتیجه‌ش این بود که یه خطای واحد گاهی ۲ بار جدا لاگ می‌شد (یکی از اینجا،
// یکی از index.html) — دقیقاً همون الگوی «JSERR: Script error. @ :0» و
// «... @ app.js:0» تقریباً هم‌زمانی که تو لاگ‌های قبلی دیده شد. رشته‌ی
// "app.js" اونجا صرفاً fallback هاردکد همین هندلر بود وقتی filename واقعی
// در دسترس نبود، نه لزوماً محل واقعی خطا. الان همه‌چی از یه جا (index.html،
// با logEvent/sid یکسان) میاد — اینجا فقط از همون استفاده می‌کنیم.

// ⚠️ خط اثر انگشت بوت (نگاه کن به توضیح مشابه تو api.js).
try {
  if (window.logEvent) window.logEvent('BOOT', 'app.js loaded', { build: window.__MH_BUILD || '?' });
} catch (e) {}

const App = {
  _initialized: false,

  state: {
    currentTab: 'signals',
    signalSubTab: 'active',
    searchQuery: '',
    session: null,
    signals: [],
    leaderboardType: 'callers',
    leaderboardData: { callers: [], signal_givers: [] },
    academyTab: 'strategies',
    strategies: [],
    articles: [],
    staffList: [],
    // ⚠️ فیچر جدید: فیلتر/سورت سیگنال‌ها (دکمه ⚙️ کنار جستجو). مقدار
    // پیش‌فرض «همه چیز، جدیدترین اول» — دقیقاً همون رفتار قبلی، تا کسی که
    // هیچ‌وقت فیلتر نمی‌زنه چیزی عوض نشه.
    signalFilters: { sort: 'newest', timeRange: 'all', channel: 'all', risk: 'all' }
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

  // فیلتر انتخابی کاربر بین باز کردن‌های بعدی اپ باقی می‌مونه (دقیقاً مثل
  // اکثر اپ‌ها/سایت‌ها — مثلاً همون رفتار فیلتر تو اپ‌های فروشگاهی) تا هربار
  // مجبور نشه از اول تنظیم کنه.
  loadSignalFilters() {
    try {
      const raw = localStorage.getItem('mh_signal_filters');
      if (raw) {
        const saved = JSON.parse(raw);
        this.state.signalFilters = Object.assign({}, this.state.signalFilters, saved);
      }
    } catch (e) { /* دیتای خراب تو localStorage نباید کل اپ رو بترکونه */ }
  },

  saveSignalFilters() {
    try {
      localStorage.setItem('mh_signal_filters', JSON.stringify(this.state.signalFilters));
    } catch (e) {}
  },

  isSignalFiltersDefault() {
    const f = this.state.signalFilters;
    return f.sort === 'newest' && f.timeRange === 'all' && f.channel === 'all' && f.risk === 'all';
  },

  // ⚠️ فیکس: بعد از تبدیل ۳ فیلتر به چیپ‌های همیشه-نمایان (که خودشون مقدار
  // فعلی‌شون رو نشون می‌دن)، فقط سطح ریسک پشت آیکونه — پس نقطه‌ی فعال باید
  // فقط همینو نشون بده، نه هر ۴ تا رو (وگرنه با انتخاب یه کانال خاص، نقطه
  // رو آیکون ریسک روشن می‌شد که گمراه‌کننده‌ست).
  updateFilterActiveDot() {
    const dot = document.getElementById('filterActiveDot');
    if (dot) dot.style.display = (this.state.signalFilters.risk === 'all') ? 'none' : 'block';
  },

  async init() {
    if (this._initialized) return;
    this._initialized = true;

    this.loadSignalFilters();

    if (window.TGBridge && typeof TGBridge.init === 'function') {
      TGBridge.init();
    } else if (window.logEvent) {
      window.logEvent('BOOT', 'guardFail', { check: 'TGBridge.init', hasTGBridge: Boolean(window.TGBridge) });
    }
    this.startSplashTicker();

    // ⚠️ فیکس: قبلاً splashStartedAt/MIN_SPLASH_MS وجود نداشت — به محض
    // تموم‌شدن try (که می‌تونه خیلی سریع باشه، مثلاً ۳۰۰ میلی‌ثانیه)، فقط
    // ۱۵۰ میلی‌ثانیه صبر می‌کرد و اسپلش رو مخفی می‌کرد. safetyTimer در واقع
    // فقط یه سقفِ حداکثر انتظار بود (برای وقتی چیزی گیر می‌کنه)، نه تضمین
    // حداقل نمایش. الان اسپلش حداقل ۲ ثانیه (خواسته‌ی شما) نمایش داده می‌شه.
    const MIN_SPLASH_MS = 2000;
    const splashStartedAt = Date.now();
    const safetyTimer = setTimeout(() => this.hideSplash(), 8000);

    try {
      let session = null;
      try {
        if (window.API && typeof API.authenticateWebApp === 'function') {
          session = await API.authenticateWebApp();
        } else {
          // ⚠️ فیکس مشاهده‌پذیری: قبلاً اگه این شرط رد می‌شد (یعنی api.js
          // اصلاً لود نشده بود)، هیچ لاگی ثبت نمی‌شد و کل init ساکت جلو
          // می‌رفت با session=null، دقیقاً همون چیزی که باعث AuthAttempt
          // نبودن تو لاگ‌های قبلی می‌شد بدون هیچ توضیحی.
          window.logEvent('BOOT', 'guardFail', { check: 'API.authenticateWebApp', hasAPI: Boolean(window.API) });
        }
        if (!session && window.API && typeof API.getSession === 'function') {
          session = await API.getSession();
        } else if (!session) {
          window.logEvent('BOOT', 'guardFail', { check: 'API.getSession', hasAPI: Boolean(window.API) });
        }
      } catch (e) {
        window.logEvent('APP', 'authNotice', { err: e.message || e });
      }
      this.state.session = session;

      await this.loadSignals();
      this.updateUserInterface();

      if (window.Views) {
        if (typeof Views.syncFilterChipsUI === 'function') {
          Views.syncFilterChipsUI();
        }
        if (typeof Views.renderSignalsList === 'function') {
          Views.renderSignalsList();
        } else if (typeof Views.renderCurrent === 'function') {
          Views.renderCurrent();
        }
      } else {
        window.logEvent('BOOT', 'guardFail', { check: 'window.Views' });
      }

      const tgUid = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
      const isAdm = Boolean(session?.is_admin || session?.is_super_admin);
      window.logEvent('APP', 'ready', { sessUid: session?.telegram_id || 'none', tgUid: tgUid || 'none', adm: isAdm, sigCount: this.state.signals.length });

      if (window.PullRefresh && typeof PullRefresh.init === 'function') {
        PullRefresh.init('#tab-signals', async (isSilent) => {
          await App.loadSignals();
          if (window.Views && typeof Views.renderSignalsList === 'function') {
            Views.renderSignalsList();
          }
          if (!isSilent && window.API && typeof API.getSession === 'function') {
            const fresh = await API.getSession();
            if (fresh) {
              App.state.session = fresh;
              App.updateUserInterface();
            }
          }
        });
      } else {
        window.logEvent('BOOT', 'guardFail', { check: 'PullRefresh.init', hasPullRefresh: Boolean(window.PullRefresh) });
      }
    } catch (err) {
      window.logEvent('APP', 'initErr', { err: err.message || err, stack: (err.stack || '').slice(0, 300) });
    } finally {
      clearTimeout(safetyTimer);
      const elapsed = Date.now() - splashStartedAt;
      const remaining = Math.max(0, MIN_SPLASH_MS - elapsed);
      setTimeout(() => this.hideSplash(), remaining + 150);
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

    const isSuper = Boolean(s?.is_super_admin === true || quota?.is_super_admin === true);
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
        avatarContainer.innerHTML = `<img src="${escapeHtml(photoUrl)}" alt="${escapeHtml(displayName)}" style="width:100%; height:100%; object-fit:cover; border-radius:50%; display:block;" onerror="this.outerHTML=window.AvatarRenderer ? AvatarRenderer.getAvatarSvg('${roleKey}') : ''">`;
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
    if (window.Views && typeof Views.renderCurrent === 'function') {
      Views.renderCurrent();
    }
  },

  setSignalSubTab(subTab) {
    this.haptic('selection');
    this.state.signalSubTab = subTab;
    document.getElementById('subTabActive')?.classList.toggle('active', subTab === 'active');
    document.getElementById('subTabClosed')?.classList.toggle('active', subTab === 'closed');
    if (window.Views && typeof Views.renderSignalsList === 'function') {
      Views.renderSignalsList();
    }
  },

  onSearchInput(val) {
    this.state.searchQuery = (val || '').trim().toLowerCase();
    if (window.Views && typeof Views.renderSignalsList === 'function') {
      Views.renderSignalsList();
    }
  },

  async loadSignals() {
    try {
      if (window.API && typeof API.getSignals === 'function') {
        const res = await API.getSignals();
        this.state.signals = Array.isArray(res) ? res : (res?.items || res?.signals || res?.feed || []);
      }
      
      const openCount = (this.state.signals || []).filter(s => {
        const st = String(s.outcome_status || s.status || 'open').toLowerCase();
        return st === 'open' || st === 'active';
      }).length;

      const countBadge = document.getElementById('activeCountBadge');
      if (countBadge) countBadge.textContent = openCount;

      // ⚠️ throttled: این تابع با هر pull-refresh دوباره صدا زده می‌شه؛
      // بدون throttle همون ۱۴ بار تو ۴۰ ثانیه‌ای بود که لاگ‌های مهم‌تر رو
      // له می‌کرد.
      if (window.logEventThrottled) {
        window.logEventThrottled('APP', 'loadSignalsOK', { total: this.state.signals.length, open: openCount }, 30000);
      }
    } catch (e) {
      if (window.logEvent) window.logEvent('APP', 'loadSignalsErr', { err: e.message || e });
      this.state.signals = [];
    }
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => App.init());
} else {
  App.init();
}