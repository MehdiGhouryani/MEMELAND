/**
 * MemeLand Modals & Actions Controller (v6.5.0 with Article Publishing)
 */

const Modals = {
  // ================= مدال ثبت سیگنال با آپلود واترمارک =================
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
      <div class="field">
        <label>تصویر چارت (واترمارک خودکار):</label>
        <input type="file" id="signalPhotoFileInput" accept="image/*" onchange="Modals.handleImageUpload(this, 'signalBeforeImg', 'uploadStatusText')">
        <input type="hidden" id="signalBeforeImg">
        <div id="uploadStatusText" style="font-size:10.5px; color:var(--text-muted); margin-top:4px;">فرمت‌های مجاز: JPG, PNG (حداکثر ۸MB)</div>
      </div>
      <div class="field"><label>آدرس کانترکت (CA):</label><input id="newCA" placeholder="آدرس کانترکت"></div>
      <div class="field"><label>لینک خرید (GMGN / Raydium):</label><input id="newBuyLink" placeholder="https://..."></div>
      <div class="field"><label>توضیح / تارگت‌ها (کپشن):</label><textarea id="newNote" rows="3" placeholder="تحلیل یا اهداف قیمتی..."></textarea></div>
      <button class="btn btn-primary" id="btnSubmitSignal" onclick="Modals.submitNewSignal()">ثبت نهایی سیگنال</button>
    `;
    document.getElementById('modalOverlay').classList.add('show');
  },

  async handleImageUpload(input, targetHiddenId, statusElId) {
    const file = input.files[0];
    if (!file) return;

    const status = document.getElementById(statusElId);
    if (status) {
      status.textContent = '⏳ در حال آپلود و پردازش تصویر...';
      status.style.color = 'var(--gold)';
    }

    const formData = new FormData();
    formData.append('image', file);

    // استخراج توکن معتبر از سشن جاری یا لوکال استوریج
    const sess = App.state.session || {};
    let token = sess.token || localStorage.getItem('ml_token') || '';
    if (!token) {
      try {
        const stored = JSON.parse(localStorage.getItem('memeland_session') || '{}');
        token = stored.token || '';
      } catch (e) {}
    }

    try {
      const resp = await fetch('/site/upload', {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body: formData
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(`HTTP ${resp.status}: ${errJson.error || 'Upload error'}`);
      }

      const data = await resp.json();
      document.getElementById(targetHiddenId).value = data.url;
      if (status) {
        status.textContent = '✅ تصویر با موفقیت بارگذاری شد.';
        status.style.color = '#4ade80';
      }
      if (window.sendRemoteLog) window.sendRemoteLog('IMG_OK: ' + data.url.split('/').pop());
    } catch(err) {
      if (status) {
        status.textContent = '❌ خطا در آپلود تصویر';
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

  // ================= مدال افزودن مقاله و پست آموزشی جدید =================
  openAddArticleModal() {
    if (window.TGBridge) TGBridge.haptic('selection');
    document.getElementById('modalTitle').textContent = 'انتشار مقاله در آکادمی';
    document.getElementById('modalBody').innerHTML = `
      <div class="field">
        <label>عنوان مقاله:</label>
        <input id="articleTitle" placeholder="مثلاً روانشناسی ترید میم‌کوین‌ها...">
      </div>
      <div class="field">
        <label>عکس هدر و شاخص مقاله:</label>
        <input type="file" id="articlePhotoInput" accept="image/*" onchange="Modals.handleImageUpload(this, 'articleHeaderImg', 'articleUploadStatus')">
        <input type="hidden" id="articleHeaderImg">
        <div id="articleUploadStatus" style="font-size:10.5px; color:var(--text-muted); margin-top:4px;">فرمت‌های مجاز: JPG, PNG</div>
      </div>
      <div class="field">
        <label>متن کامل مقاله:</label>
        <textarea id="articleBody" rows="7" placeholder="محتوای آموزشی، نکات مدیریت سرمایه یا استراتژی..."></textarea>
      </div>
      <button class="btn btn-primary" id="btnSubmitArticle" onclick="Modals.submitNewArticle()">انتشار در آکادمی</button>
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

    // استفاده مستقیم از آبجکت API برای تضمین ارسال هدر معتبر Authorization
    const headers = (window.API && typeof API.getHeaders === 'function') 
      ? API.getHeaders() 
      : {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${App.state.session?.token || localStorage.getItem('ml_token') || ''}`
        };

    try {
      const resp = await fetch('/site/content/articles', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({ title, body, image })
      });

      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        if (window.sendRemoteLog) window.sendRemoteLog(`ART_PUB_ERR: HTTP ${resp.status} - ${d.error || 'unknown'}`);
        if (window.TGBridge) TGBridge.showAlert(d.error || 'خطا در ثبت مقاله');
        return;
      }

      if (window.TGBridge) TGBridge.haptic('success');
      if (window.sendRemoteLog) window.sendRemoteLog(`ART_PUB_OK: ${title.slice(0, 15)}`);
      
      this.closeModal();
      App.state.articles = [];
      await Views.renderAcademy();
    } catch (e) {
      if (window.sendRemoteLog) window.sendRemoteLog(`ART_PUB_CATCH: ${e.message}`);
      if (window.TGBridge) TGBridge.showAlert('خطا در برقراری ارتباط');
    }
  },

  async deleteArticleAction(articleId) {
    if (window.TGBridge) {
      const conf = await TGBridge.showConfirm('آیا از حذف این مقاله مطمئن هستید؟');
      if (!conf) return;
    }

    try {
      const resp = await fetch(`/site/content/articles/${articleId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('ml_token') || ''}`
        }
      });

      if (resp.ok) {
        if (window.TGBridge) TGBridge.haptic('success');
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