/**
 * MemeLand Views & Feed Renderer (v6.5.0 with Academic Header Covers)
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

  // ================= تب سیگنال‌ها =================
  renderSignalsList() {
    const listEl = document.getElementById('signalsFeedList');
    if (!listEl) return;

    const isClosed = App.state.signalSubTab === 'closed';

    let list = (App.state.signals || []).filter(s => {
      const matchStatus = isClosed
        ? (s.outcome_status === 'win' || s.outcome_status === 'loss')
        : (s.outcome_status === 'open');
      const matchCat = App.state.category === 'all' || s.channel === App.state.category;
      const matchSearch = !App.state.searchQuery || (s.coin && s.coin.toLowerCase().includes(App.state.searchQuery));
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

      const caPart = s.contract_address
        ? `<span class="ca-chip" onclick="event.stopPropagation(); if(window.TGBridge) TGBridge.copyText('${s.contract_address}')">📋 ${s.contract_address.slice(0, 4)}...${s.contract_address.slice(-4)}</span>`
        : '';

      const callerPart = callerId
        ? `<span class="caller-chip" onclick="event.stopPropagation(); Dossier.show(${callerId})" style="cursor:pointer; text-decoration:underline; font-weight:600; color:var(--teal);">👤 ${caller}</span>`
        : `<span>👤 ${caller}</span>`;

      return `
        <div class="card-atomic" onclick="Views.openSignalDetails(${s.id})">
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
    if (window.TGBridge) TGBridge.haptic('light');
    const s = (App.state.signals || []).find(item => item.id === signalId);
    if (!s) return;

    const isAdmin = Boolean(App.state.session && (App.state.session.role === 'admin' || App.state.session.is_admin === true));
    const body = document.getElementById('sheetContent');
    if (!body) return;

    body.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h3 style="font-size:17px;">${s.coin || '—'}</h3>
        <span class="badge-chain">${s.channel ? s.channel.toUpperCase() : 'DEX'}</span>
      </div>
      
      ${s.before_img ? `
        <div style="margin-bottom:12px; border-radius:12px; overflow:hidden; border:1px solid var(--border);">
          <img src="${s.before_img}" style="width:100%; display:block; max-height:260px; object-fit:cover;" alt="Chart">
        </div>` : ''
      }

      ${s.contract_address ? `
        <div style="background:var(--bg); padding:9px 12px; border-radius:10px; margin-bottom:12px; font-size:11px; display:flex; justify-content:space-between; align-items:center;">
          <span class="mono">${s.contract_address}</span>
          <button class="btn btn-teal" style="width:auto; padding:4px 9px; font-size:10px;" onclick="if(window.TGBridge) TGBridge.copyText('${s.contract_address}')">کپی CA</button>
        </div>` : ''
      }

      ${s.note ? `<p style="font-size:12px; line-height:1.8; color:var(--text-muted); margin-bottom:14px; white-space:pre-line;">${s.note}</p>` : ''}
      
      ${s.buy_link ? `<a href="${s.buy_link}" target="_blank" class="btn btn-primary" style="margin-bottom:10px;">خرید مستقیم در دکس ↗</a>` : ''}

      ${isAdmin ? `
        <div class="admin-actions-grid" style="border-top:1px solid var(--border); padding-top:12px; margin-top:14px;">
          <button class="btn btn-secondary" onclick="Modals.openUpdateResult(${s.id})">🎯 ثبت نتیجه</button>
          <button class="btn btn-secondary" style="color:var(--red);" onclick="Modals.deleteSignalAction(${s.id})">🗑️ حذف سیگنال</button>
        </div>` : ''
      }
    `;

    const sheet = document.getElementById('bottomSheet');
    if (sheet) sheet.classList.add('show');
    if (window.TGBridge) TGBridge.syncBackButton(true);
  },

  closeBottomSheet() {
    const sheet = document.getElementById('bottomSheet');
    if (sheet) sheet.classList.remove('show');
    if (window.TGBridge) TGBridge.syncBackButton(App.state.currentTab !== 'signals');
  },

  // ================= تب لیدربورد =================
  setLeaderboardType(type) {
    if (window.TGBridge) TGBridge.haptic('selection');
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
      listEl.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:11px;">در حال بارگذاری رتبه‌بندی...</div>';
      try {
        App.state.leaderboardData = await API.getLeaderboard();
      } catch (e) {
        App.state.leaderboardData = { callers: [], signal_givers: [] };
      }
    }

    const isCallers = App.state.leaderboardType === 'callers';
    const rows = isCallers ? (App.state.leaderboardData?.callers || []) : (App.state.leaderboardData?.signal_givers || []);

    if (!rows || rows.length === 0) {
      listEl.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-muted); font-size:12px;">هنوز رتبه‌ای ثبت نشده است.</div>`;
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
              <span class="mono" style="color:var(--pink, #ec4899); font-weight:700;">#${i + 1}</span>
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

  // ================= تب آکادمی با مقالات هدر تصاویری =================
  setAcademySubTab(subTab) {
    if (window.TGBridge) TGBridge.haptic('selection');
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

    const isAdmin = Boolean(App.state.session && (App.state.session.role === 'admin' || App.state.session.is_admin === true));

    if (App.state.academyTab === 'strategies') {
      if (!App.state.strategies || !App.state.strategies.length) {
        listEl.innerHTML = '<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:11px;">در حال دریافت ستاپ‌ها...</div>';
        try {
          App.state.strategies = await API.getContent('strategies');
        } catch (e) {
          App.state.strategies = [];
        }
      }

      if (!App.state.strategies || App.state.strategies.length === 0) {
        listEl.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-muted); font-size:12px;">ستاپ تحلیلی ثبت نشده است.</div>';
        return;
      }

      listEl.innerHTML = App.state.strategies.map(st => `
        <div class="card-atomic" style="cursor:default;">
          <h4 style="font-size:13px; margin-bottom:5px; color:var(--text);">${st.title || 'ستاپ معاملاتی'}</h4>
          <p style="font-size:11px; color:var(--text-muted); line-height:1.7;">${st.desc || st.body || ''}</p>
        </div>
      `).join('');
    } else {
      let adminActionHeader = '';
      if (isAdmin) {
        adminActionHeader = `
          <div style="margin-bottom:12px;">
            <button class="btn btn-secondary" style="border-style:dashed; border-color:var(--teal); color:var(--teal);" onclick="Modals.openAddArticleModal()">
              ➕ نگارش و انتشار مقاله جدید
            </button>
          </div>
        `;
      }

      if (!App.state.articles || !App.state.articles.length) {
        listEl.innerHTML = adminActionHeader + '<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:11px;">در حال دریافت مقالات...</div>';
        try {
          App.state.articles = await API.getContent('articles');
        } catch (e) {
          App.state.articles = [];
        }
      }

      if (!App.state.articles || App.state.articles.length === 0) {
        listEl.innerHTML = adminActionHeader + '<div style="text-align:center; padding:30px; color:var(--text-muted); font-size:12px;">مقاله‌ای ثبت نشده است.</div>';
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