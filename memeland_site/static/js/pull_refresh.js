/**
 * MemeLand Fluid Pull-to-Refresh & Optimized Logging (v7.0.0)
 */
(function() {
  const PullRefresh = {
    startY: 0,
    currentY: 0,
    isPulling: false,
    isRefreshing: false,
    triggerThreshold: 56,

    init(containerSelector, onRefresh) {
      const el = document.querySelector(containerSelector);
      if (!el) return;

      this.callback = onRefresh;

      let ptr = document.getElementById('ptrIndicator');
      if (!ptr) {
        ptr = document.createElement('div');
        ptr.id = 'ptrIndicator';
        ptr.className = 'ptr-indicator';
        ptr.innerHTML = `
          <div id="ptrFrogBox" class="ptr-frog-box">
            <span id="ptrFrogIcon" class="ptr-frog-icon">🐸</span>
          </div>
          <div id="ptrText" class="ptr-status-text">بکشید برای به‌روزرسانی...</div>
        `;
        el.parentNode.insertBefore(ptr, el);
      }

      this.indicator = ptr;
      this.textEl = document.getElementById('ptrText');
      this.frogBox = document.getElementById('ptrFrogBox');
      this.frogIcon = document.getElementById('ptrFrogIcon');

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

        if (diff > 4 && getScrollTop() <= 0) {
          if (e.cancelable) {
            e.preventDefault();
          }

          // Dynamic dampening physics
          const height = Math.min(diff * 0.38, 76);
          this.indicator.classList.add('pulling');
          this.indicator.style.height = `${height}px`;

          const progress = Math.min(height / this.triggerThreshold, 1);
          const rotate = progress * 240;
          this.frogIcon.style.transform = `rotate(${rotate}deg)`;

          if (height >= this.triggerThreshold) {
            this.indicator.classList.add('active');
            this.textEl.textContent = 'رها کنید...';
            this.textEl.style.color = 'var(--accent-light, #818cf8)';
          } else {
            this.indicator.classList.remove('active');
            this.textEl.textContent = 'بکشید برای به‌روزرسانی...';
            this.textEl.style.color = 'var(--text-muted, #8a93a6)';
          }
        }
      }, { passive: false });

      const resetIndicator = () => {
        this.indicator.classList.remove('pulling', 'active', 'refreshing');
        this.indicator.style.transition = 'height 0.28s cubic-bezier(0.16, 1, 0.3, 1)';
        this.indicator.style.height = '0px';
        this.frogIcon.style.transform = 'rotate(0deg)';
      };

      const handleRelease = async () => {
        if (!this.isPulling || this.isRefreshing) return;
        this.isPulling = false;

        const diff = this.currentY - this.startY;
        const height = Math.min(diff * 0.38, 76);

        if (height >= this.triggerThreshold && getScrollTop() <= 0) {
          this.isRefreshing = true;
          this.indicator.classList.add('refreshing');
          this.indicator.classList.remove('pulling');
          this.indicator.style.transition = 'height 0.2s ease';
          this.indicator.style.height = '52px';
          this.textEl.textContent = 'در حال دریافت داده‌های زنده...';

          // Native Telegram Haptic impact
          if (window.Telegram?.WebApp?.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
          } else if (window.TGBridge?.haptic) {
            TGBridge.haptic('medium');
          }

          try {
            if (this.callback) await this.callback();
            this.textEl.textContent = 'به‌روز شد ✓';
            this.textEl.style.color = 'var(--green, #10b981)';
          } catch (err) {
            this.textEl.textContent = 'خطا در ارتباط';
            this.textEl.style.color = 'var(--red, #f43f5e)';
            // Only send error logs to prevent server log inflation
            if (window.sendRemoteLog) {
              window.sendRemoteLog('PTR_ERR: ' + (err.message || err));
            }
          }

          setTimeout(() => {
            resetIndicator();
            this.isRefreshing = false;
          }, 450);
        } else {
          resetIndicator();
        }
      };

      document.addEventListener('touchend', handleRelease);
      document.addEventListener('touchcancel', () => {
        this.isPulling = false;
        resetIndicator();
      });
    }
  };

  window.PullRefresh = PullRefresh;
})();