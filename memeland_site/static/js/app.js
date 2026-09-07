/**
 * MemeLand App Controller (TMA v5.1.0)
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
    TGBridge.init();
    this.startSplashTicker();

    const safetyTimer = setTimeout(() => this.hideSplash(), 3500);

    // پس از لود اولیه در init() فراخوانی شود:
    PullRefresh.init('#tab-signals', async (isSilent) => {
      await App.loadSignals();
      App.renderSignalsList();
      if (!isSilent) {
        let session = await API.getSession();
        if (session) {
          App.state.session = session;
          App.updateUserInterface();
        }
      }
    });

    try {
      let session = await API.authenticateWebApp();
      if (!session) {
        session = await API.getSession();
      }
      this.state.session = session;

      await this.loadSignals();
      this.updateUserInterface();
      this.renderCurrentView();
    } catch (err) {
      console.warn('Init error:', err);
    } finally {
      clearTimeout(safetyTimer);
      setTimeout(() => this.hideSplash(), 350);
    }
  },

  startSplashTicker() {
    const statusEl = document.getElementById('splashStatusText');
    if (!statusEl) return;
    const steps = [
      'در حال اتصال به شبکه آلفا...',
      'اسکن پامپ‌های دکس و سولانا...',
      'همگام‌سازی سهمیه و سیگنال‌ها...',
      'آماده‌سازی تیکرهای زنده...'
    ];
    let idx = 0;
    this._splashInterval = setInterval(() => {
      idx = (idx + 1) % steps.length;
      statusEl.textContent = steps[idx];
    }, 750);
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
    
    // المان‌های آواتار نئونی
    const avatarFrame = document.getElementById('profileAvatarFrame');
    const avatarContainer = document.getElementById('avatarSvgContainer');
    const avatarMiniBadge = document.getElementById('avatarMiniBadge');

    const tid = s ? (s.telegram_id || (s.user && s.user.id) || (window.Telegram?.WebApp?.initDataUnsafe?.user?.id)) : null;
    const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;

    const displayName = (s && s.display_name) ||
                        (s && s.user && s.user.first_name) ||
                        (s && s.first_name) ||
                        (tgUser && tgUser.first_name) ||
                        'کاربر تلگرام';

    const username = (s && s.username) ||
                     (s && s.user && s.user.username) ||
                     (tgUser && tgUser.username) ||
                     null;

    const isAdmin = Boolean(s && (s.role === 'admin' || s.is_admin === true));
    const quota = (s && s.quota) ? s.quota : null;

    // تشخیص کلید نقش جهت رندر آواتار
    let roleKey = 'rookie';
    if (isAdmin) {
      roleKey = (quota && quota.is_super_admin) ? 'super_admin' : 'admin';
    } else if (quota && quota.role_key) {
      roleKey = quota.role_key;
    }

    // رندر گرافیک وکتوری و تم نئونی آواتار
    if (avatarContainer && window.AvatarRenderer) {
      avatarContainer.innerHTML = AvatarRenderer.getAvatarSvg(roleKey);
      if (avatarMiniBadge) avatarMiniBadge.textContent = AvatarRenderer.getRoleMiniBadge(roleKey);
      if (avatarFrame) {
        avatarFrame.className = `avatar-frame theme-${roleKey}`;
      }
    }

    if (s && (tid || s.token)) {
      if (headerName) headerName.textContent = displayName;
      if (profileName) profileName.textContent = displayName;
      if (profileUser) profileUser.textContent = username ? `@${username.replace('@', '')}` : '—';
      if (profileId) profileId.textContent = tid ? String(tid) : '—';

      if (profileRole && quota) {
        profileRole.textContent = quota.display_role;
      }
      if (profileQuota && quota) {
        profileQuota.textContent = `${quota.signals_today} از ${quota.daily_limit} مصرف شده`;
      }

      if (isAdmin) {
        if (headerAdmin) headerAdmin.style.display = 'inline-block';
        if (adminSec) adminSec.style.display = 'block';
        if (adminFab) adminFab.style.display = 'flex';
      } else {
        if (headerAdmin) headerAdmin.style.display = 'none';
        if (adminSec) adminSec.style.display = 'none';
        if (adminFab) adminFab.style.display = 'none';
      }
    } else {
      if (headerName) headerName.textContent = 'مهمان';
      if (profileName) profileName.textContent = 'کاربر مهمان';
      if (profileUser) profileUser.textContent = 'بدون نشست تلگرام';
      if (profileId) profileId.textContent = '—';
      if (profileRole) profileRole.textContent = 'فقط خواندنی';
      if (headerAdmin) headerAdmin.style.display = 'none';
      if (adminSec) adminSec.style.display = 'none';
      if (adminFab) adminFab.style.display = 'none';
    }
  },

  switchTab(tabName) {
    TGBridge.haptic('selection');
    this.state.currentTab = tabName;

    document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.bottom-nav .nav-btn').forEach(el => el.classList.remove('active'));

    const activeView = document.getElementById(`tab-${tabName}`);
    if (activeView) activeView.classList.add('active');

    const tabMap = { signals: 0, leaderboard: 1, academy: 2, profile: 3 };
    const navBtn = document.querySelectorAll('.bottom-nav .nav-btn')[tabMap[tabName]];
    if (navBtn) navBtn.classList.add('active');

    TGBridge.syncBackButton(tabName !== 'signals');
    this.renderCurrentView();
  },

  setSignalSubTab(subTab) {
    TGBridge.haptic('selection');
    this.state.signalSubTab = subTab;
    document.getElementById('subTabActive').classList.toggle('active', subTab === 'active');
    document.getElementById('subTabClosed').classList.toggle('active', subTab === 'closed');
    this.renderSignalsList();
  },

  setCategory(cat) {
    TGBridge.haptic('selection');
    this.state.category = cat;
    document.querySelectorAll('#catFilterChips .chip').forEach(c => {
      c.classList.toggle('active', c.getAttribute('onclick').includes(`'${cat}'`));
    });
    this.renderSignalsList();
  },

  onSearchInput(val) {
    this.state.searchQuery = val.trim().toLowerCase();
    this.renderSignalsList();
  },

  async loadSignals() {
    try {
      this.state.signals = await API.getSignals();
      const openCount = this.state.signals.filter(s => s.outcome_status === 'open').length;
      document.getElementById('activeCountBadge').textContent = openCount;
    } catch (e) {
      this.state.signals = [];
    }
  },

  renderCurrentView() {
    if (this.state.currentTab === 'signals') {
      this.renderSignalsList();
    } else if (this.state.currentTab === 'leaderboard') {
      this.renderLeaderboard();
    } else if (this.state.currentTab === 'academy') {
      this.renderAcademy();
    }
  },

  renderSignalsList() {
    const listEl = document.getElementById('signalsFeedList');
    if (!listEl) return;

    const isClosed = this.state.signalSubTab === 'closed';

    let list = this.state.signals.filter(s => {
      const matchStatus = isClosed
        ? (s.outcome_status === 'win' || s.outcome_status === 'loss')
        : (s.outcome_status === 'open');
      const matchCat = this.state.category === 'all' || s.channel === this.state.category;
      const matchSearch = !this.state.searchQuery || (s.coin && s.coin.toLowerCase().includes(this.state.searchQuery));
      return matchStatus && matchCat && matchSearch;
    });

    if (list.length === 0) {
      listEl.innerHTML = '<div style="text-align:center; padding:36px; color:var(--text-muted); font-size:12px;">سیگنالی یافت نشد.</div>';
      return;
    }

    listEl.innerHTML = list.map(s => {
      const roiClass = s.outcome_status === 'win' ? 'roi-win' : (s.outcome_status === 'loss' ? 'roi-loss' : 'roi-open');
      const roiText = s.result ? s.result : (s.outcome_status === 'open' ? 'درحال معامله' : '—');
      const caller = s.caller_name || s.owner_first_name || 'آلفا';
      const callerId = s.owner_telegram_id || s.caller_telegram_id || null;

      // ساخت چیپ آدرس کانترکت همراه با کپی ایزوله‌شده
      const caPart = s.contract_address
        ? `<span class="ca-chip" onclick="event.stopPropagation(); TGBridge.copyText('${s.contract_address}')">📋 ${s.contract_address.slice(0, 4)}...${s.contract_address.slice(-4)}</span>`
        : '';

      // نام کالر قابل کلیک جهت باز شدن پرونده تریدر (Dossier)
      const callerPart = callerId
        ? `<span class="caller-chip" onclick="event.stopPropagation(); Dossier.show(${callerId})" style="cursor:pointer; text-decoration:underline;">👤 ${caller}</span>`
        : `<span>👤 ${caller}</span>`;

      return `
        <div class="card-atomic" onclick="App.openSignalDetails(${s.id})">
          <div class="card-atomic-top">
            <div class="token-meta">
              <span class="token-name">${s.coin || '—'}</span>
              <span class="badge-chain">${s.channel ? s.channel.toUpperCase() : 'DEX'}</span>
              ${s.tier === 'vip' ? '<span class="badge-vip">VIP</span>' : ''}
            </div>
            <div class="roi-badge ${roiClass}">${roiText}</div>
          </div>
          <div class="card-atomic-bottom">
            ${callerPart}
            ${caPart}
          </div>
        </div>
      `;
    }).join('');
  },

  openSignalDetails(signalId) {
    TGBridge.haptic('light');
    const s = this.state.signals.find(item => item.id === signalId);
    if (!s) return;

    const isAdmin = Boolean(this.state.session && (this.state.session.role === 'admin' || this.state.session.is_admin === true));
    const body = document.getElementById('sheetContent');

    body.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h3 style="font-size:17px;">${s.coin || '—'}</h3>
        <span class="badge-chain">${s.channel ? s.channel.toUpperCase() : 'DEX'}</span>
      </div>
      
      ${s.contract_address ? `
        <div style="background:var(--bg); padding:9px 12px; border-radius:10px; margin-bottom:12px; font-size:11px; display:flex; justify-content:space-between; align-items:center;">
          <span class="mono">${s.contract_address}</span>
          <button class="btn btn-teal" style="width:auto; padding:4px 9px; font-size:10px;" onclick="TGBridge.copyText('${s.contract_address}')">کپی CA</button>
        </div>` : ''
      }

      ${s.note ? `<p style="font-size:12px; line-height:1.8; color:var(--text-muted); margin-bottom:14px;">${s.note}</p>` : ''}
      
      ${s.buy_link ? `<a href="${s.buy_link}" target="_blank" class="btn btn-primary" style="margin-bottom:10px;">خرید مستقیم در دکس ↗</a>` : ''}

      ${isAdmin ? `
        <div class="admin-actions-grid" style="border-top:1px solid var(--border); padding-top:12px; margin-top:14px;">
          <button class="btn btn-secondary" onclick="App.openUpdateResult(${s.id})">🎯 ثبت نتیجه</button>
          <button class="btn btn-secondary" style="color:var(--red);" onclick="App.deleteSignalAction(${s.id})">🗑️ حذف سیگنال</button>
        </div>` : ''
      }
    `;

    document.getElementById('bottomSheet').classList.add('show');
    TGBridge.syncBackButton(true);
  },

  closeBottomSheet() {
    document.getElementById('bottomSheet').classList.remove('show');
    TGBridge.syncBackButton(this.state.currentTab !== 'signals');
  },

  // ================= مدال مدیریت کادر و اعطای نقش =================
  async openManageStaffModal() {
    TGBridge.haptic('selection');
    document.getElementById('modalTitle').textContent = 'مدیریت ادمین‌ها و نقش‌ها';
    document.getElementById('modalBody').innerHTML = `
      <div style="margin-bottom:14px; border-bottom:1px solid var(--border); padding-bottom:12px;">
        <h5 style="font-size:12px; margin-bottom:8px; color:var(--teal);">افزودن عضو جدید</h5>
        <div class="field"><label>شناسه عددی تلگرام (User ID):</label><input id="staffUserId" placeholder="مثلاً 123456789"></div>
        <div class="field"><label>انتخاب نقش:</label><select id="staffRole">
          <option value="admin">👑 Admin (مدیر کامل)</option>
          <option value="vip_helper">💎 VIP Helper (کمک‌ادمین)</option>
          <option value="og">👑 Memeland OG (۵۰ سیگنال)</option>
          <option value="alpha">🚀 Memeland Alpha Master (۱۵ سیگنال)</option>
          <option value="guardian">🦈 Memeland Guardian (۸ سیگنال)</option>
          <option value="explorer">🐸 Memeland Explorer (۵ سیگنال)</option>
        </select></div>
        <button class="btn btn-primary" onclick="App.submitAddStaff()">اعطای دسترسی</button>
      </div>
      <div>
        <h5 style="font-size:12px; margin-bottom:8px;">لیست کادر فعلی</h5>
        <div id="staffListContainer" style="display:flex; flex-direction:column; gap:6px;">
          <div style="font-size:11px; color:var(--text-muted);">در حال بارگذاری...</div>
        </div>
      </div>
    `;
    document.getElementById('modalOverlay').classList.add('show');
    await this.loadStaffList();
  },

  async loadStaffList() {
    const cont = document.getElementById('staffListContainer');
    try {
      const resp = await fetch('/site/staff', { headers: API.getHeaders() });
      if (!resp.ok) throw new Error();
      const list = await resp.json();
      this.state.staffList = list;

      if (!list.length) {
        cont.innerHTML = '<div style="font-size:11px; color:var(--text-muted);">عضوی در دیتابیس ثبت نشده است.</div>';
        return;
      }

      cont.innerHTML = list.map(item => `
        <div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg); padding:8px 10px; border-radius:8px; font-size:11px;">
          <div>
            <span class="mono" style="font-weight:700;">${item.user_id}</span>
            <span style="color:var(--text-muted); margin-right:6px;">(${item.role})</span>
          </div>
          ${!item.is_super ? `<button class="btn btn-secondary" style="width:auto; padding:2px 8px; color:var(--red); font-size:10px;" onclick="App.removeStaffAction(${item.user_id})">حذف</button>` : '<span style="font-size:10px; color:var(--gold);">Super</span>'}
        </div>
      `).join('');
    } catch (e) {
      cont.innerHTML = '<div style="font-size:11px; color:var(--red);">خطا در دریافت لیست</div>';
    }
  },

  async submitAddStaff() {
    const uid = document.getElementById('staffUserId').value.trim();
    const role = document.getElementById('staffRole').value;
    if (!uid || !/^\d+$/.test(uid)) {
      TGBridge.showAlert('شناسه عددی باید عدد باشد');
      return;
    }

    const resp = await fetch('/site/staff', {
      method: 'POST',
      headers: API.getHeaders(),
      body: JSON.stringify({ user_id: parseInt(uid), role })
    });

    if (resp.ok) {
      TGBridge.haptic('success');
      TGBridge.showAlert('نقش با موفقیت اعمال شد');
      await this.loadStaffList();
    } else {
      TGBridge.haptic('error');
      TGBridge.showAlert('خطا در ثبت نقش');
    }
  },

  async removeStaffAction(uid) {
    const conf = await TGBridge.showConfirm(`آیا از خلع دسترسی کاربر ${uid} مطمئن هستید؟`);
    if (!conf) return;

    const resp = await fetch(`/site/staff/${uid}`, {
      method: 'DELETE',
      headers: API.getHeaders()
    });

    if (resp.ok) {
      TGBridge.haptic('success');
      await this.loadStaffList();
    } else {
      TGBridge.haptic('error');
      TGBridge.showAlert('امکان حذف این کاربر وجود ندارد');
    }
  },

  // ================= مدال افزودن سیگنال =================
  openAddSignalModal() {
    TGBridge.haptic('selection');
    document.getElementById('modalTitle').textContent = 'ثبت سیگنال جدید';
    document.getElementById('modalBody').innerHTML = `
      <div class="field"><label>نماد دارایی (کوین):</label><input id="newCoin" placeholder="مثلاً $PEPE یا SOL"></div>
      <div class="field"><label>شبکه / کتگوری:</label><select id="newChannel">
        <option value="dex">دکس (Solana / EVM)</option>
        <option value="alt">آلت‌کوین</option>
        <option value="stock">سهام جهانی</option>
        <option value="irbourse">بورس ایران</option>
      </select></div>
      <div class="field"><label>آدرس کانترکت (CA):</label><input id="newCA" placeholder="آدرس کانترکت"></div>
      <div class="field"><label>لینک خرید (GMGN / Raydium):</label><input id="newBuyLink" placeholder="https://..."></div>
      <div class="field"><label>توضیح / تارگت‌ها:</label><textarea id="newNote" rows="3"></textarea></div>
      <button class="btn btn-primary" onclick="App.submitNewSignal()">ثبت نهایی</button>
    `;
    document.getElementById('modalOverlay').classList.add('show');
  },

  async submitNewSignal() {
    const coin = document.getElementById('newCoin').value.trim();
    if (!coin) { TGBridge.showAlert('نماد کوین الزامی است'); return; }

    const payload = {
      coin,
      channel: document.getElementById('newChannel').value,
      contract_address: document.getElementById('newCA').value.trim() || null,
      buy_link: document.getElementById('newBuyLink').value.trim() || null,
      note: document.getElementById('newNote').value.trim() || null,
      tier: 'free',
      outcome_status: 'open'
    };

    const res = await API.createSignal(payload);
    if (res.ok) {
      TGBridge.haptic('success');
      this.closeModal();
      await this.loadSignals();
      this.renderSignalsList();
      let session = await API.getSession();
      if (session) {
        this.state.session = session;
        this.updateUserInterface();
      }
    } else {
      const data = await res.json().catch(() => ({}));
      TGBridge.haptic('error');
      TGBridge.showAlert(data.error || 'خطا در ثبت سیگنال');
    }
  },

  openUpdateResult(signalId) {
    TGBridge.haptic('selection');
    this.closeBottomSheet();
    const s = this.state.signals.find(item => item.id === signalId);
    if (!s) return;

    document.getElementById('modalTitle').textContent = `نتیجه برای ${s.coin || ''}`;
    document.getElementById('modalBody').innerHTML = `
      <div class="field">
        <label>درصد سود یا متن نتیجه:</label>
        <input id="updResult" value="${s.result || ''}" placeholder="مثلاً +250% یا تارگت ۲">
      </div>
      <div class="field">
        <label>وضعیت نهایی پوزیشن:</label>
        <select id="updStatus">
          <option value="win" ${s.outcome_status === 'win' ? 'selected' : ''}>✅ برد (Win)</option>
          <option value="loss" ${s.outcome_status === 'loss' ? 'selected' : ''}>❌ باخت (Loss)</option>
          <option value="open" ${s.outcome_status === 'open' ? 'selected' : ''}>⏳ باز (Open)</option>
        </select>
      </div>
      <button class="btn btn-primary" onclick="App.submitUpdateResult(${s.id})">ثبت نتیجه</button>
    `;
    document.getElementById('modalOverlay').classList.add('show');
  },

  async submitUpdateResult(signalId) {
    const result = document.getElementById('updResult').value.trim();
    const status = document.getElementById('updStatus').value;

    const res = await API.updateSignalResult(signalId, result, status);
    if (res.ok) {
      TGBridge.haptic('success');
      this.closeModal();
      await this.loadSignals();
      this.renderSignalsList();
    } else {
      TGBridge.haptic('error');
      TGBridge.showAlert('خطا در ثبت نتیجه');
    }
  },

  async deleteSignalAction(id) {
    const conf = await TGBridge.showConfirm('آیا از حذف این سیگنال مطمئن هستید؟');
    if (!conf) return;

    const resp = await API.deleteSignal(id);
    if (resp.ok) {
      TGBridge.haptic('success');
      this.closeBottomSheet();
      await this.loadSignals();
      this.renderSignalsList();
    } else {
      TGBridge.haptic('error');
      TGBridge.showAlert('خطا در حذف سیگنال');
    }
  },

  closeModal() {
    document.getElementById('modalOverlay').classList.remove('show');
  }
};

window.addEventListener('DOMContentLoaded', () => App.init());