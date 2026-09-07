/**
 * MemeLand App Controller
 * استاندارد TMA: احراز هویت سایلنت، کارت‌های اتمیک و تفکیک ادمین بر اساس .env
 */

const App = {
  state: {
    currentTab: 'signals',
    signalSubTab: 'active',
    category: 'all',
    searchQuery: '',
    session: null,
    signals: [],
    leaderboard: { callers: [], signal_givers: [] },
    academyTab: 'strategies',
    strategies: [],
    articles: []
  },

  async init() {
    TGBridge.init();

    // ۱. احراز هویت سایلنت در پس‌زمینه
    try {
      let session = await API.authenticateWebApp();
      if (!session) {
        session = await API.getSession();
      }
      this.state.session = session;
    } catch (e) {
      console.warn('Silent auth fallback to guest mode');
    }

    // ۲. بارگذاری اولیه فید سیگنال‌ها
    await this.loadSignals();

    // ۳. به‌روزرسانی هویت در رابط کاربری
    this.updateUserInterface();

    // ۴. محو کردن لودینگ قورباغه پس از تکمیل کامل بارگذاری
    setTimeout(() => {
      const splash = document.getElementById('splashScreen');
      if (splash) splash.classList.add('fade-out');
    }, 450);

    this.renderCurrentView();
  },

  updateUserInterface() {
    const s = this.state.session;
    const headerName = document.getElementById('headerUserName');
    const headerAdmin = document.getElementById('headerAdminBadge');
    const profileName = document.getElementById('profileFullName');
    const profileUser = document.getElementById('profileUsername');
    const profileId = document.getElementById('profileTelegramId');
    const profileRole = document.getElementById('profileRoleText');
    const adminSec = document.getElementById('adminPanelSection');
    const adminFab = document.getElementById('adminFabBtn');

    if (s && s.user) {
      const displayName = s.display_name || s.user.first_name || 'کاربر تلگرام';
      const username = s.user.username ? `@${s.user.username}` : '—';
      const isAdmin = s.role === 'admin';

      headerName.textContent = displayName;
      profileName.textContent = displayName;
      profileUser.textContent = username;
      profileId.textContent = s.user.id;

      if (isAdmin) {
        headerAdmin.style.display = 'inline-block';
        profileRole.textContent = '👑 ادمین ارشد (ADMIN_IDS)';
        profileRole.style.color = 'var(--gold)';
        adminSec.style.display = 'block';
        adminFab.style.display = 'flex';
      } else {
        headerAdmin.style.display = 'none';
        profileRole.textContent = 'عضو رسمی';
        profileRole.style.color = 'var(--teal)';
        adminSec.style.display = 'none';
        adminFab.style.display = 'none';
      }
    } else {
      headerName.textContent = 'مهمان';
      profileName.textContent = 'کاربر مهمان';
      profileUser.textContent = 'بدون نشست تلگرام';
      profileId.textContent = '—';
      profileRole.textContent = 'فقط خواندنی';
      adminSec.style.display = 'none';
      adminFab.style.display = 'none';
    }
  },

  switchTab(tabName) {
    TGBridge.haptic('selection');
    this.state.currentTab = tabName;

    document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));

    document.getElementById(`tab-${tabName}`).classList.add('active');

    const tabMap = { signals: 0, leaderboard: 1, academy: 2, profile: 3 };
    document.querySelectorAll('.bottom-nav .nav-btn')[tabMap[tabName]].classList.add('active');

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
    const isClosed = this.state.signalSubTab === 'closed';

    let list = this.state.signals.filter(s => {
      const matchStatus = isClosed ? (s.outcome_status === 'win' || s.outcome_status === 'loss') : (s.outcome_status === 'open');
      const matchCat = this.state.category === 'all' || s.channel === this.state.category;
      const matchSearch = !this.state.searchQuery || s.coin.toLowerCase().includes(this.state.searchQuery);
      return matchStatus && matchCat && matchSearch;
    });

    if (list.length === 0) {
      listEl.innerHTML = '<div style="text-align:center; padding:36px; color:var(--text-muted); font-size:12px;">سیگنالی یافت نشد.</div>';
      return;
    }

    listEl.innerHTML = list.map(s => {
      const roiClass = s.outcome_status === 'win' ? 'roi-win' : (s.outcome_status === 'loss' ? 'roi-loss' : 'roi-open');
      const roiText = s.result ? s.result : (s.outcome_status === 'open' ? 'درحال معامله' : '—');
      const caller = s.owner_first_name || s.caller_name || 'آلفا';
      const caPart = s.contract_address ? `<span class="ca-chip" onclick="event.stopPropagation(); TGBridge.copyText('${s.contract_address}')">📋 ${s.contract_address.slice(0, 4)}...${s.contract_address.slice(-4)}</span>` : '';

      return `
        <div class="card-atomic" onclick="App.openSignalDetails(${s.id})">
          <div class="card-atomic-top">
            <div class="token-meta">
              <span class="token-name">${s.coin}</span>
              <span class="badge-chain">${s.channel ? s.channel.toUpperCase() : 'DEX'}</span>
              ${s.tier === 'vip' ? '<span class="badge-vip">VIP</span>' : ''}
            </div>
            <div class="roi-badge ${roiClass}">${roiText}</div>
          </div>
          <div class="card-atomic-bottom">
            <span>👤 ${caller}</span>
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

    const isAdmin = this.state.session && this.state.session.role === 'admin';
    const body = document.getElementById('sheetContent');

    body.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h3 style="font-size:17px;">${s.coin}</h3>
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
          <button class="btn btn-secondary" onclick="App.openUpdateResult(${s.id})">ثبت نتیجه</button>
          <button class="btn btn-secondary" style="color:var(--red);" onclick="App.deleteSignalAction(${s.id})">حذف سیگنال</button>
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

  async renderLeaderboard() {
    const listEl = document.getElementById('leaderboardFeedList');
    this.state.leaderboard = await API.getLeaderboard();
    const rows = this.state.leaderboard.callers || [];

    if (rows.length === 0) {
      listEl.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-muted);">رتبه‌بندی موجود نیست.</div>';
      return;
    }

    listEl.innerHTML = rows.map((r, i) => `
      <div class="card-atomic" style="cursor:default;">
        <div class="card-atomic-top">
          <div class="token-meta">
            <span class="mono" style="color:var(--teal); font-weight:700;">#${i + 1}</span>
            <span class="token-name">👤 ${r.caller_name || 'ناشناس'}</span>
          </div>
          <span style="color:var(--gold); font-size:12.5px; font-weight:700;">★ ${r.avg_rating || '5.0'}</span>
        </div>
        <div class="card-atomic-bottom">
          <span>${r.count || 0} کال ثبت‌شده</span>
          <span>${r.tier ? r.tier.toUpperCase() : 'BRONZE'}</span>
        </div>
      </div>
    `).join('');
  },

  async renderAcademy() {
    const listEl = document.getElementById('academyFeedList');
    this.state.strategies = await API.getContent('strategies');
    
    if (this.state.strategies.length === 0) {
      listEl.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-muted);">محتوایی ثبت نشده است.</div>';
      return;
    }

    listEl.innerHTML = this.state.strategies.map(st => `
      <div class="card-atomic" style="cursor:default;">
        <h4 style="font-size:13px; margin-bottom:5px;">${st.title}</h4>
        <p style="font-size:11px; color:var(--text-muted); line-height:1.7;">${st.desc}</p>
      </div>
    `).join('');
  },

  openAddSignalModal() {
    document.getElementById('modalTitle').textContent = 'ثبت سیگنال جدید';
    document.getElementById('modalBody').innerHTML = `
      <div class="field"><label>نماد دارایی (کوین):</label><input id="newCoin" placeholder="مثلاً $PEPE یا SOL"></div>
      <div class="field"><label>شبکه / کتگوری:</label><select id="newChannel">
        <option value="dex">دکس (Solana / EVM)</option>
        <option value="alt">آلت‌کوین</option>
        <option value="stock">سهام جهانی</option>
        <option value="irbourse">بورس ایران</option>
      </select></div>
      <div class="field"><label>آدرس کانترکت (CA):</label><input id="newCA" placeholder="آدرس کانترکت برای خرید"></div>
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
    } else {
      TGBridge.haptic('error');
      TGBridge.showAlert('خطا در ثبت سیگنال');
    }
  },

  closeModal() {
    document.getElementById('modalOverlay').classList.remove('show');
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
    }
  }
};

window.addEventListener('DOMContentLoaded', () => App.init());