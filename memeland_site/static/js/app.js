/**
 * MemeLand App Controller
 * نسخه نهایی و پایدار (TMA Standard)
 * - احراز هویت سایلنت و بدون نقص تلگرام
 * - تفکیک دسترسی ادمین منحصراً بر اساس ADMIN_IDS
 * - کارت‌های اتمیک ترید، باتم‌شیت و رفع کامل باگ‌های ناوبری
 */

const App = {
  state: {
    currentTab: 'signals',
    signalSubTab: 'active',      // 'active' | 'closed'
    category: 'all',             // 'all' | 'dex' | 'alt' | 'stock' | 'irbourse'
    searchQuery: '',
    session: null,
    signals: [],
    leaderboardType: 'callers',  // 'callers' | 'signal_givers'
    leaderboardData: { callers: [], signal_givers: [] },
    academyTab: 'strategies',    // 'strategies' | 'articles'
    strategies: [],
    articles: []
  },

  async init() {
    TGBridge.init();

    // تغییر متن‌های لودینگ قورباغه برای جذابیت بصری
    this.startSplashTicker();

    // سوپاپ اطمینان: اسپلش در بدترین حالت شبکه نهایتاً بعد از ۳.۵ ثانیه محو می‌شود
    const safetyTimeout = setTimeout(() => this.hideSplash(), 3500);

    try {
      // ۱. احراز هویت سایلنت در پس‌زمینه
      let session = await API.authenticateWebApp();
      if (!session) {
        session = await API.getSession();
      }
      this.state.session = session;

      // ۲. بارگذاری اولیه فید سیگنال‌ها
      await this.loadSignals();

      // ۳. همگام‌سازی رابط کاربری با مشخصات تلگرام
      this.updateUserInterface();
      this.renderCurrentView();
    } catch (err) {
      console.warn('Init fallback:', err);
    } finally {
      clearTimeout(safetyTimeout);
      setTimeout(() => this.hideSplash(), 400);
    }
  },

  startSplashTicker() {
    const statusEl = document.getElementById('splashStatusText');
    if (!statusEl) return;
    const steps = [
      'در حال اتصال به شبکه آلفا...',
      'اسکن پامپ‌های دکس و سولانا...',
      'همگام‌سازی سیگنال‌های VIP...',
      'آماده‌سازی تیکرهای زنده...'
    ];
    let i = 0;
    this._splashInterval = setInterval(() => {
      i = (i + 1) % steps.length;
      statusEl.textContent = steps[i];
    }, 800);
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
    const adminSec = document.getElementById('adminPanelSection');
    const adminFab = document.getElementById('adminFabBtn');

    // استخراج سازگار با هر دو ساختار /webapp-auth و /site/session
    const tid = s ? (s.telegram_id || (s.user && s.user.id)) : null;
    const displayName = s ? (s.display_name || (s.user && s.user.first_name) || s.first_name || 'کاربر تلگرام') : null;
    const username = s ? (s.username || (s.user && s.user.username)) : null;
    const isAdmin = s && s.role === 'admin';

    if (s && tid) {
      headerName.textContent = displayName;
      profileName.textContent = displayName;
      profileUser.textContent = username ? `@${username}` : '—';
      profileId.textContent = tid;

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
      headerAdmin.style.display = 'none';
      adminSec.style.display = 'none';
      adminFab.style.display = 'none';
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
      const caPart = s.contract_address
        ? `<span class="ca-chip" onclick="event.stopPropagation(); TGBridge.copyText('${s.contract_address}')">📋 ${s.contract_address.slice(0, 4)}...${s.contract_address.slice(-4)}</span>`
        : '';

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

  // ================= مدیریت لیدربورد =================
  setLeaderboardType(type) {
    TGBridge.haptic('selection');
    this.state.leaderboardType = type;
    document.getElementById('btnLbCallers').classList.toggle('active', type === 'callers');
    document.getElementById('btnLbGivers').classList.toggle('active', type === 'signal_givers');
    this.renderLeaderboard();
  },

  async renderLeaderboard() {
    const listEl = document.getElementById('leaderboardFeedList');
    if (!this.state.leaderboardData.callers.length && !this.state.leaderboardData.signal_givers.length) {
      listEl.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:11px;">در حال دریافت جدول رتبه‌بندی...</div>';
      this.state.leaderboardData = await API.getLeaderboard();
    }

    const isCallers = this.state.leaderboardType === 'callers';
    const rows = isCallers ? this.state.leaderboardData.callers : this.state.leaderboardData.signal_givers;

    if (!rows || rows.length === 0) {
      listEl.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-muted); font-size:12px;">رتبه‌بندی موجود نیست.</div>';
      return;
    }

    if (isCallers) {
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
    } else {
      listEl.innerHTML = rows.map((r, i) => `
        <div class="card-atomic" style="cursor:default;">
          <div class="card-atomic-top">
            <div class="token-meta">
              <span class="mono" style="color:var(--pink); font-weight:700;">#${i + 1}</span>
              <span class="token-name">📡 ${r.full_name || r.username || 'کاربر'}</span>
            </div>
            <span style="color:var(--teal); font-size:12.5px; font-weight:700;">${r.points || 0} pt</span>
          </div>
          <div class="card-atomic-bottom">
            <span>${r.count || 0} سیگنال · ${r.wins || 0} برد</span>
            <span>سطح ${r.level || 1}</span>
          </div>
        </div>
      `).join('');
    }
  },

  // ================= مدیریت آکادمی و استراتژی‌ها =================
  setAcademySubTab(subTab) {
    TGBridge.haptic('selection');
    this.state.academyTab = subTab;
    document.getElementById('btnAcadStrat').classList.toggle('active', subTab === 'strategies');
    document.getElementById('btnAcadArt').classList.toggle('active', subTab === 'articles');
    this.renderAcademy();
  },

  async renderAcademy() {
    const listEl = document.getElementById('academyFeedList');

    if (this.state.academyTab === 'strategies') {
      if (!this.state.strategies.length) {
        listEl.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:11px;">در حال دریافت ستاپ‌ها...</div>';
        this.state.strategies = await API.getContent('strategies');
      }

      if (!this.state.strategies || this.state.strategies.length === 0) {
        listEl.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-muted); font-size:12px;">ستاپ تحلیلی ثبت نشده است.</div>';
        return;
      }

      listEl.innerHTML = this.state.strategies.map(st => `
        <div class="card-atomic" style="cursor:default;">
          <h4 style="font-size:13px; margin-bottom:5px; color:var(--text);">${st.title}</h4>
          <p style="font-size:11px; color:var(--text-muted); line-height:1.7;">${st.desc}</p>
        </div>
      `).join('');
    } else {
      if (!this.state.articles.length) {
        listEl.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:11px;">در حال دریافت مقالات...</div>';
        this.state.articles = await API.getContent('articles');
      }

      if (!this.state.articles || this.state.articles.length === 0) {
        listEl.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-muted); font-size:12px;">مقاله‌ای ثبت نشده است.</div>';
        return;
      }

      listEl.innerHTML = this.state.articles.map(art => `
        <div class="card-atomic" style="cursor:default;">
          <h4 style="font-size:13px; margin-bottom:5px; color:var(--teal);">${art.title}</h4>
          <p style="font-size:11px; color:var(--text-muted); line-height:1.8; white-space:pre-line;">${art.body || art.desc || ''}</p>
        </div>
      `).join('');
    }
  },

  // ================= مدیریت فرم‌های ادمین =================
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
    } else {
      TGBridge.haptic('error');
      TGBridge.showAlert('خطا در ثبت سیگنال');
    }
  },

  openUpdateResult(signalId) {
    TGBridge.haptic('selection');
    this.closeBottomSheet();
    const s = this.state.signals.find(item => item.id === signalId);
    if (!s) return;

    document.getElementById('modalTitle').textContent = `نتیجه برای ${s.coin}`;
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

  openBulkModal() {
    TGBridge.haptic('selection');
    document.getElementById('modalTitle').textContent = 'ثبت گروهی سیگنال‌ها';
    document.getElementById('modalBody').innerHTML = `
      <p style="font-size:11px; color:var(--text-muted); margin-bottom:8px; line-height:1.6;">
        فرمت هر خط: <b>کتگوری|نماد|توضیح|آدرس‌کانترکت|لینک‌خرید</b><br>
        کتگوری‌ها: dex / alt / stock / irbourse
      </p>
      <div class="field">
        <textarea id="bulkData" rows="6" placeholder="dex|PEPE|تارگت ۲|0x...|https://..."></textarea>
      </div>
      <button class="btn btn-primary" onclick="App.submitBulkSignals()">درون‌ریزی داده‌ها</button>
    `;
    document.getElementById('modalOverlay').classList.add('show');
  },

  async submitBulkSignals() {
    const raw = document.getElementById('bulkData').value.trim();
    if (!raw) return;

    const lines = raw.split('\n').map(l => l.trim()).filter(Boolean);
    let count = 0;

    for (const line of lines) {
      const parts = line.split('|').map(p => p.trim());
      if (parts.length >= 2) {
        const [channel, coin, note, ca, link] = parts;
        await API.createSignal({
          channel: channel || 'dex',
          coin,
          note: note || null,
          contract_address: ca || null,
          buy_link: link || null,
          tier: 'free',
          outcome_status: 'open'
        });
        count++;
      }
    }

    TGBridge.haptic('success');
    this.closeModal();
    TGBridge.showAlert(`${count} سیگنال با موفقیت ثبت شد.`);
    await this.loadSignals();
    this.renderSignalsList();
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