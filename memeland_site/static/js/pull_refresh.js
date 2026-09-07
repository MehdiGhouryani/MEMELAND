/**
 * MemeLand Robust Pull-to-Refresh (v6.2.0)
 */
(function() {
  const PullRefresh = {
    startY: 0,
    currentY: 0,
    isPulling: false,
    isRefreshing: false,
    triggerThreshold: 60,

    init(containerSelector, onRefresh) {
      const el = document.querySelector(containerSelector);
      if (!el) {
        if (window.sendRemoteLog) window.sendRemoteLog('PTR_INIT: Container not found ' + containerSelector);
        return;
      }
      this.callback = onRefresh;

      let ptr = document.getElementById('ptrIndicator');
      if (!ptr) {
        ptr = document.createElement('div');
        ptr.id = 'ptrIndicator';
        ptr.className = 'ptr-indicator';
        ptr.style.cssText = 'height: 0px; overflow: hidden; display: flex; flex-direction: column; align-items: center; justify-content: center; pointer-events: none; will-change: height;';
        ptr.innerHTML = `
          <div id="ptrFrogBox" style="font-size: 26px; transform: scale(0.7); transition: transform 0.1s ease;">🐸</div>
          <div id="ptrText" style="font-size: 11px; color: #a1a1aa; margin-top: 3px; font-weight: 500;">بکشید تا رفرش شود...</div>
        `;
        el.parentNode.insertBefore(ptr, el);
      }
      this.indicator = ptr;
      this.textEl = document.getElementById('ptrText');
      this.frogBox = document.getElementById('ptrFrogBox');

      const getScrollTop = () => {
        return window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;
      };

      document.addEventListener('touchstart', (e) => {
        if (getScrollTop() <= 0 && !this.isRefreshing) {
          this.startY = e.touches[0].pageY;
          this.isPulling = true;
        }
      }, { passive: true });

      document.addEventListener('touchmove', (e) => {
        if (!this.isPulling || this.isRefreshing) return;
        this.currentY = e.touches[0].pageY;
        const diff = this.currentY - this.startY;

        if (diff > 5 && getScrollTop() <= 0) {
          if (e.cancelable) {
            e.preventDefault();
          }

          const height = Math.min(diff * 0.4, 80);
          this.indicator.style.transition = 'none';
          this.indicator.style.height = `${height}px`;

          const rotate = Math.min(height * 4.5, 360);
          this.frogBox.style.transform = `scale(${0.7 + (height / 80) * 0.4}) rotate(${rotate}deg)`;

          if (height >= this.triggerThreshold) {
            this.textEl.textContent = 'رها کن تا رفرش بشه! 🚀';
            this.textEl.style.color = '#4ade80';
          } else {
            this.textEl.textContent = 'بکشید تا رفرش شود...';
            this.textEl.style.color = '#a1a1aa';
          }
        }
      }, { passive: false });

      const resetIndicator = () => {
        this.indicator.style.transition = 'height 0.25s ease';
        this.indicator.style.height = '0px';
        this.frogBox.style.transform = 'scale(0.7) rotate(0deg)';
      };

      const handleRelease = async () => {
        if (!this.isPulling || this.isRefreshing) return;
        this.isPulling = false;

        const diff = this.currentY - this.startY;
        const height = Math.min(diff * 0.4, 80);

        if (height >= this.triggerThreshold && getScrollTop() <= 0) {
          this.isRefreshing = true;
          this.indicator.style.transition = 'height 0.2s ease';
          this.indicator.style.height = '52px';
          this.textEl.textContent = 'در حال اسکن سیگنال‌ها...';
          if (window.TGBridge) TGBridge.haptic('medium');
          if (window.sendRemoteLog) window.sendRemoteLog('PTR: Triggered');

          try {
            if (this.callback) await this.callback();
            this.textEl.textContent = 'بروز شد! ✅';
          } catch (err) {
            this.textEl.textContent = 'خطا در ارتباط';
            if (window.sendRemoteLog) window.sendRemoteLog('PTR_ERR: ' + err);
          }

          setTimeout(() => {
            resetIndicator();
            this.isRefreshing = false;
          }, 400);
        } else {
          resetIndicator();
        }
      };

      document.addEventListener('touchend', handleRelease);
      document.addEventListener('touchcancel', () => {
        this.isPulling = false;
        resetIndicator();
      });

      if (window.sendRemoteLog) window.sendRemoteLog('PTR_INIT: Success');
    }
  };

  window.PullRefresh = PullRefresh;
})();