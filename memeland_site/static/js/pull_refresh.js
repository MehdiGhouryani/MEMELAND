/**
 * MemeLand Robust Pull-to-Refresh (v6.0.0)
 */

const PullRefresh = {
  startY: 0,
  currentY: 0,
  isPulling: false,
  isRefreshing: false,
  triggerThreshold: 65,

  init(containerSelector, onRefresh) {
    const el = document.querySelector(containerSelector);
    if (!el) {
      if (window.sendRemoteLog) window.sendRemoteLog('PTR_ERR: Container not found ' + containerSelector);
      return;
    }
    this.target = el;
    this.callback = onRefresh;

    // ایجاد نشانگر بالای فید سیگنال‌ها
    let ptr = document.getElementById('ptrIndicator');
    if (!ptr) {
      ptr = document.createElement('div');
      ptr.id = 'ptrIndicator';
      ptr.className = 'ptr-indicator';
      ptr.style.cssText = 'height: 0px; overflow: hidden; display: flex; flex-direction: column; align-items: center; justify-content: center; transition: height 0.2s cubic-bezier(0.2, 0.8, 0.2, 1);';
      ptr.innerHTML = `
        <div id="ptrFrogBox" style="font-size: 26px; transform: scale(0.8); transition: transform 0.15s ease;">🐸</div>
        <div id="ptrText" style="font-size: 11px; color: #a1a1aa; margin-top: 4px; font-weight: 500;">بکشید تا رفرش شود...</div>
      `;
      el.parentNode.insertBefore(ptr, el);
    }
    this.indicator = ptr;
    this.textEl = document.getElementById('ptrText');
    this.frogBox = document.getElementById('ptrFrogBox');

    // لیسنرهای لمسی مستقیم روی خود المنت و بدنه آن
    const bindTarget = document.querySelector('.app-main') || el;

    bindTarget.addEventListener('touchstart', (e) => {
      // فقط در صورتی که بالای صفحه باشیم
      if ((window.scrollY <= 0 && bindTarget.scrollTop <= 0) && !this.isRefreshing) {
        this.startY = e.touches[0].pageY;
        this.isPulling = true;
      }
    }, { passive: true });

    bindTarget.addEventListener('touchmove', (e) => {
      if (!this.isPulling || this.isRefreshing) return;
      this.currentY = e.touches[0].pageY;
      const diff = this.currentY - this.startY;

      if (diff > 12 && (window.scrollY <= 0 && bindTarget.scrollTop <= 0)) {
        // جلوگیری از تداخل سوایپ بسته شدن مینی‌اپ تلگرام
        if (e.cancelable) e.preventDefault();

        const height = Math.min(diff * 0.45, 90);
        this.indicator.style.transition = 'none';
        this.indicator.style.height = `${height}px`;

        const rotate = Math.min(height * 4, 360);
        this.frogBox.style.transform = `scale(${0.75 + (height / 90) * 0.4}) rotate(${rotate}deg)`;

        if (height >= this.triggerThreshold) {
          this.textEl.textContent = 'رها کنید تا اسکن شود! 🚀';
          this.textEl.style.color = '#4ade80';
          if (!this._haptic) {
            if (window.TGBridge) TGBridge.haptic('selection');
            this._haptic = true;
          }
        } else {
          this.textEl.textContent = 'بکشید تا رفرش شود...';
          this.textEl.style.color = '#a1a1aa';
          this._haptic = false;
        }
      }
    }, { passive: false });

    bindTarget.addEventListener('touchend', async () => {
      if (!this.isPulling || this.isRefreshing) return;
      this.isPulling = false;
      this.indicator.style.transition = 'height 0.25s ease';

      const diff = this.currentY - this.startY;
      const height = Math.min(diff * 0.45, 90);

      if (height >= this.triggerThreshold) {
        this.isRefreshing = true;
        this.indicator.style.height = '60px';
        this.textEl.textContent = 'در حال اسکن پامپ‌های جدید...';
        if (window.TGBridge) TGBridge.haptic('medium');

        if (window.sendRemoteLog) window.sendRemoteLog('PTR: Refresh Executed');

        try {
          if (this.callback) await this.callback();
          this.textEl.textContent = 'کال‌ها بروز شدند! ✨';
        } catch (err) {
          this.textEl.textContent = 'خطا در ارتباط';
          if (window.sendRemoteLog) window.sendRemoteLog('PTR_ERR: ' + err);
        }

        setTimeout(() => {
          this.indicator.style.height = '0px';
          this.frogBox.style.transform = 'scale(0.8) rotate(0deg)';
          this.isRefreshing = false;
        }, 450);
      } else {
        this.indicator.style.height = '0px';
        this.frogBox.style.transform = 'scale(0.8) rotate(0deg)';
      }
    });

    if (window.sendRemoteLog) window.sendRemoteLog('PTR_INIT: Ready on ' + containerSelector);
  }
};