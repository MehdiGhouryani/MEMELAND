/**
 * MemeLand Trader Dossier Module (v7.0.0 - Stealth Aesthetics & Spring Physics)
 */

const Dossier = {
  // Helper to trigger Telegram native haptic feedback
  haptic(type = 'light') {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === 'selection') {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      } else if (type === 'success' || type === 'error') {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred(type);
      } else {
        window.Telegram.WebApp.HapticFeedback.impactOccurred(type);
      }
    } else if (window.TGBridge) {
      TGBridge.haptic(type);
    }
  },

  async show(userId) {
    if (!userId) {
      if (window.TGBridge) TGBridge.showAlert('شناسه کاربری معتبر یافت نشد');
      return;
    }
    this.haptic('selection');

    const sheet = document.getElementById('bottomSheet');
    const body = document.getElementById('sheetContent');
    if (!sheet || !body) return;

    // Fluid Skeleton shimmer loader
    body.innerHTML = `
      <div style="text-align:center; padding:36px 20px;">
        <div style="font-size:24px; margin-bottom:10px; animation:frogVibe 1.2s infinite ease-in-out;">👤</div>
        <div style="font-size:12px; color:var(--text-muted);">در حال دریافت پرونده تریدر...</div>
      </div>
    `;
    sheet.classList.add('show');
    if (window.TGBridge) TGBridge.syncBackButton(true);

    try {
      const headers = (window.API && typeof API.getHeaders === 'function') 
        ? API.getHeaders() 
        : { 'Content-Type': 'application/json' };

      const resp = await fetch(`/site/traders/${userId}`, { headers });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      const roleKey = data.is_admin ? 'admin' : (data.role_key || 'rookie');
      const avatarSvg = (window.AvatarRenderer && typeof AvatarRenderer.getAvatarSvg === 'function') 
        ? AvatarRenderer.getAvatarSvg(roleKey) 
        : '🐸';
      const miniBadge = (window.AvatarRenderer && typeof AvatarRenderer.getRoleMiniBadge === 'function') 
        ? AvatarRenderer.getRoleMiniBadge(roleKey) 
        : '👑';

      const winRateColor = data.win_rate >= 50 ? 'var(--green)' : 'var(--red)';

      body.innerHTML = `
        <div style="display:flex; align-items:center; gap:14px; margin-bottom:18px;">
          <div class="avatar-frame theme-${roleKey}" style="width:58px; height:58px; min-width:58px; min-height:58px; border-radius:50%; background:var(--bg); border:1px solid var(--border); display:flex; align-items:center; justify-content:center; position:relative;">
            <div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center;">${avatarSvg}</div>
            <span class="role-badge-mini" style="position:absolute; bottom:-2px; right:-2px; font-size:12px;">${miniBadge}</span>
          </div>
          <div>
            <h3 style="font-size:16px; font-weight:700; margin-bottom:3px; color:var(--text);">${data.display_name || 'کاربر'}</h3>
            <span class="mono" style="font-size:11.5px; color:var(--text-muted);">${data.username ? '@' + data.username : 'ID: ' + data.telegram_id}</span>
            <div style="margin-top:6px;">
              <span class="chip" style="padding:2px 9px; font-size:10px; border-color:rgba(255,255,255,0.08); background:rgba(255,255,255,0.04); color:var(--accent-light);">${data.display_role || 'معامله‌گر'}</span>
            </div>
          </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:18px;">
          <div class="card-atomic" style="padding:12px; text-align:center; margin:0; cursor:default;">
            <div style="font-size:10.5px; color:var(--text-muted); margin-bottom:4px;">نرخ برد (Win Rate)</div>
            <div class="mono" style="font-size:19px; font-weight:700; color:${winRateColor};">${data.win_rate || 0}%</div>
          </div>
          <div class="card-atomic" style="padding:12px; text-align:center; margin:0; cursor:default;">
            <div style="font-size:10.5px; color:var(--text-muted); margin-bottom:4px;">مجموع سیگنال‌ها</div>
            <div class="mono" style="font-size:19px; font-weight:700; color:var(--gold);">${data.total_signals || 0}</div>
          </div>
          <div class="card-atomic" style="padding:12px; text-align:center; margin:0; cursor:default;">
            <div style="font-size:10.5px; color:var(--text-muted); margin-bottom:4px;">بردها / باخت‌ها</div>
            <div class="mono" style="font-size:13.5px; font-weight:700;">
              <span style="color:var(--green);">${data.wins || 0}W</span> · <span style="color:var(--red);">${data.losses || 0}L</span>
            </div>
          </div>
          <div class="card-atomic" style="padding:12px; text-align:center; margin:0; cursor:default;">
            <div style="font-size:10.5px; color:var(--text-muted); margin-bottom:4px;">بهترین کال</div>
            <div class="mono" style="font-size:12.5px; font-weight:700; color:var(--green); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${data.best_call || '—'}</div>
          </div>
        </div>

        <div style="font-size:12px; font-weight:700; color:var(--text); margin-bottom:10px;">آخرین کال‌های ثبت‌شده:</div>
        <div style="display:flex; flex-direction:column; gap:6px;">
          ${
            !data.recent_signals || data.recent_signals.length === 0 
            ? '<div style="font-size:11px; color:var(--text-muted); text-align:center; padding:16px; background:var(--bg); border-radius:var(--radius-sm);">سیگنالی در تاریخچه موجود نیست.</div>'
            : data.recent_signals.map(s => {
                const roiClass = s.outcome_status === 'win' ? 'roi-win' : (s.outcome_status === 'loss' ? 'roi-loss' : 'roi-open');
                const roiText = s.result || (s.outcome_status === 'open' ? 'در حال معامله' : '—');
                return `
                  <div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg); border:1px solid var(--border); padding:9px 12px; border-radius:var(--radius-sm); font-size:11.5px;">
                    <span style="font-weight:600; color:var(--text);">${s.coin || '—'} <span class="mono" style="color:var(--text-dim); font-size:9.5px; margin-right:4px;">(${s.channel ? s.channel.toUpperCase() : 'DEX'})</span></span>
                    <span class="roi-badge ${roiClass}" style="padding:2px 7px; font-size:10px;">${roiText}</span>
                  </div>
                `;
              }).join('')
          }
        </div>
      `;
    } catch (e) {
      body.innerHTML = `
        <div style="text-align:center; padding:36px 20px;">
          <div style="font-size:24px; margin-bottom:8px; color:var(--red);">⚠️</div>
          <div style="font-size:12px; color:var(--red); font-weight:600;">پرونده این معامله‌گر یافت نشد یا در دسترس نیست.</div>
        </div>
      `;
    }
  }
};