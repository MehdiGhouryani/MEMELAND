/**
 * Telegram WebApp Native Integration Bridge
 * نسخه اصلاح‌شده با Getter پویا، فال‌بک کلیپ‌بورد و مهار کامل دکمه بازگشت
 */

const TGBridge = {
  // دسترسی پویا به SDK حتی در صورت تاخیر در بارگذاری اولیه
  get tg() {
    return window.Telegram?.WebApp || null;
  },

  init() {
    const tg = this.tg;
    if (!tg) return;

    tg.ready();
    tg.expand();

    // مهار بسته‌شدن برنامه حین اسکرول عمودی (Bot API 7.7+)
    if (tg.disableVerticalSwipes) {
      try { tg.disableVerticalSwipes(); } catch (e) {}
    }

    // هماهنگ‌سازی رنگ هدر و پس‌زمینه
    if (tg.setHeaderColor) {
      try { tg.setHeaderColor('#07090e'); } catch (e) {}
    }
    if (tg.setBackgroundColor) {
      try { tg.setBackgroundColor('#07090e'); } catch (e) {}
    }

    // مدیریت جامع دکمه بازگشت تلگرام (مودال ⟵ باتم‌شیت ⟵ تب‌ها)
    if (tg.BackButton) {
      tg.BackButton.onClick(() => {
        const modal = document.getElementById('modalOverlay');
        if (modal && modal.classList.contains('show')) {
          App.closeModal();
          return;
        }

        const sheet = document.getElementById('bottomSheet');
        if (sheet && sheet.classList.contains('show')) {
          App.closeBottomSheet();
          return;
        }

        if (App.state && App.state.currentTab !== 'signals') {
          App.switchTab('signals');
        }
      });
    }
  },

  haptic(type = 'light') {
    const tg = this.tg;
    if (!tg || !tg.HapticFeedback) return;
    try {
      if (['success', 'error', 'warning'].includes(type)) {
        tg.HapticFeedback.notificationOccurred(type);
      } else if (type === 'selection') {
        tg.HapticFeedback.selectionChanged();
      } else {
        tg.HapticFeedback.impactOccurred(type);
      }
    } catch (e) {}
  },

  syncBackButton(shouldShow) {
    const tg = this.tg;
    if (!tg || !tg.BackButton) return;
    if (shouldShow) {
      tg.BackButton.show();
    } else {
      tg.BackButton.hide();
    }
  },

  showAlert(message) {
    const tg = this.tg;
    if (tg && tg.showAlert) {
      tg.showAlert(message);
    } else {
      alert(message);
    }
  },

  showConfirm(message) {
    return new Promise((resolve) => {
      const tg = this.tg;
      if (tg && tg.showConfirm) {
        tg.showConfirm(message, (ok) => resolve(!!ok));
      } else {
        resolve(confirm(message));
      }
    });
  },

  copyText(text, successMsg = 'کپی شد!') {
    if (!text) return;
    
    // روش استاندارد با فال‌بک متنی برای مرورگرهای قدیمی وب‌ویو
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text)
        .then(() => {
          this.haptic('success');
          this.showAlert(successMsg);
        })
        .catch(() => this._fallbackCopy(text, successMsg));
    } else {
      this._fallbackCopy(text, successMsg);
    }
  },

  _fallbackCopy(text, successMsg) {
    try {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-9999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      this.haptic('success');
      this.showAlert(successMsg);
    } catch (err) {
      this.showAlert('کپی ناموفق بود.');
    }
  }
};