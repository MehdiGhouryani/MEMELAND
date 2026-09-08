/**
 * Telegram WebApp Native Integration Bridge (v7.0.0 - Native Control Dock & Gestures Lock)
 */

const TGBridge = {
  _mainActionCallback: null,
  _secondaryActionCallback: null,

  get tg() {
    return window.Telegram?.WebApp || null;
  },

  init() {
    const tg = this.tg;
    if (!tg) return;

    try {
      tg.ready();
      tg.expand();
    } catch (e) {}

    // ۱. مهار ژست مزاحم بسته شدن پنجره با سوایپ عمودی (Bot API 7.7+)
    if (tg.disableVerticalSwipes) {
      try {
        tg.disableVerticalSwipes();
      } catch (e) {}
    }

    // ۲. هماهنگ‌سازی رنگ‌های هدر، پس‌زمینه و نوار پایین بر اساس تم جدید
    const darkBg = '#090a0f';
    try {
      if (tg.setHeaderColor) tg.setHeaderColor(darkBg);
      if (tg.setBackgroundColor) tg.setBackgroundColor(darkBg);
      if (tg.setBottomBarColor) tg.setBottomBarColor(darkBg);
    } catch (e) {}

    // ۳. مدیریت جامع و یکپارچه دکمه بازگشت (BackButton)
    if (tg.BackButton) {
      tg.BackButton.onClick(() => {
        // بستن مودال‌های پاپ‌آپ
        const modal = document.getElementById('modalOverlay');
        if (modal && modal.classList.contains('show')) {
          if (window.Modals && typeof Modals.closeModal === 'function') {
            Modals.closeModal();
          }
          return;
        }

        // بستن شیت کشویی جزئیات
        const sheet = document.getElementById('bottomSheet');
        if (sheet && sheet.classList.contains('show')) {
          if (window.Views && typeof Views.closeBottomSheet === 'function') {
            Views.closeBottomSheet();
          }
          return;
        }

        // بازگشت به تب سیگنال‌ها در صورت حضور در سایر تب‌ها
        if (window.App && App.state && App.state.currentTab !== 'signals') {
          App.switchTab('signals');
        }
      });
    }
  },

  // ================= داک کنترلی بومی (Native Dock: Main & Secondary Buttons) =================

  showDockActions({ mainText, onMainClick, secondaryText, onSecondaryClick }) {
    const tg = this.tg;
    if (!tg) return;

    // پیکربندی و اتصال MainButton
    if (tg.MainButton && mainText && typeof onMainClick === 'function') {
      if (this._mainActionCallback) {
        tg.MainButton.offClick(this._mainActionCallback);
      }
      this._mainActionCallback = () => {
        this.haptic('selection');
        onMainClick();
      };

      tg.MainButton.setParams({
        text: mainText,
        color: '#6366f1',
        text_color: '#ffffff',
        is_active: true,
        is_visible: true
      });
      tg.MainButton.onClick(this._mainActionCallback);
      tg.MainButton.show();
    } else if (tg.MainButton) {
      tg.MainButton.hide();
    }

    // پیکربندی و اتصال SecondaryButton (Bot API 7.10+)
    if (tg.SecondaryButton && secondaryText && typeof onSecondaryClick === 'function') {
      if (this._secondaryActionCallback) {
        tg.SecondaryButton.offClick(this._secondaryActionCallback);
      }
      this._secondaryActionCallback = () => {
        this.haptic('light');
        onSecondaryClick();
      };

      tg.SecondaryButton.setParams({
        text: secondaryText,
        color: '#161b26',
        text_color: '#818cf8',
        is_active: true,
        is_visible: true
      });
      tg.SecondaryButton.onClick(this._secondaryActionCallback);
      tg.SecondaryButton.show();
    } else if (tg.SecondaryButton) {
      tg.SecondaryButton.hide();
    }
  },

  hideDockActions() {
    const tg = this.tg;
    if (!tg) return;

    if (tg.MainButton) {
      if (this._mainActionCallback) {
        tg.MainButton.offClick(this._mainActionCallback);
        this._mainActionCallback = null;
      }
      tg.MainButton.hide();
    }

    if (tg.SecondaryButton) {
      if (this._secondaryActionCallback) {
        tg.SecondaryButton.offClick(this._secondaryActionCallback);
        this._secondaryActionCallback = null;
      }
      tg.SecondaryButton.hide();
    }
  },

  // باز کردن امن لینک‌های بیرونی در تلگرام
  openLink(url) {
    if (!url) return;
    const tg = this.tg;
    if (tg && tg.openLink) {
      tg.openLink(url);
    } else {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  },

  // ================= بازخورد لمسی (Haptic) =================
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
        tg.showConfirm(message, (ok) => resolve(Boolean(ok)));
      } else {
        resolve(confirm(message));
      }
    });
  },

  copyText(text, successMsg = 'کپی شد ✓') {
    if (!text) return;
    
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