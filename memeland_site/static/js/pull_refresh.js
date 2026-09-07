/**
 * MemeLand Pull-to-Refresh & Live Polling Controller (Ultra-Smooth v5.5.0)
 */

const PullRefresh = {
  startY: 0,
  currentY: 0,
  isPulling: false,
  isRefreshing: false,
  maxPull: 90,
  triggerThreshold: 68,
  minDragRequired: 25, // حداقل کشش برای جلوگیری از رفرش با لمس خالی

  init(scrollableSelector, onRefreshCallback) {
    this.target = document.querySelector(scrollableSelector);
    this.callback = onRefreshCallback;
    if (!this.target) return;

    this.createIndicator();
    this.bindTouchEvents();
    this.startAutoPolling();
  },

  createIndicator() {
    if (document.getElementById('ptrIndicator')) return;
    const ptr = document.createElement('div');
    ptr.id = 'ptrIndicator';
    ptr.className = 'ptr-indicator';
    ptr.innerHTML = `
      <div class="ptr-frog-box" id="ptrFrogBox">
        <span class="ptr-frog-icon" id="ptrFrogIcon">🐸</span>
      </div>
      <div id="ptrText" class="ptr-status-text">بکشید تا پامپ‌ها رفرش شوند...</div>
    `;
    this.target.parentNode.insertBefore(ptr, this.target);
    this.indicator = ptr;
    this.frogBox = document.getElementById('ptrFrogBox');
    this.frogIcon = document.getElementById('ptrFrogIcon');
    this.textEl = document.getElementById('ptrText');
  },

  bindTouchEvents() {
    window.addEventListener('touchstart', (e) => {
      // فقط در بالاترین نقطه اسکرول صفحه و زمانی که رفرش در حال اجرا نیست
      if (window.scrollY <= 0 && !this.isRefreshing) {
        this.startY = e.touches[0].pageY;
        this.hasMovedPastMin = false;
        this.isPulling = false; // تا حرکت واقعی نکند فعال نمی‌شود
      }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
      if (this.isRefreshing || window.scrollY > 0) return;
      
      this.currentY = e.touches[0].pageY;
      const rawDistance = this.currentY - this.startY;

      // فیلتر لمس خالی: فقط در صورتی وارد فرآیند شود که کاربر بیشتر از ۲۵ پیکسل به پایین کشیده باشد
      if (rawDistance > this.minDragRequired) {
        this.isPulling = true;
        const dragDistance = rawDistance - this.minDragRequired;
        // فرمول لگاریتمی کشسانی برای نرم شدن انیمیشن
        const pullHeight = Math.min(dragDistance * 0.42, this.maxPull);

        this.indicator.style.height = `${pullHeight}px`;
        this.indicator.classList.add('pulling');

        // انیمیشن چرخش زاویه‌ای قورباغه با توجه به مسافت کشش
        const rotateDeg = Math.min(pullHeight * 4.5, 360);
        const scaleVal = 0.65 + (pullHeight / this.maxPull) * 0.45;
        this.frogBox.style.transform = `scale(${scaleVal}) rotate(${rotateDeg}deg)`;

        if (pullHeight >= this.triggerThreshold) {
          this.indicator.classList.add('active');
          this.textEl.textContent = 'رها کن تا راکت پرواز کنه! 🚀';
          if (!this._hapticTriggered) {
            TGBridge.haptic('selection');
            this._hapticTriggered = true;
          }
        } else {
          this.indicator.classList.remove('active');
          this.textEl.textContent = 'بکشید تا پامپ‌ها رفرش شوند...';
          this._hapticTriggered = false;
        }
      }
    }, { passive: true });

    window.addEventListener('touchend', async () => {
      if (!this.isPulling || this.isRefreshing) {
        this.reset();
        return;
      }
      this.isPulling = false;
      this.indicator.classList.remove('pulling');

      const rawDistance = this.currentY - this.startY;
      const dragDistance = Math.max(0, rawDistance - this.minDragRequired);
      const finalHeight = Math.min(dragDistance * 0.42, this.maxPull);

      if (finalHeight >= this.triggerThreshold) {
        await this.triggerRefresh();
      } else {
        this.reset();
      }
    });
  },

  async triggerRefresh() {
    this.isRefreshing = true;
    this.indicator.style.height = '68px';
    this.indicator.classList.add('refreshing');
    this.frogBox.style.transform = 'scale(1)';
    this.textEl.textContent = 'در حال اسکن پامپ‌های جدید...';
    TGBridge.haptic('medium');

    try {
      if (this.callback) await this.callback();
      TGBridge.haptic('success');
      this.textEl.textContent = 'کال‌ها آپدیت شدند! ✨';
    } catch (e) {
      TGBridge.haptic('error');
      this.textEl.textContent = 'خطا در برقراری ارتباط';
    }

    setTimeout(() => this.reset(), 500);
  },

  reset() {
    this.indicator.style.height = '0';
    this.indicator.classList.remove('active', 'refreshing', 'pulling');
    if (this.frogBox) this.frogBox.style.transform = 'scale(0.65) rotate(0deg)';
    this._hapticTriggered = false;
    this.isPulling = false;
    setTimeout(() => {
      this.isRefreshing = false;
      if (this.textEl) this.textEl.textContent = 'بکشید تا پامپ‌ها رفرش شوند...';
    }, 300);
  },

  startAutoPolling() {
    setInterval(async () => {
      if (document.visibilityState === 'visible' && !this.isRefreshing) {
        if (this.callback) await this.callback(true);
      }
    }, 45000);
  }
};