/**
 * MemeLand Modals & Actions Controller
 */

const Modals = {
  // ================= مدال ثبت سیگنال =================
  openAddSignalModal() {
    if (window.TGBridge) TGBridge.haptic('selection');
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
      <button class="btn btn-primary" onclick="Modals.submitNewSignal()">ثبت نهایی</button>
    `;
    document.getElementById('modalOverlay').classList.add('show');
  },

  async submitNewSignal() {
    const coin = document.getElementById('newCoin').value.trim();
    if (!coin) {
      if (window.TGBridge) TGBridge.showAlert('نماد کوین الزامی است');
      return;
    }

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
      if (window.TGBridge) TGBridge.haptic('success');
      this.closeModal();
      await App.loadSignals();
      Views.renderSignalsList();
      const session = await API.getSession();
      if (session) {
        App.state.session = session;
        App.updateUserInterface();
      }
    } else {
      const data = await res.json().catch(() => ({}));
      if (window.TGBridge) {
        TGBridge.haptic('error');
        TGBridge.showAlert(data.error || 'خطا در ثبت سیگنال');
      }
    }
  },

  // ================= مدال ویرایش نتیجه سیگنال =================
  openUpdateResult(signalId) {
    if (window.TGBridge) TGBridge.haptic('selection');
    Views.closeBottomSheet();
    const s = (App.state.signals || []).find(item => item.id === signalId);
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
      <button class="btn btn-primary" onclick="Modals.submitUpdateResult(${s.id})">ثبت نتیجه</button>
    `;
    document.getElementById('modalOverlay').classList.add('show');
  },

  async submitUpdateResult(signalId) {
    const result = document.getElementById('updResult').value.trim();
    const status = document.getElementById('updStatus').value;

    const res = await API.updateSignalResult(signalId, result, status);
    if (res.ok) {
      if (window.TGBridge) TGBridge.haptic('success');
      this.closeModal();
      await App.loadSignals();
      Views.renderSignalsList();
    } else {
      if (window.TGBridge) {
        TGBridge.haptic('error');
        TGBridge.showAlert('خطا در ثبت نتیجه');
      }
    }
  },

  async deleteSignalAction(id) {
    if (window.TGBridge) {
      const conf = await TGBridge.showConfirm('آیا از حذف این سیگنال مطمئن هستید؟');
      if (!conf) return;
    }

    const resp = await API.deleteSignal(id);
    if (resp.ok) {
      if (window.TGBridge) TGBridge.haptic('success');
      Views.closeBottomSheet();
      await App.loadSignals();
      Views.renderSignalsList();
    } else {
      if (window.TGBridge) {
        TGBridge.haptic('error');
        TGBridge.showAlert('خطا در حذف سیگنال');
      }
    }
  },

  // ================= مدال مدیریت کادر =================
  async openManageStaffModal() {
    if (window.TGBridge) TGBridge.haptic('selection');
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
        <button class="btn btn-primary" onclick="Modals.submitAddStaff()">اعطای دسترسی</button>
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
      App.state.staffList = list;

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
          ${!item.is_super ? `<button class="btn btn-secondary" style="width:auto; padding:2px 8px; color:var(--red); font-size:10px;" onclick="Modals.removeStaffAction(${item.user_id})">حذف</button>` : '<span style="font-size:10px; color:var(--gold);">Super</span>'}
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
      if (window.TGBridge) TGBridge.showAlert('شناسه عددی باید عدد باشد');
      return;
    }

    const resp = await fetch('/site/staff', {
      method: 'POST',
      headers: API.getHeaders(),
      body: JSON.stringify({ user_id: parseInt(uid), role })
    });

    if (resp.ok) {
      if (window.TGBridge) {
        TGBridge.haptic('success');
        TGBridge.showAlert('نقش با موفقیت اعمال شد');
      }
      await this.loadStaffList();
    } else {
      if (window.TGBridge) {
        TGBridge.haptic('error');
        TGBridge.showAlert('خطا در ثبت نقش');
      }
    }
  },

  async removeStaffAction(uid) {
    if (window.TGBridge) {
      const conf = await TGBridge.showConfirm(`آیا از خلع دسترسی کاربر ${uid} مطمئن هستید؟`);
      if (!conf) return;
    }

    const resp = await fetch(`/site/staff/${uid}`, {
      method: 'DELETE',
      headers: API.getHeaders()
    });

    if (resp.ok) {
      if (window.TGBridge) TGBridge.haptic('success');
      await this.loadStaffList();
    } else {
      if (window.TGBridge) {
        TGBridge.haptic('error');
        TGBridge.showAlert('امکان حذف این کاربر وجود ندارد');
      }
    }
  },

  closeModal() {
    const modal = document.getElementById('modalOverlay');
    if (modal) modal.classList.remove('show');
  }
};