/**
 * MemeLand Modals & Actions Controller (v7.0.0 - Stealth Design & Full Staff Management)
 */

const Modals = {
  currentStaffFilter: 'all',

  // Helper to extract a fully valid authentication token and build safe headers
  getAuthContext() {
    const sess = (window.App && App.state && App.state.session) || {};
    let token = sess.token || localStorage.getItem('ml_token') || sessionStorage.getItem('ml_token') || '';
    
    if (!token) {
      try {
        const stored = JSON.parse(localStorage.getItem('memeland_session') || '{}');
        token = stored.token || '';
      } catch (e) {}
    }

    const initData = window.Telegram?.WebApp?.initData || '';
    const telegramId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id || sess.user_id || '';

    const headers = {
      'Content-Type': 'application/json'
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    if (initData) {
      headers['X-Telegram-Init-Data'] = initData;
    }
    if (telegramId) {
      headers['X-Telegram-User-Id'] = String(telegramId);
    }

    return { token, initData, telegramId, headers };
  },

  haptic(type = 'light') {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === 'selection') window.Telegram.WebApp.HapticFeedback.selectionChanged();
      else if (type === 'success' || type === 'error') window.Telegram.WebApp.HapticFeedback.notificationOccurred(type);
      else window.Telegram.WebApp.HapticFeedback.impactOccurred(type);
    } else if (window.TGBridge) {
      TGBridge.haptic(type);
    }
  },

  // ================= مدال ثبت سیگنال با آپلود تصویر =================
  openAddSignalModal() {
    this.haptic('selection');

    document.getElementById('modalTitle').textContent = 'ثبت سیگنال تحلیلی';
    document.getElementById('modalBody').innerHTML = `
      <div class="field">
        <label>نماد دارایی (Coin / Ticker):</label>
        <input id="newCoin" placeholder="مثلاً $PEPE یا SOL" autocomplete="off">
      </div>
      <div class="field">
        <label>شبکه / دسته‌بندی:</label>
        <select id="newChannel">
          <option value="dex">دکس (Solana / EVM)</option>
          <option value="alt">آلت‌کوین</option>
          <option value="stock">سهام جهانی</option>
          <option value="irbourse">بورس ایران</option>
        </select>
      </div>
      <div class="field">
        <label>تصویر چارت (واترمارک و بهینه‌سازی):</label>
        <input type="file" id="signalPhotoFileInput" accept="image/*" onchange="Modals.handleImageUpload(this, 'signalBeforeImg', 'uploadStatusText')">
        <input type="hidden" id="signalBeforeImg">
        <div id="uploadStatusText" style="font-size:11px; color:var(--text-muted); margin-top:5px;">فرمت‌های مجاز: JPG, PNG (حداکثر ۸MB)</div>
      </div>
      <div class="field">
        <label>آدرس کانترکت (Contract Address):</label>
        <input id="newCA" class="mono" placeholder="0x... یا آدرس سالید">
      </div>
      <div class="field">
        <label>لینک مرجع / صرافی (GMGN / Raydium):</label>
        <input id="newBuyLink" class="mono" placeholder="https://...">
      </div>
      <div class="field">
        <label>توضیحات و تارگت‌ها:</label>
        <textarea id="newNote" rows="3" placeholder="سطوح ورود، حد ضرر و تارگت‌های تحلیلی..."></textarea>
      </div>
      <button class="btn btn-primary" id="btnSubmitSignal" onclick="Modals.submitNewSignal()">ثبت نهایی سیگنال</button>
    `;
    document.getElementById('modalOverlay').classList.add('show');
  },

  async handleImageUpload(input, targetHiddenId, statusElId) {
    const file = input.files[0];
    if (!file) return;

    const status = document.getElementById(statusElId);
    if (status) {
      status.textContent = 'در حال آپلود و پردازش تصویر...';
      status.style.color = 'var(--gold)';
    }

    const formData = new FormData();
    formData.append('image', file);

    const { token, initData, telegramId } = this.getAuthContext();
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (initData) headers['X-Telegram-Init-Data'] = initData;
    if (telegramId) headers['X-Telegram-User-Id'] = String(telegramId);

    try {
      const resp = await fetch('/site/upload', {
        method: 'POST',
        headers: headers,
        body: formData
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(`HTTP ${resp.status}: ${errJson.error || 'Upload error'}`);
      }

      const data = await resp.json();
      document.getElementById(targetHiddenId).value = data.url;
      if (status) {
        status.textContent = 'تصویر با موفقیت ثبت شد ✓';
        status.style.color = 'var(--green)';
      }
    } catch(err) {
      if (status) {
        status.textContent = 'خطا در آپلود تصویر';
        status.style.color = 'var(--red)';
      }
      if (window.sendRemoteLog) window.sendRemoteLog('IMG_FAIL: ' + err.message);
    }
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
      before_img: document.getElementById('signalBeforeImg').value || null,
      contract_address: document.getElementById('newCA').value.trim() || null,
      buy_link: document.getElementById('newBuyLink').value.trim() || null,
      note: document.getElementById('newNote').value.trim() || null,
      tier: 'free',
      outcome_status: 'open'
    };

    const res = await API.createSignal(payload);
    if (res.ok) {
      this.haptic('success');
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
      this.haptic('error');
      if (window.TGBridge) {
        TGBridge.showAlert(data.error || 'خطا در ثبت سیگنال');
      }
    }
  },

  // ================= مدال افزودن مقاله و انتشار =================
  openAddArticleModal() {
    this.haptic('selection');

    document.getElementById('modalTitle').textContent = 'انتشار مقاله در آکادمی';
    document.getElementById('modalBody').innerHTML = `
      <div class="field">
        <label>عنوان مقاله:</label>
        <input id="articleTitle" placeholder="مثلاً روانشناسی رفتار تریدر در میم‌کوین‌ها...">
      </div>
      <div class="field">
        <label>تصویر شاخص مقاله:</label>
        <input type="file" id="articlePhotoInput" accept="image/*" onchange="Modals.handleImageUpload(this, 'articleHeaderImg', 'articleUploadStatus')">
        <input type="hidden" id="articleHeaderImg">
        <div id="articleUploadStatus" style="font-size:11px; color:var(--text-muted); margin-top:5px;">فرمت‌های مجاز: JPG, PNG</div>
      </div>
      <div class="field">
        <label>متن کامل مقاله:</label>
        <textarea id="articleBody" rows="7" placeholder="محتوای آموزشی، تجربیات تحلیلی، استراتژی‌های مدیریت ریسک..."></textarea>
      </div>
      <button class="btn btn-primary" id="btnSubmitArticle" onclick="Modals.submitNewArticle()">انتشار مقاله</button>
    `;
    document.getElementById('modalOverlay').classList.add('show');
  },

  async submitNewArticle() {
    const title = document.getElementById('articleTitle').value.trim();
    const body = document.getElementById('articleBody').value.trim();
    const image = document.getElementById('articleHeaderImg').value || null;

    if (!title || !body) {
      if (window.TGBridge) TGBridge.showAlert('عنوان و متن مقاله الزامی است');
      return;
    }

    const { token, initData, telegramId, headers } = this.getAuthContext();

    const payload = {
      title: title,
      body: body,
      image: image,
      init_data: initData,
      telegram_id: telegramId
    };

    try {
      const resp = await fetch('/site/content/articles', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });

      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        this.haptic('error');
        if (window.TGBridge) TGBridge.showAlert(d.error || 'خطا در دسترسی و انتشار مقاله (۴۰۳)');
        return;
      }

      this.haptic('success');
      this.closeModal();
      App.state.articles = [];
      await Views.renderAcademy();
    } catch (e) {
      this.haptic('error');
      if (window.TGBridge) TGBridge.showAlert('خطا در برقراری ارتباط با سرور');
    }
  },

  async deleteArticleAction(articleId) {
    if (window.TGBridge) {
      const conf = await TGBridge.showConfirm('آیا از حذف این مقاله مطمئن هستید؟');
      if (!conf) return;
    }

    const { headers } = this.getAuthContext();

    try {
      const resp = await fetch(`/site/content/articles/${articleId}`, {
        method: 'DELETE',
        headers: headers
      });

      if (resp.ok) {
        this.haptic('success');
        App.state.articles = [];
        await Views.renderAcademy();
      } else {
        if (window.TGBridge) TGBridge.showAlert('خطا در حذف مقاله');
      }
    } catch (e) {
      if (window.TGBridge) TGBridge.showAlert('خطا در ارتباط با سرور');
    }
  },

  // ================= مدال ویرایش نتیجه سیگنال =================
  openUpdateResult(signalId) {
    this.haptic('selection');

    Views.closeBottomSheet();
    const s = (App.state.signals || []).find(item => item.id === signalId);
    if (!s) return;

    document.getElementById('modalTitle').textContent = `بروزرسانی وضعیت ${s.coin || ''}`;
    document.getElementById('modalBody').innerHTML = `
      <div class="field">
        <label>درصد سود یا نتیجه نهایی:</label>
        <input id="updResult" class="mono" value="${s.result || ''}" placeholder="مثلاً +240% یا تارگت نهایی">
      </div>
      <div class="field">
        <label>وضعیت بسته شدن پوزیشن:</label>
        <select id="updStatus">
          <option value="win" ${s.outcome_status === 'win' ? 'selected' : ''}>✅ برد با سود (Win)</option>
          <option value="loss" ${s.outcome_status === 'loss' ? 'selected' : ''}>❌ فعال‌سازی استاپ (Loss)</option>
          <option value="open" ${s.outcome_status === 'open' ? 'selected' : ''}>⏳ در جریان (Open)</option>
        </select>
      </div>
      <button class="btn btn-primary" onclick="Modals.submitUpdateResult(${s.id})">ثبت و ذخیره تغییرات</button>
    `;
    document.getElementById('modalOverlay').classList.add('show');
  },

  async submitUpdateResult(signalId) {
    const result = document.getElementById('updResult').value.trim();
    const status = document.getElementById('updStatus').value;

    const res = await API.updateSignalResult(signalId, result, status);
    if (res.ok) {
      this.haptic('success');
      this.closeModal();
      await App.loadSignals();
      Views.renderSignalsList();
    } else {
      this.haptic('error');
      if (window.TGBridge) TGBridge.showAlert('خطا در ثبت نتیجه');
    }
  },

  async deleteSignalAction(id) {
    if (window.TGBridge) {
      const conf = await TGBridge.showConfirm('آیا از حذف این سیگنال مطمئن هستید؟');
      if (!conf) return;
    }

    const resp = await API.deleteSignal(id);
    if (resp.ok) {
      this.haptic('success');
      Views.closeBottomSheet();
      await App.loadSignals();
      Views.renderSignalsList();
    } else {
      this.haptic('error');
      if (window.TGBridge) TGBridge.showAlert('خطا در حذف سیگنال');
    }
  },

  // ================= مدال مدیریت کادر و اعضای تیم (طراحی جدید و پیشرفته) =================
  async openManageStaffModal() {
    this.haptic('selection');
    this.currentStaffFilter = 'all';

    document.getElementById('modalTitle').textContent = 'مدیریت کادر و نقش‌های فعال';
    document.getElementById('modalBody').innerHTML = `
      <!-- بخش افزودن یا ویرایش عضو جدید -->
      <div style="background:var(--bg); border:1px solid var(--border); border-radius:var(--radius-md); padding:14px; margin-bottom:14px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <span style="font-size:12.5px; font-weight:700; color:var(--text);">➕ اعطا یا تغییر نقش کاربر</span>
        </div>
        <div class="field" style="margin-bottom:8px;">
          <label>شناسه عددی تلگرام (User ID):</label>
          <input id="staffUserId" class="mono" placeholder="مثلاً 123456789" autocomplete="off">
        </div>
        <div class="field" style="margin-bottom:12px;">
          <label>سطح دسترسی و نقش:</label>
          <select id="staffRole">
            <option value="admin">👑 Admin (مدیریت کامل سیستم)</option>
            <option value="vip_helper">💎 VIP Helper (دسترسی کمکی)</option>
            <option value="og">👑 Memeland OG (۵۰ کال موفق)</option>
            <option value="alpha">🚀 Alpha Master (۱۵ کال موفق)</option>
            <option value="guardian">🦈 Guardian (۸ کال موفق)</option>
            <option value="explorer">🐸 Explorer (۵ کال موفق)</option>
          </select>
        </div>
        <button class="btn btn-primary" onclick="Modals.submitAddStaff()">اعمال و ذخیره نقش</button>
      </div>

      <!-- فیلترهای دسته‌بندی کادر -->
      <div class="filter-scroll" style="margin-bottom:10px;">
        <button class="chip active" id="staffFilter-all" onclick="Modals.filterStaff('all')">همه اعضا</button>
        <button class="chip" id="staffFilter-admin" onclick="Modals.filterStaff('admin')">مدیران</button>
        <button class="chip" id="staffFilter-helper" onclick="Modals.filterStaff('helper')">دستیاران</button>
        <button class="chip" id="staffFilter-traders" onclick="Modals.filterStaff('traders')">تریدرهای ویژه</button>
      </div>

      <!-- کانتینر لیست کادر -->
      <div>
        <div id="staffListContainer" style="display:flex; flex-direction:column; gap:8px;">
          <div style="text-align:center; padding:24px; color:var(--text-muted); font-size:12px;">در حال بارگذاری لیست اعضا...</div>
        </div>
      </div>
    `;
    document.getElementById('modalOverlay').classList.add('show');
    await this.loadStaffList();
  },

  filterStaff(type) {
    this.haptic('selection');
    this.currentStaffFilter = type;
    document.querySelectorAll('[id^="staffFilter-"]').forEach(el => el.classList.remove('active'));
    document.getElementById(`staffFilter-${type}`)?.classList.add('active');
    this.renderStaffRows();
  },

  async loadStaffList() {
    const { headers } = this.getAuthContext();
    try {
      const resp = await fetch('/site/staff', { headers });
      if (!resp.ok) throw new Error();
      const list = await resp.json();
      App.state.staffList = list;
      this.renderStaffRows();
    } catch (e) {
      const cont = document.getElementById('staffListContainer');
      if (cont) cont.innerHTML = '<div style="text-align:center; padding:20px; font-size:12px; color:var(--red);">خطا در دریافت لیست مدیران</div>';
    }
  },

  renderStaffRows() {
    const cont = document.getElementById('staffListContainer');
    if (!cont) return;

    let list = App.state.staffList || [];
    const filter = this.currentStaffFilter;

    if (filter === 'admin') {
      list = list.filter(x => x.role === 'admin' || x.is_super);
    } else if (filter === 'helper') {
      list = list.filter(x => x.role === 'vip_helper');
    } else if (filter === 'traders') {
      list = list.filter(x => ['og', 'alpha', 'guardian', 'explorer'].includes(x.role));
    }

    if (!list.length) {
      cont.innerHTML = `
        <div style="text-align:center; padding:24px 10px; background:var(--bg); border:1px dashed var(--border); border-radius:var(--radius-md); font-size:11.5px; color:var(--text-muted);">
          عضوی در این دسته‌بندی یافت نشد.
        </div>
      `;
      return;
    }

    const roleBadgeMap = {
      admin: '👑 مدیر',
      vip_helper: '💎 دستیار',
      og: '👑 OG',
      alpha: '🚀 Alpha',
      guardian: '🦈 Guardian',
      explorer: '🐸 Explorer'
    };

    cont.innerHTML = list.map(item => {
      const roleText = item.is_super ? '👑 Super Admin' : (roleBadgeMap[item.role] || item.role);
      const isSuper = Boolean(item.is_super);
      const displayName = item.first_name || `کاربر ${item.user_id}`;
      const username = item.username || `ID: ${item.user_id}`;
      const roleKey = item.role || 'rookie';

      return `
        <div class="card-atomic" style="margin:0; padding:10px 12px; cursor:default;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:10px;">
              <div class="avatar-frame theme-${roleKey}" style="width:38px !important; height:38px !important; min-width:38px !important; min-height:38px !important;">
                <div style="font-size:16px;">${isSuper ? '👑' : (window.AvatarRenderer ? AvatarRenderer.getRoleMiniBadge(roleKey) : '👤')}</div>
              </div>
              <div>
                <div style="font-size:12.5px; font-weight:700; color:var(--text); line-height:1.3;">
                  ${displayName}
                </div>
                <div style="font-size:10.5px; color:var(--text-muted); display:flex; align-items:center; gap:6px; margin-top:2px;">
                  <span class="mono">${username}</span>
                  <span style="opacity:0.4;">•</span>
                  <span class="mono" style="cursor:pointer; text-decoration:underline;" onclick="event.stopPropagation(); Views.copyContract('${item.user_id}')">${item.user_id}</span>
                </div>
              </div>
            </div>

            <div style="display:flex; align-items:center; gap:6px;">
              <span class="badge-vip" style="font-size:9.5px; padding:2px 7px;">${roleText}</span>
              ${!isSuper ? `
                <button class="btn-del-article" style="padding:4px 8px; font-size:10px;" onclick="Modals.removeStaffAction(${item.user_id})">حذف</button>
              ` : ''}
            </div>
          </div>
        </div>
      `;
    }).join('');
  },

  async submitAddStaff() {
    const uid = document.getElementById('staffUserId').value.trim();
    const role = document.getElementById('staffRole').value;
    if (!uid || !/^\d+$/.test(uid)) {
      if (window.TGBridge) TGBridge.showAlert('شناسه عددی تلگرام باید صرفاً شامل ارقام باشد');
      return;
    }

    const { headers } = this.getAuthContext();

    const resp = await fetch('/site/staff', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({ user_id: parseInt(uid), role })
    });

    if (resp.ok) {
      this.haptic('success');
      if (window.TGBridge) TGBridge.showAlert('نقش با موفقیت اعمال شد');
      document.getElementById('staffUserId').value = '';
      await this.loadStaffList();
    } else {
      this.haptic('error');
      if (window.TGBridge) TGBridge.showAlert('خطا در اعمال نقش');
    }
  },

  async removeStaffAction(uid) {
    if (window.TGBridge) {
      const conf = await TGBridge.showConfirm(`آیا از سلب دسترسی کاربر ${uid} اطمینان دارید؟`);
      if (!conf) return;
    }

    const { headers } = this.getAuthContext();

    const resp = await fetch(`/site/staff/${uid}`, {
      method: 'DELETE',
      headers: headers
    });

    if (resp.ok) {
      this.haptic('success');
      await this.loadStaffList();
    } else {
      this.haptic('error');
      if (window.TGBridge) TGBridge.showAlert('امکان حذف این کاربر وجود ندارد');
    }
  },

  closeModal() {
    const modal = document.getElementById('modalOverlay');
    if (modal) modal.classList.remove('show');
  }
};