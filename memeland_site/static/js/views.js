/**
 * MemeLand Views & Feed Renderer (v7.1.0 - Robust Filtering & Diagnostic Logs)
 */

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

  // متد مرکزی فراخوانی بازخورد لمسی (Haptic)
  haptic(type = 'light') {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === 'selection') {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      } else if (type === 'success' || type === 'error' || type === 'warning') {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred(type);
      } else {
        window.Telegram.WebApp.HapticFeedback.impactOccurred(type);
      }
    } else if (window.TGBridge && typeof TGBridge.haptic === 'function') {
      TGBridge.haptic(type);
    }
  },

  // ================= تب سیگنال‌ها =================
  renderSignalsList() {
    const listEl = document.getElementById('signalsFeedList');
    if (!listEl) return;

    const isClosed = App.state.signalSubTab === 'closed';
    const allSignals = App.state.signals || [];

    // فیلتر منعطف بر اساس وضعیت‌های مختلف ثبت‌شده در دیتابیس (open/active/closed/win/loss)
    const list = allSignals.filter(s => {
      const rawStatus = String(s.outcome_status || s.status || 'open').toLowerCase();
      const matchStatus = isClosed
        ? (rawStatus === 'win' || rawStatus === 'loss' || rawStatus === 'closed')
        : (rawStatus === 'open' || rawStatus === 'active');

      const rawChannel = String(s.channel || s.category || 'dex').toLowerCase();
      const matchCat = App.state.category === 'all' || rawChannel === App.state.category;

      const coinName = String(s.coin || s.symbol || s.name || '').toLowerCase();
      const matchSearch = !App.state.searchQuery || coinName.includes(App.state.searchQuery.toLowerCase());

      return matchStatus && matchCat && matchSearch;
    });

    // لاگ تشخیصی برای مانیتورینگ تعداد سیگنال‌ها در ترمینال سرور
    if (window.sendRemoteLog) {
      window.sendRemoteLog(`[VIEW] Render: tab=${App.state.signalSubTab}, cat=${App.state.category}, total=${allSignals.length}, filtered=${list.length}`);
    }

    if (list.length === 0) {
      listEl.innerHTML = `
        <div style="text-align:center; padding:44px 20px; color:var(--text-muted); font-size:12px;">
          <div style="font-size:24px; margin-bottom:8px; opacity:0.6;">🔍</div>
          سیگنالی در این دسته‌بندی یافت نشد.
        </div>
      `;
      return;
    }

    listEl.innerHTML = list.map(s => {
      const statusKey = String(s.outcome_status || s.status || 'open').toLowerCase();
      const roiClass = statusKey === 'win' ? 'roi-win' : (statusKey === 'loss' ? 'roi-loss' : 'roi-open');
      const roiText = s.result ? s.result : (statusKey === 'open' || statusKey === 'active' ? 'در حال معامله' : '—');
      const caller = s.caller_name || s.owner_first_name || 'تیم تحلیلی';
      const callerId = s.owner_telegram_id || s.caller_telegram_id || null;
      const coinTitle = s.coin || s.symbol || '—';
      const channelTitle = (s.channel || s.category || 'DEX').toUpperCase();
      const contractAddr = s.contract_address || s.ca || null;

      const caPart = contractAddr
        ? `<span class="ca-chip" onclick="event.stopPropagation(); Views.copyContract('${contractAddr}')">📋 ${contractAddr.slice(0, 4)}...${contractAddr.slice(-4)}</span>`
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
    const isAdmin = Boolean(session && (session.role === 'admin' || session.is_admin === true || session.is_super_admin === true));
    const body = document.getElementById('sheetContent');
    if (!body) return;

    const coinTitle = s.coin || s.symbol || '—';
    const channelTitle = (s.channel || s.category || 'DEX').toUpperCase();
    const contractAddr = s.contract_address || s.ca || null;
    const buyLink = s.buy_link || s.link || null;
    const chartImg = s.before_img || s.image || null;

    body.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <h3 style="font-size:17px; font-weight:700;">${coinTitle}</h3>
        <span class="badge-chain">${channelTitle}</span>
      </div>
      
      ${chartImg ? `
        <div style="margin-bottom:14px; border-radius:var(--radius-md); overflow:hidden; border:1px solid var(--border); background:var(--bg);">
          <img src="${chartImg}" style="width:100%; display:block; max-height:260px; object-fit:cover;" alt="Chart">
        </div>` : ''
      }

      ${contractAddr ? `
        <div style="background:var(--bg); padding:10px 12px; border-radius:var(--radius-sm); border:1px solid var(--border); margin-bottom:12px; font-size:11.5px; display:flex; justify-content:space-between; align-items:center;">
          <span class="mono" style="color:var(--text); word-break:break-all; font-size:11px;">${contractAddr}</span>
          <button class="btn btn-secondary" style="width:auto; padding:4px 10px; font-size:10.5px; margin-right:8px;" onclick="Views.copyContract('${contractAddr}')">کپی</button>
        </div>` : ''
      }

      ${s.note ? `<p style="font-size:12.5px; line-height:1.8; color:var(--text-muted); margin-bottom:16px; white-space:pre-line;">${s.note}</p>` : ''}

      <!-- دکمه فال‌بک مرورگر دسکتاپ خارج از تلگرام -->
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

    // اتصال اکشن‌ها به داک بومی تلگرام (MainButton و SecondaryButton)
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
              <span class="mono" style="color:var(--accent-light); font-weight:700;">#${i + 1}</span>
              <span class="token-name">📡 ${r.full_name || r.username || 'کاربر'}</span>
            </div>
            <span style="color:var(--green); font-size:12.5px; font-weight:700;" class="mono">${r.points || 0} pt</span>
          </div>
          <div class="card-atomic-bottom">
            <span>${r.count || 0} سیگنال · ${r.wins || 0} برد</span>
            <span>سطح ${r.level || 1}</span>
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
    const isAdmin = Boolean(session && (session.role === 'admin' || session.is_admin === true || session.is_super_admin === true));

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
          <h4 style="font-size:13.5px; font-weight:700; margin-bottom:6px; color:var(--text);">${st.title || 'ستاپ معاملاتی'}</h4>
          <p style="font-size:12px; color:var(--text-muted); line-height:1.75;">${st.desc || st.body || ''}</p>
        </div>
      `).join('');
    } else {
      let adminActionHeader = '';
      if (isAdmin) {
        adminActionHeader = `
          <div style="margin-bottom:14px;">
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

      const articlesHtml = App.state.articles.map(art => {
        const headerImg = art.image || art.header_image || null;
        return `
          <div class="article-card">
            ${headerImg ? `
              <div class="article-cover">
                <img src="${headerImg}" alt="${art.title || ''}" loading="lazy">
              </div>` : ''
            }
            <div class="article-content">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:6px;">
                <h4 class="article-title">${art.title || 'مقاله آموزشی'}</h4>
                ${isAdmin && art.id ? `
                  <button class="btn-del-article" onclick="Modals.deleteArticleAction(${art.id})">حذف</button>
                ` : ''}
              </div>
              <div class="article-body">${art.body || art.desc || ''}</div>
              ${art.created_at ? `<span class="article-date mono">${art.created_at}</span>` : ''}
            </div>
          </div>
        `;
      }).join('');

      listEl.innerHTML = adminActionHeader + articlesHtml;
    }
  }
};