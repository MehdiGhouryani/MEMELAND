/**
 * MemeLand Views & Feed Renderer (v7.6.0 - Direct Feed Render & Reader Mode)
 */

// ⚠️ خط اثر انگشت بوت (نگاه کن به توضیح مشابه تو api.js).
try {
  if (window.logEvent) window.logEvent('BOOT', 'views.js loaded', { build: window.__MH_BUILD || '?' });
} catch (e) {}

const Views = {
  renderCurrent() {
    if (App.state.currentTab === 'signals') {
      this.renderSignalsList();
    } else if (App.state.currentTab === 'leaderboard') {
      this.renderLeaderboard();
    } else if (App.state.currentTab === 'academy') {
      this.renderAcademy();
    }
  },

  haptic(type = 'light') {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === 'selection') {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      } else if (type === 'success' || type === 'error' || type === 'warning') {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred(type);
      } else {
        window.Telegram.WebApp.HapticFeedback.impactOccurred(type);
      }
    } else if (window.TGBridge) {
      TGBridge.haptic(type);
    }
  },

  // ================= تب سیگنال‌ها =================

  // ⚠️ فیچر جدید (فیلتر ⚙️): بازه‌های ثابت به‌صورت پنجره‌ی متحرک (rolling)
  // حساب می‌شن (مثلاً «این هفته» یعنی ۷ روز گذشته، نه از شنبه‌ی تقویمی) —
  // ساده‌تره و از پیچیدگی مرزهای منطقه‌زمانی جلوگیری می‌کنه.
  _isWithinTimeRange(createdAt, range) {
    if (range === 'all' || !createdAt) return true;
    const created = new Date(createdAt);
    if (isNaN(created.getTime())) return true; // تاریخ خراب/نامعتبر رو فیلتر نکن، نشونش بده
    const diffMs = Date.now() - created.getTime();
    const dayMs = 24 * 60 * 60 * 1000;
    if (range === 'today') return diffMs <= dayMs;
    if (range === 'week') return diffMs <= 7 * dayMs;
    if (range === 'month') return diffMs <= 30 * dayMs;
    return true;
  },

  renderSignalsList() {
    const listEl = document.getElementById('signalsFeedList');
    if (!listEl) return;

    const isClosed = App.state.signalSubTab === 'closed';
    const allSignals = App.state.signals || [];
    const f = App.state.signalFilters || { sort: 'newest', timeRange: 'all', channel: 'all', risk: 'all' };

    let list = allSignals.filter(s => {
      const rawStatus = String(s.outcome_status || s.status || 'open').toLowerCase();
      const matchStatus = isClosed
        ? (rawStatus === 'win' || rawStatus === 'loss' || rawStatus === 'closed')
        : (rawStatus === 'open' || rawStatus === 'active');

      const coinName = String(s.coin || s.symbol || s.name || '').toLowerCase();
      const matchSearch = !App.state.searchQuery || coinName.includes(App.state.searchQuery.toLowerCase());

      const matchTime = this._isWithinTimeRange(s.created_at, f.timeRange);
      const matchChannel = f.channel === 'all' || (s.channel || 'alt') === f.channel;
      const matchRisk = f.risk === 'all' || (s.risk_level || 'low') === f.risk;

      return matchStatus && matchSearch && matchTime && matchChannel && matchRisk;
    });

    list = list.slice().sort((a, b) => {
      const ta = new Date(a.created_at || 0).getTime();
      const tb = new Date(b.created_at || 0).getTime();
      return f.sort === 'oldest' ? ta - tb : tb - ta;
    });

    if (window.logEventThrottled) {
      window.logEventThrottled('VIEW', 'render', { tab: App.state.signalSubTab, total: allSignals.length, filtered: list.length }, 30000);
    }

    if (list.length === 0) {
      listEl.innerHTML = `
        <div style="text-align:center; padding:44px 20px; color:var(--text-muted); font-size:12px;">
          <div style="font-size:28px; margin-bottom:8px; opacity:0.6;">⚡</div>
          سیگنال فعالی در این بخش موجود نیست.
        </div>
      `;
      return;
    }

    listEl.innerHTML = list.map(s => {
      const statusKey = String(s.outcome_status || s.status || 'open').toLowerCase();
      const roiClass = statusKey === 'win' ? 'roi-win' : (statusKey === 'loss' ? 'roi-loss' : 'roi-open');
      const roiText = escapeHtml(s.result ? s.result : 'در حال معامله');
      const caller = escapeHtml(s.caller_name || 'تیم تحلیلی');
      const callerId = s.owner_telegram_id || null;
      const coinTitle = escapeHtml(s.coin || '—');
      const channelTitle = escapeHtml((s.channel || 'DEX').toUpperCase());
      const contractAddr = s.contract_address || null;
      const riskLevel = s.risk_level || 'low';

      // ⚠️ فیکس XSS: قبلاً contractAddr مستقیم داخل onclick="...('${contractAddr}')"
      // تزریق می‌شد — یعنی یه آپاستروف تو آدرس کافی بود که از رشته‌ی جاوااسکریپت
      // فرار کنه و کد دلخواه اجرا کنه (حتی با HTML-escape هم این بردار خاص بسته
      // نمی‌شه، چون مرورگر قبل از اجرای onclick، entity هارو دیکد می‌کنه). به‌جاش
      // آدرس رو تو یه data-attribute می‌ذاریم و از یه هندلر واحد می‌خونیمش.
      const caPart = contractAddr
        ? `<span class="ca-chip" data-contract="${escapeHtml(contractAddr)}" onclick="event.stopPropagation(); Views.copyContractFromEl(this)">📋 ${escapeHtml(contractAddr.length > 10 ? contractAddr.slice(0, 4) + '...' + contractAddr.slice(-4) : contractAddr)}</span>`
        : '';

      const callerPart = callerId
        ? `<span class="caller-chip" onclick="event.stopPropagation(); Dossier.show(${callerId})" style="cursor:pointer; font-weight:600; color:var(--accent-light);">👤 ${caller}</span>`
        : `<span>👤 ${caller}</span>`;

      return `
        <div class="card-atomic" onclick="Views.openSignalDetails(${s.id})">
          <div class="card-atomic-top">
            <div class="token-meta">
              <span class="token-name">${coinTitle}</span>
              <span class="badge-chain">${channelTitle}</span>
              ${s.tier === 'vip' ? '<span class="badge-vip">VIP</span>' : ''}
              ${riskLevel === 'high' ? '<span class="badge-risk-high">🔴 پرریسک</span>' : ''}
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

  copyContractFromEl(el) {
    const addr = el.getAttribute('data-contract');
    if (addr) this.copyContract(addr);
  },

  copyContract(address) {
    this.haptic('light');
    if (window.TGBridge) {
      TGBridge.copyText(address, 'آدرس کانترکت کپی شد ✓');
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(address).then(() => {
        this.haptic('success');
      }).catch(() => {});
    }
  },

  openSignalDetails(signalId) {
    this.haptic('light');
    const s = (App.state.signals || []).find(item => item.id === signalId);
    if (!s) return;

    const session = App.state.session;
    const tgUid = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    const isAdmin = Boolean(session?.is_admin || session?.is_super_admin);
    const body = document.getElementById('sheetContent');
    if (!body) return;

    const coinTitle = escapeHtml(s.coin || s.symbol || '—');
    const channelTitle = escapeHtml((s.channel || s.category || 'DEX').toUpperCase());
    const contractAddr = s.contract_address || s.ca || null;
    const buyLink = safeUrl(s.buy_link || s.link || null);
    const chartImg = s.before_img || s.image || null;
    const noteText = escapeHtml(s.note || '').replace(/\n/g, '<br>');
    const riskLevel = s.risk_level || 'low';

    body.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <h3 style="font-size:17px; font-weight:700;">${coinTitle}</h3>
        <div style="display:flex; gap:6px;">
          <span class="badge-chain">${channelTitle}</span>
          ${riskLevel === 'high' ? '<span class="badge-risk-high">🔴 پرریسک</span>' : ''}
        </div>
      </div>

      ${riskLevel === 'high' ? `
        <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.25); border-radius:var(--radius-sm); padding:10px 12px; margin-bottom:14px; font-size:11.5px; color:var(--red);">
          ⚠️  این سیگنال پرریسکه — برای مدیریت سرمایه، حجم ورودت رو محدود نگه دار.
        </div>` : ''
      }

      ${chartImg ? `
        <div style="margin-bottom:14px; border-radius:var(--radius-md); overflow:hidden; border:1px solid var(--border); background:var(--bg);">
          <img src="${escapeHtml(chartImg)}" style="width:100%; display:block; max-height:260px; object-fit:contain;" alt="Chart">
        </div>` : ''
      }

      ${contractAddr ? `
        <div style="background:var(--bg); padding:10px 12px; border-radius:var(--radius-sm); border:1px solid var(--border); margin-bottom:12px; font-size:11.5px; display:flex; justify-content:space-between; align-items:center;">
          <span class="mono" style="color:var(--text); word-break:break-all; font-size:11px;" data-contract="${escapeHtml(contractAddr)}">${escapeHtml(contractAddr)}</span>
          <button class="btn btn-secondary" style="width:auto; padding:4px 10px; font-size:10.5px; margin-right:8px;" onclick="Views.copyContractFromEl(this.previousElementSibling)">کپی</button>
        </div>` : ''
      }

      ${noteText ? `<p style="font-size:12.5px; line-height:1.8; color:var(--text-muted); margin-bottom:16px; white-space:pre-line;">${noteText}</p>` : ''}

      ${(!window.Telegram?.WebApp?.initData && buyLink) ? `
        <a href="${buyLink}" target="_blank" class="btn btn-primary" style="margin-bottom:12px;">خرید مستقیم در صرافی / دکس ↗</a>
      ` : ''}

      ${isAdmin ? `
        <div class="admin-actions-grid" style="border-top:1px solid var(--border); padding-top:14px; margin-top:14px;">
          <button class="btn btn-secondary" onclick="Modals.openUpdateResult(${s.id})">🎯 ثبت نتیجه</button>
          <button class="btn btn-secondary" style="color:var(--red); border-color:rgba(244,63,94,0.2);" onclick="Modals.deleteSignalAction(${s.id})">🗑️ حذف سیگنال</button>
        </div>` : ''
      }
    `;

    const sheet = document.getElementById('bottomSheet');
    if (sheet) sheet.classList.add('show');
    if (window.TGBridge) TGBridge.syncBackButton(true);

    if (window.TGBridge && typeof TGBridge.showDockActions === 'function') {
      const mainText = buyLink ? 'خرید مستقیم در صرافی ↗' : (contractAddr ? 'کپی آدرس کانترکت (CA)' : null);
      const onMainClick = buyLink 
        ? () => TGBridge.openLink(buyLink)
        : (contractAddr ? () => Views.copyContract(contractAddr) : null);

      const secondaryText = (buyLink && contractAddr) ? 'کپی آدرس کانترکت (CA)' : null;
      const onSecondaryClick = (buyLink && contractAddr) 
        ? () => Views.copyContract(contractAddr) 
        : null;

      if (mainText) {
        TGBridge.showDockActions({ mainText, onMainClick, secondaryText, onSecondaryClick });
      } else {
        TGBridge.hideDockActions();
      }
    }
  },

  closeBottomSheet() {
    const sheet = document.getElementById('bottomSheet');
    if (sheet) sheet.classList.remove('show');

    if (window.TGBridge) {
      TGBridge.syncBackButton(App.state.currentTab !== 'signals');
      if (typeof TGBridge.hideDockActions === 'function') {
        TGBridge.hideDockActions();
      }
    }
  },

  // ⚠️ فیچر جدید: ردیف چیپ فیلتر (شبیه CoinMarketCap) کنار جستجو. ۳ تا
  // چیپ (مرتب‌سازی/بازه/کانال) با تغییرشون فوری اعمال می‌شن، بدون نیاز به
  // دکمه‌ی «اعمال» جدا. سطح ریسک چون کم‌کاربردتره پشت آیکون قیف (⚠️) مونده.
  //
  // ⚠️ فیکس مشاهده‌پذیری: این ۵ تابع (که از onclick/onchange مستقیم صدا
  // زده می‌شن) هرکدوم try/catch اختصاصی گرفتن. چرا این مهمه: اگه یه خطا
  // از داخل یه هندلر inline (onclick=...) به بیرون درز کنه، به
  // window.onerror سراسری می‌رسه که تو وب‌ویوی تلگرام (به‌خصوص نسخه‌ی
  // وب/دسکتاپ که Mini App رو تو iframe لود می‌کنه) ممکنه به‌صورت سانسورشده
  // ("Script error." با خط ۰) گزارش بشه — دقیقاً چیزی که تو لاگ سرور دیده
  // شد. یه catch محلی همینجا، تو همون فایل/اسکوپ، همیشه به پیام و stack
  // واقعی خطا دسترسی داره، مهم نیست وب‌ویو چیکار می‌کنه.

  syncFilterChipsUI() {
    try {
      const f = App.state.signalFilters || { sort: 'newest', timeRange: 'all', channel: 'all', risk: 'all' };
      const sortEl = document.getElementById('chipSort');
      const timeEl = document.getElementById('chipTimeRange');
      const chEl = document.getElementById('chipChannel');
      if (sortEl) sortEl.value = f.sort;
      if (timeEl) timeEl.value = f.timeRange;
      if (chEl) chEl.value = f.channel;
      App.updateFilterActiveDot();
    } catch (e) {
      window.logEvent('JSERR', 'syncFilterChipsUI', { err: e.message || e, stack: (e.stack || '').slice(0, 200) });
    }
  },

  onChipFilterChange() {
    try {
      this.haptic('selection');
      App.state.signalFilters = Object.assign({}, App.state.signalFilters, {
        sort: document.getElementById('chipSort')?.value || 'newest',
        timeRange: document.getElementById('chipTimeRange')?.value || 'all',
        channel: document.getElementById('chipChannel')?.value || 'all',
      });
      App.saveSignalFilters();
      App.updateFilterActiveDot();
      this.renderSignalsList();
    } catch (e) {
      window.logEvent('JSERR', 'onChipFilterChange', { err: e.message || e, stack: (e.stack || '').slice(0, 200) });
    }
  },

  openRiskFilterPanel() {
    try {
      this.haptic('selection');
      const f = App.state.signalFilters || { sort: 'newest', timeRange: 'all', channel: 'all', risk: 'all' };
      const body = document.getElementById('sheetContent');
      if (!body) return;

      body.innerHTML = `
        <h3 style="font-size:15px; font-weight:700; margin-bottom:14px;">فیلتر سطح ریسک</h3>
        <div class="field">
          <select id="chipRiskModal">
            <option value="all" ${f.risk === 'all' ? 'selected' : ''}>همه</option>
            <option value="low" ${f.risk === 'low' ? 'selected' : ''}>🟢 کم‌ریسک</option>
            <option value="high" ${f.risk === 'high' ? 'selected' : ''}>🔴 پرریسک</option>
          </select>
        </div>
        <div style="display:flex; gap:8px; margin-top:16px;">
          <button class="btn btn-secondary" style="flex:1;" onclick="Views.clearAllFilters()">پاک‌کردن همه‌ی فیلترها</button>
          <button class="btn btn-primary" style="flex:1;" onclick="Views.applyRiskFilter()">اعمال</button>
        </div>
      `;

      const sheet = document.getElementById('bottomSheet');
      if (sheet) sheet.classList.add('show');
      if (window.TGBridge && typeof TGBridge.syncBackButton === 'function') {
        TGBridge.syncBackButton(true);
        if (typeof TGBridge.hideDockActions === 'function') TGBridge.hideDockActions();
      }
    } catch (e) {
      window.logEvent('JSERR', 'openRiskFilterPanel', { err: e.message || e, stack: (e.stack || '').slice(0, 200) });
    }
  },

  applyRiskFilter() {
    try {
      this.haptic('success');
      App.state.signalFilters = Object.assign({}, App.state.signalFilters, {
        risk: document.getElementById('chipRiskModal')?.value || 'all',
      });
      App.saveSignalFilters();
      App.updateFilterActiveDot();
      this.closeBottomSheet();
      this.renderSignalsList();
    } catch (e) {
      window.logEvent('JSERR', 'applyRiskFilter', { err: e.message || e, stack: (e.stack || '').slice(0, 200) });
    }
  },

  clearAllFilters() {
    try {
      this.haptic('light');
      App.state.signalFilters = { sort: 'newest', timeRange: 'all', channel: 'all', risk: 'all' };
      App.saveSignalFilters();
      this.syncFilterChipsUI();
      this.closeBottomSheet();
      this.renderSignalsList();
    } catch (e) {
      window.logEvent('JSERR', 'clearAllFilters', { err: e.message || e, stack: (e.stack || '').slice(0, 200) });
    }
  },

  // ================= تب لیدربورد =================
  setLeaderboardType(type) {
    this.haptic('selection');
    App.state.leaderboardType = type;
    const btnCallers = document.getElementById('btnLbCallers');
    const btnGivers = document.getElementById('btnLbGivers');
    if (btnCallers) btnCallers.classList.toggle('active', type === 'callers');
    if (btnGivers) btnGivers.classList.toggle('active', type === 'signal_givers');
    this.renderLeaderboard();
  },

  async renderLeaderboard() {
    const listEl = document.getElementById('leaderboardFeedList');
    if (!listEl) return;

    if (!App.state.leaderboardData || (!App.state.leaderboardData.callers?.length && !App.state.leaderboardData.signal_givers?.length)) {
      listEl.innerHTML = '<div style="text-align:center; padding:24px; color:var(--text-muted); font-size:12px;">در حال بارگذاری رتبه‌بندی...</div>';
      try {
        App.state.leaderboardData = await API.getLeaderboard();
      } catch (e) {
        App.state.leaderboardData = { callers: [], signal_givers: [] };
      }
    }

    const isCallers = App.state.leaderboardType === 'callers';
    const rows = isCallers ? (App.state.leaderboardData?.callers || []) : (App.state.leaderboardData?.signal_givers || []);

    if (!rows || rows.length === 0) {
      listEl.innerHTML = `<div style="text-align:center; padding:32px; color:var(--text-muted); font-size:12px;">هنوز رتبه‌ای ثبت نشده است.</div>`;
      return;
    }

    if (isCallers) {
      listEl.innerHTML = rows.map((r, i) => `
        <div class="card-atomic" style="cursor:default;">
          <div class="card-atomic-top">
            <div class="token-meta">
              <span class="mono" style="color:var(--accent-light); font-weight:700;">#${i + 1}</span>
              <span class="token-name">👤 ${escapeHtml(r.caller_name || 'ناشناس')}</span>
            </div>
            <span style="color:var(--gold); font-size:12.5px; font-weight:700;">★ ${escapeHtml(r.avg_rating || '5.0')}</span>
          </div>
          <div class="card-atomic-bottom">
            <span>${escapeHtml(r.count || 0)} کال ثبت‌شده</span>
            <span>${escapeHtml(r.tier ? r.tier.toUpperCase() : 'BRONZE')}</span>
          </div>
        </div>
      `).join('');
    } else {
      listEl.innerHTML = rows.map((r, i) => `
        <div class="card-atomic" style="cursor:default;">
          <div class="card-atomic-top">
            <div class="token-meta">
              <span class="mono" style="color:var(--accent-light); font-weight:700;">#${i + 1}</span>
              <span class="token-name">📡 ${escapeHtml(r.full_name || r.username || 'کاربر')}</span>
            </div>
            <span style="color:var(--green); font-size:12.5px; font-weight:700;" class="mono">${escapeHtml(r.points || 0)} pt</span>
          </div>
          <div class="card-atomic-bottom">
            <span>${escapeHtml(r.count || 0)} سیگنال · ${escapeHtml(r.wins || 0)} برد</span>
            <span>سطح ${escapeHtml(r.level || 1)}</span>
          </div>
        </div>
      `).join('');
    }
  },

  // ================= تب آکادمی =================
  setAcademySubTab(subTab) {
    this.haptic('selection');
    App.state.academyTab = subTab;
    const btnStrat = document.getElementById('btnAcadStrat');
    const btnArt = document.getElementById('btnAcadArt');
    if (btnStrat) btnStrat.classList.toggle('active', subTab === 'strategies');
    if (btnArt) btnArt.classList.toggle('active', subTab === 'articles');
    this.renderAcademy();
  },

  async renderAcademy() {
    const listEl = document.getElementById('academyFeedList');
    if (!listEl) return;

    const session = App.state.session;
    const tgUid = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    const isAdmin = Boolean(session?.is_admin || session?.is_super_admin);

    if (App.state.academyTab === 'strategies') {
      if (!App.state.strategies || !App.state.strategies.length) {
        listEl.innerHTML = '<div style="text-align:center; padding:24px; color:var(--text-muted); font-size:12px;">در حال دریافت استراتژی‌ها...</div>';
        try {
          App.state.strategies = await API.getContent('strategies');
        } catch (e) {
          App.state.strategies = [];
        }
      }

      if (!App.state.strategies || App.state.strategies.length === 0) {
        listEl.innerHTML = '<div style="text-align:center; padding:32px; color:var(--text-muted); font-size:12px;">ستاپ تحلیلی ثبت نشده است.</div>';
        return;
      }

      listEl.innerHTML = App.state.strategies.map(st => `
        <div class="card-atomic" style="cursor:default;">
          <h4 style="font-size:13.5px; font-weight:700; margin-bottom:6px; color:var(--text);">${escapeHtml(st.title || 'ستاپ معاملاتی')}</h4>
          <p style="font-size:12px; color:var(--text-muted); line-height:1.75;">${escapeHtml(st.desc || st.body || '')}</p>
        </div>
      `).join('');
    } else {
      let adminActionHeader = '';
      if (isAdmin) {
        adminActionHeader = `
          <div style="margin-bottom:12px;">
            <button class="btn btn-secondary" style="border-style:dashed; border-color:var(--accent); color:var(--accent-light);" onclick="Modals.openAddArticleModal()">
              ➕ نگارش و انتشار مقاله جدید
            </button>
          </div>
        `;
      }

      if (!App.state.articles || !App.state.articles.length) {
        listEl.innerHTML = adminActionHeader + '<div style="text-align:center; padding:24px; color:var(--text-muted); font-size:12px;">در حال دریافت مقالات...</div>';
        try {
          App.state.articles = await API.getContent('articles');
        } catch (e) {
          App.state.articles = [];
        }
      }

      if (!App.state.articles || App.state.articles.length === 0) {
        listEl.innerHTML = adminActionHeader + '<div style="text-align:center; padding:32px; color:var(--text-muted); font-size:12px;">مقاله‌ای ثبت نشده است.</div>';
        return;
      }

      const sortedArticles = [...App.state.articles].sort((a, b) => {
        const timeA = a.id ? Number(a.id) : (a.created_at ? new Date(a.created_at).getTime() : 0);
        const timeB = b.id ? Number(b.id) : (b.created_at ? new Date(b.created_at).getTime() : 0);
        return timeB - timeA;
      });

      const gridHtml = `
        <div class="articles-grid">
          ${sortedArticles.map(art => {
            const headerImg = art.image || art.header_image || null;
            const title = escapeHtml(art.title || 'مقاله آموزشی');
            const snippet = escapeHtml(art.desc || (art.body ? art.body.slice(0, 90) : '') || '');
            const dateStr = escapeHtml(art.created_at ? String(art.created_at).split(' ')[0] : 'اخیر');

            return `
              <div class="article-grid-card" onclick="Views.openArticleReader(${art.id})">
                <div class="article-grid-cover">
                  ${headerImg ? `
                    <img src="${escapeHtml(headerImg)}" alt="${title}" loading="lazy">
                  ` : `
                    <div class="cover-placeholder">📰</div>
                  `}
                </div>
                <div class="article-grid-body">
                  <h4 class="article-grid-title">${title}</h4>
                  <p class="article-grid-snippet">${snippet}</p>
                  <div class="article-grid-meta">
                    <span class="mono">${dateStr}</span>
                    <span class="article-read-badge">مطالعه ↗</span>
                  </div>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `;

      listEl.innerHTML = adminActionHeader + gridHtml;
    }
  },

  openArticleReader(articleId) {
    this.haptic('light');
    const art = (App.state.articles || []).find(item => Number(item.id) === Number(articleId));
    if (!art) return;

    const session = App.state.session;
    const tgUid = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    const isAdmin = Boolean(session?.is_admin || session?.is_super_admin);
    const body = document.getElementById('sheetContent');
    if (!body) return;

    const headerImg = art.image || art.header_image || null;
    // ⚠️ فیکس XSS: قبلاً کل متن مقاله (که از یه textarea ساده میاد، نه ادیتور
    // HTML) مستقیم به‌عنوان HTML رندر می‌شد. حالا escape می‌شه و فقط خط‌های
    // جدید (که خودمون اضافه می‌کنیم، نه از ورودی کاربر) به <br> تبدیل می‌شن تا
    // ظاهر چندخطی مقاله حفظ بشه.
    const fullText = escapeHtml(art.body || art.desc || '').replace(/\n/g, '<br>');
    const title = escapeHtml(art.title || 'مقاله آموزشی');
    const dateStr = escapeHtml(art.created_at || '—');

    body.innerHTML = `
      <div class="article-reader-container">
        ${headerImg ? `
          <div class="article-reader-cover">
            <img src="${escapeHtml(headerImg)}" alt="${title}">
          </div>
        ` : ''}

        <div class="article-reader-header">
          <h2 class="article-reader-title">${title}</h2>
          <div class="article-reader-meta">
            <span class="mono">📅 ${dateStr}</span>
            <span class="article-read-badge">📚 MemeLand Academy</span>
          </div>
        </div>

        <div class="article-reader-body">${fullText}</div>

        ${isAdmin ? `
          <div style="border-top:1px solid var(--border); padding-top:14px; margin-top:10px;">
            <button class="btn btn-secondary" style="color:var(--red); border-color:rgba(244,63,94,0.2);" onclick="Modals.deleteArticleAction(${art.id})">
              🗑️ حذف این مقاله
            </button>
          </div>
        ` : ''}
      </div>
    `;

    const sheet = document.getElementById('bottomSheet');
    if (sheet) sheet.classList.add('show');
    if (window.TGBridge) TGBridge.syncBackButton(true);
  }
};

/* ══════════════════════════════════════════════════════════════════════
 * 🚨 فیکس ریشه‌ای (باگ اصلی این دور):
 *   `const X = {...}` در بالاترین سطح یک classic script، فقط یه binding
 *   *لغوی* توی global scope می‌سازه — برخلاف `var`، هیچ‌وقت به‌صورت
 *   `window.X` قابل‌دسترسی نیست. یعنی `X` کار می‌کرد ولی `window.X`
 *   همیشه undefined بود.
 *   کل کد (app.js، telegram.js، ...) قبل از هر فراخوانی `window.X` رو
 *   چک می‌کرد ⇒ همه‌ی گاردها رد می‌شدن، احراز هویت هیچ‌وقت اجرا نمی‌شد،
 *   سشن null می‌موند و adm=false بود. دقیقاً همون چیزی که تو لاگ دیده شد:
 *     [BOOT] guardFail check=API.getSession hasAPI=false
 *     [BOOT] guardFail check=TGBridge.init hasTGBridge=false
 *     [BOOT] guardFail check=window.Views
 *   این یه خط، اون رو می‌بنده. (avatars.js و pull_refresh.js از اول این
 *   کار رو درست انجام می‌دادن — برای همین اون دوتا هیچ‌وقت guardFail نداشتن.)
 * ══════════════════════════════════════════════════════════════════════ */
window.Views = Views;
if (window.MHLog) MHLog.info('BOOT', 'views.js', { build: window.__MH_BUILD });
