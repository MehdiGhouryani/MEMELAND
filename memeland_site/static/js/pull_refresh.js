/**
 * MemeLand Robust Pull-to-Refresh (v5.9.0)
 */

const PullRefresh = {
  startY: 0,
  currentY: 0,
  isPulling: false,
  isRefreshing: false,
  triggerThreshold: 60,

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
        <div class="ptr-frog-box" id="ptrFrogBox" style="font-size:24px; transition:transform 0.15s ease;">🐸</div>
        <div id="ptrText" class="ptr-status-text" style="font-size:10.5px; color:var(--text-muted); margin-top:4px;">بکشید تا رفرش شود...</div>
      `;
      el.parentNode.insertBefore(ptr, el);
    }
    this.indicator = ptr;
    this.textEl = document.getElementById('ptrText');
    this.frogBox = document.getElementById('ptrFrogBox');

    // لیسنر مستقیم روی سند جهت دریافت سریع لمس در وب‌ویوی تلگرام
    window.addEventListener('touchstart', (e) => {
      if ((window.scrollY <= 0 || document.documentElement.scrollTop <= 0) && !this.isRefreshing) {
        this.startY = e.touches[0].clientY;
        this.isPulling = true;
      }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
      if (!this.isPulling || this.isRefreshing) return;
      this.currentY = e.touches[0].clientY;
      const diff = this.currentY - this.startY;

      if (diff > 10 && (window.scrollY <= 0 || document.documentElement.scrollTop <= 0)) {
        const height = Math.min(diff * 0.42, 85);
        this.indicator.style.height = `${height}px`;
        this.indicator.classList.add('pulling');

        const rotate = Math.min(height * 4, 360);
        this.frogBox.style.transform = `scale(${0.7 + (height / 85) * 0.4}) rotate(${rotate}deg)`;

        if (height >= this.triggerThreshold) {
          this.textEl.textContent = 'رها کن تا رفرش بشه! 🚀';
        } else {
          this.textEl.textContent = 'بکشید تا رفرش شود...';
        }
      }
    }, { passive: true });

    window.addEventListener('touchend', async () => {
      if (!this.isPulling || this.isRefreshing) return;
      this.isPulling = false;
      this.indicator.classList.remove('pulling');

      const diff = this.currentY - this.startY;
      const height = Math.min(diff * 0.42, 85);

      if (height >= this.triggerThreshold) {
        this.isRefreshing = true;
        this.indicator.style.height = '58px';
        this.textEl.textContent = 'در حال اسکن سیگنال‌ها...';
        if (window.TGBridge) TGBridge.haptic('medium');

        if (window.sendRemoteLog) window.sendRemoteLog('PTR: Triggered');

        try {
          if (this.callback) await this.callback();
          this.textEl.textContent = 'بروز شد! ✅';
        } catch (e) {
          this.textEl.textContent = 'خطا در ارتباط';
        }

        setTimeout(() => {
          this.indicator.style.height = '0';
          this.frogBox.style.transform = 'scale(0.7) rotate(0deg)';
          this.isRefreshing = false;
        }, 400);
      } else {
        this.indicator.style.height = '0';
        this.frogBox.style.transform = 'scale(0.7) rotate(0deg)';
      }
    });
  }
};