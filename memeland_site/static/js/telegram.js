/**
 * Telegram WebApp Native Integration Bridge
 */
const TGBridge = {
  tg: window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null,

  init() {
    if (!this.tg) return;

    this.tg.ready();
    this.tg.expand();

    // جلوگیری از بسته‌شدن برنامه با اسکرول عمودی (Bot API 7.7+)
    if (this.tg.disableVerticalSwipes) {
      try { this.tg.disableVerticalSwipes(); } catch (e) {}
    }

    // هماهنگ‌سازی رنگ هدر و پس‌زمینه
    if (this.tg.setHeaderColor) {
      try { this.tg.setHeaderColor('#07090e'); } catch (e) {}
    }
    if (this.tg.setBackgroundColor) {
      try { this.tg.setBackgroundColor('#07090e'); } catch (e) {}
    }

    // رویداد دکمه برگشت بومی تلگرام
    if (this.tg.BackButton) {
      this.tg.BackButton.onClick(() => {
        if (document.getElementById('bottomSheet').classList.contains('show')) {
          App.closeBottomSheet();
        } else if (App.state.currentTab !== 'signals') {
          App.switchTab('signals');
        }
      });
    }
  },

  haptic(type = 'light') {
    if (!this.tg || !this.tg.HapticFeedback) return;
    try {
      if (['success', 'error', 'warning'].includes(type)) {
        this.tg.HapticFeedback.notificationOccurred(type);
      } else if (type === 'selection') {
        this.tg.HapticFeedback.selectionChanged();
      } else {
        this.tg.HapticFeedback.impactOccurred(type);
      }
    } catch (e) {}
  },

  syncBackButton(shouldShow) {
    if (!this.tg || !this.tg.BackButton) return;
    if (shouldShow) {
      this.tg.BackButton.show();
    } else {
      this.tg.BackButton.hide();
    }
  },

  showAlert(message) {
    if (this.tg && this.tg.showAlert) {
      this.tg.showAlert(message);
    } else {
      alert(message);
    }
  },

  showConfirm(message) {
    return new Promise((resolve) => {
      if (this.tg && this.tg.showConfirm) {
        this.tg.showConfirm(message, (ok) => resolve(!!ok));
      } else {
        resolve(confirm(message));
      }
    });
  },

  copyText(text, successMsg = 'کپی شد!') {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        this.haptic('success');
        this.showAlert(successMsg);
      });
    }
  }
};