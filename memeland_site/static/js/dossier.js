/**
 * MemeLand Public Trader Dossier Controller
 */

const Dossier = {
  async show(userId) {
    if (!userId) return;
    TGBridge.haptic('selection');

    const sheet = document.getElementById('bottomSheet');
    const body = document.getElementById('sheetContent');
    body.innerHTML = '<div style="text-align:center; padding:30px; font-size:12px; color:var(--text-muted);">در حال دریافت پرونده معامله‌گر...</div>';
    sheet.classList.add('show');
    TGBridge.syncBackButton(true);

    const data = await API.getTraderProfile(userId);
    if (!data) {
      body.innerHTML = '<div style="text-align:center; padding:30px; font-size:12px; color:var(--red);">پرونده این معامله‌گر یافت نشد.</div>';
      return;
    }

    const roleKey = data.is_admin ? 'admin' : (data.role_key || 'rookie');
    const avatarSvg = window.AvatarRenderer ? AvatarRenderer.getAvatarSvg(roleKey) : '';
    const miniBadge = window.AvatarRenderer ? AvatarRenderer.getRoleMiniBadge(roleKey) : '🐣';

    body.innerHTML = `
      <div style="display:flex; align-items:center; gap:14px; margin-bottom:16px;">
        <div class="avatar-frame theme-${roleKey}" style="width:64px; height:64px;">
          <div style="width:100%; height:100%;">${avatarSvg}</div>
          <span class="role-badge-mini">${miniBadge}</span>
        </div>
        <div>
          <h3 style="font-size:16px; margin-bottom:4px;">${data.display_name}</h3>
          <span style="font-size:11px; color:var(--text-muted);">${data.username ? '@' + data.username : 'شناسه: ' + data.telegram_id}</span>
          <div style="margin-top:4px;">
            <span class="chip" style="padding:2px 8px; font-size:10px; border-color:transparent; background:rgba(255,255,255,0.06);">${data.display_role}</span>
          </div>
        </div>
      </div>

      <!-- شبکه ویجت‌های آماری -->
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:16px;">
        <div class="card-atomic" style="padding:10px; text-align:center; margin:0;">
          <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">نرخ برد (Win Rate)</div>
          <div class="mono" style="font-size:18px; font-weight:700; color:${data.win_rate >= 50 ? 'var(--teal)' : 'var(--red)'};">${data.win_rate}%</div>
        </div>
        <div class="card-atomic" style="padding:10px; text-align:center; margin:0;">
          <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">مجموع سیگنال‌ها</div>
          <div class="mono" style="font-size:18px; font-weight:700; color:var(--gold);">${data.total_signals}</div>
        </div>
        <div class="card-atomic" style="padding:10px; text-align:center; margin:0;">
          <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">بردها / باخت‌ها</div>
          <div class="mono" style="font-size:13px; font-weight:700;">
            <span style="color:var(--teal);">${data.wins}W</span> · <span style="color:var(--red);">${data.losses}L</span>
          </div>
        </div>
        <div class="card-atomic" style="padding:10px; text-align:center; margin:0;">
          <div style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">بهترین کال</div>
          <div class="mono" style="font-size:12px; font-weight:700; color:var(--teal); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${data.best_call}</div>
        </div>
      </div>

      <!-- آخرین سیگنال‌های تریدر -->
      <div style="font-size:12px; font-weight:700; margin-bottom:8px;">آخرین کال‌های ثبت‌شده:</div>
      <div style="display:flex; flex-direction:column; gap:6px;">
        ${
          data.recent_signals.length === 0 
          ? '<div style="font-size:11px; color:var(--text-muted); text-align:center; padding:10px;">سیگنالی موجود نیست.</div>'
          : data.recent_signals.map(s => `
              <div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg); padding:7px 10px; border-radius:8px; font-size:11px;">
                <span>${s.coin} <span style="color:var(--text-muted); font-size:9px;">(${s.channel.toUpperCase()})</span></span>
                <span class="roi-badge ${s.outcome_status === 'win' ? 'roi-win' : (s.outcome_status === 'loss' ? 'roi-loss' : 'roi-open')}" style="padding:1px 6px; font-size:9px;">
                  ${s.result || (s.outcome_status === 'open' ? 'درحال معامله' : '—')}
                </span>
              </div>
            `).join('')
        }
      </div>
    `;
  }
};