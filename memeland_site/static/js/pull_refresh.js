/**
 * MemeLand Pull-to-Refresh & Live Polling Controller
 */

const PullRefresh = {
  startY: 0,
  currentY: 0,
  isPulling: false,
  isRefreshing: false,
  maxPull: 85,
  triggerThreshold: 65,

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
      <div class="ptr-frog-box">
        <span class="ptr-frog-icon">🐸</span>
      </div>
      <div id="ptrText" class="ptr-status-text">بکشید تا پامپ‌ها رفرش شوند...</div>
    `;
    this.target.parentNode.insertBefore(ptr, this.target);
    this.indicator = ptr;
    this.textEl = document.getElementById('ptrText');
  },

  bindTouchEvents() {
    window.addEventListener('touchstart', (e) => {
      // فقط زمانی که اسکرول صفحه در بالاترین نقطه است فعال شود
      if (window.scrollY === 0 && !this.isRefreshing) {
        this.startY = e.touches[0].pageY;
        this.isPulling = true;
      }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
      if (!this.isPulling || this.isRefreshing) return;
      this.currentY = e.touches[0].pageY;
      const distance = this.currentY - this.startY;

      if (distance > 0 && window.scrollY === 0) {
        // اعمال مقاومت کشسانی (Rubber-banding)
        const pullHeight = Math.min(distance * 0.45, this.maxPull);
        this.indicator.style.height = `${pullHeight}px`;
        this.indicator.classList.add('pulling');

        if (pullHeight >= this.triggerThreshold) {
          this.indicator.classList.add('active');
          this.textEl.textContent = 'رها کنید تا اسکن شود! 🚀';
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
      if (!this.isPulling) return;
      this.isPulling = false;
      this.indicator.classList.remove('pulling');

      const distance = this.currentY - this.startY;
      const finalHeight = Math.min(distance * 0.45, this.maxPull);

      if (finalHeight >= this.triggerThreshold && !this.isRefreshing) {
        await this.triggerRefresh();
      } else {
        this.reset();
      }
    });
  },

  async triggerRefresh() {
    this.isRefreshing = true;
    this.indicator.style.height = '60px';
    this.indicator.classList.add('refreshing');
    this.textEl.textContent = 'در حال دریافت کال‌های زنده...';
    TGBridge.haptic('light');

    try {
      if (this.callback) await this.callback();
      TGBridge.haptic('success');
      this.textEl.textContent = 'بروزرسانی شد! ✅';
    } catch (e) {
      TGBridge.haptic('error');
      this.textEl.textContent = 'خطا در ارتباط';
    }

    setTimeout(() => this.reset(), 450);
  },

  reset() {
    this.indicator.style.height = '0';
    this.indicator.classList.remove('active', 'refreshing', 'pulling');
    this._hapticTriggered = false;
    setTimeout(() => {
      this.isRefreshing = false;
      this.textEl.textContent = 'بکشید تا پامپ‌ها رفرش شوند...';
    }, 250);
  },

  // پولینگ خودکار هر ۴۵ ثانیه در پس‌زمینه
  startAutoPolling() {
    setInterval(async () => {
      if (document.visibilityState === 'visible' && !this.isRefreshing) {
        if (this.callback) await this.callback(true); // لود سایلنت
      }
    }, 45000);
  }
};