/**
 * MemeLand Client Logger (v8.0.0)
 *
 * چرا این فایل جدا شد:
 *   قبلاً منطق لاگ به‌صورت inline توی index.html بود + یه نسخه‌ی fallback
 *   تکراری توی api.js. نتیجه: دو تعریف موازی، رفتار متفاوت، و هر خط لاگ
 *   یه درخواست fetch جدا (۱۴ درخواست تو ۴۰ ثانیه فقط برای loadSignalsOK).
 *
 * چیزی که عوض شد:
 *   ۱. سطح‌بندی (E/W/I/D) — سرور هر سطح رو با levelname درست ثبت می‌کنه،
 *      پس `/logs err` واقعاً فقط خطاها رو می‌ده.
 *   ۲. Batching — رویدادها تو صف جمع می‌شن و هر ۲.۵ ثانیه (یا ۸ رویداد،
 *      یا فوراً برای خطا) تو یک POST فرستاده می‌شن. sid/build یک‌بار در هر
 *      batch میاد نه در هر خط ⇒ حجم لاگ حدود نصف.
 *   ۳. Throttle با flush زمان‌دار — اگه یه رویداد تکراری سرکوب بشه، شمارشش
 *      با یه تایمر بالاخره خالی می‌شه (repeated=N). قبلاً اگه رویداد دیگه
 *      تکرار نمی‌شد، تعداد سرکوب‌شده‌ها برای همیشه گم می‌شد.
 *   ۴. Ring buffer محلی — MHLog.tail() آخرین ۲۰۰ رویداد رو بدون نیاز به
 *      سرور برمی‌گردونه (برای دیباگ روی دستگاه خود کاربر).
 *   ۵. flush با sendBeacon موقع بسته‌شدن صفحه — لاگ لحظه‌ی کرش/خروج دیگه
 *      گم نمی‌شه (قبلاً fetch در حال پرواز کنسل می‌شد).
 */
(function () {
  'use strict';

  var BUILD = window.__MH_BUILD || 'dev';
  var SID = window.__MH_SID || Math.random().toString(36).slice(2, 8);
  window.__MH_BUILD = BUILD;
  window.__MH_SID = SID;

  var ENDPOINT = '/site/client-log';
  var FLUSH_MS = 2500;
  var FLUSH_AT = 8;
  var MAX_QUEUE = 60;      // سقف صف؛ از انفجار حافظه موقع قطعی شبکه جلوگیری می‌کنه
  var RING_MAX = 200;
  var KV_MAX_LEN = 240;    // سقف طول مقدار هر کلید، قبل از ارسال

  var queue = [];
  var ring = [];
  var flushTimer = null;
  var lastSeen = {};       // key -> { kvStr, time, suppressed, tag, ev, lv }
  var tailTimer = null;

  function clip(v) {
    if (v === undefined || v === null || v === '') return 'none';
    var s = String(v);
    return s.length > KV_MAX_LEN ? s.slice(0, KV_MAX_LEN) + '…' : s;
  }

  function fmtKv(kv) {
    if (!kv) return '';
    var parts = [];
    for (var k in kv) {
      if (Object.prototype.hasOwnProperty.call(kv, k)) {
        parts.push(k + '=' + clip(kv[k]));
      }
    }
    return parts.join(' ');
  }

  function push(level, tag, event, kv) {
    var line = '[' + tag + '] ' + event;
    var kvs = fmtKv(kv);
    if (kvs) line += ' ' + kvs;

    ring.push({ t: Date.now(), lv: level, line: line });
    if (ring.length > RING_MAX) ring.shift();

    queue.push({ lv: level, msg: line });
    if (queue.length > MAX_QUEUE) queue.splice(0, queue.length - MAX_QUEUE);

    if (level === 'E' || queue.length >= FLUSH_AT) {
      flush();
    } else if (!flushTimer) {
      flushTimer = setTimeout(flush, FLUSH_MS);
    }
  }

  function flush(useBeacon) {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
    if (!queue.length) return;

    var batch = { sid: SID, build: BUILD, events: queue };
    queue = [];

    var body = JSON.stringify(batch);
    try {
      if (useBeacon && navigator.sendBeacon) {
        navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }));
        return;
      }
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body,
        keepalive: true
      }).catch(function () {});
    } catch (e) { /* لاگ‌کردن هیچ‌وقت نباید خودش اپ رو بترکونه */ }
  }

  // ---- API عمومی -------------------------------------------------------

  var MHLog = {
    sid: SID,
    build: BUILD,

    event: function (tag, event, kv, level) {
      push(level || 'I', tag, event, kv);
    },

    error: function (tag, event, kv) { push('E', tag, event, kv); },
    warn:  function (tag, event, kv) { push('W', tag, event, kv); },
    info:  function (tag, event, kv) { push('I', tag, event, kv); },
    debug: function (tag, event, kv) { push('D', tag, event, kv); },

    /**
     * برای رویدادهای پرتکرار. اگه دقیقاً همون رویداد با همون مقادیر تو
     * بازه‌ی minIntervalMs دوباره بیاد، فرستاده نمی‌شه — فقط شمرده می‌شه.
     * وقتی بالاخره یه خط فرستاده بشه (چه به‌خاطر تغییر مقدار، چه با
     * تایمر flush)، تعداد سرکوب‌شده به‌شکل repeated=N میاد.
     */
    throttled: function (tag, event, kv, minIntervalMs, level) {
      var key = tag + ':' + event;
      var kvStr = JSON.stringify(kv || {});
      var now = Date.now();
      var interval = minIntervalMs || 30000;
      var last = lastSeen[key];

      if (last && last.kvStr === kvStr && (now - last.time) < interval) {
        last.suppressed += 1;
        scheduleTailFlush(interval);
        return;
      }

      var out = kv || {};
      if (last && last.suppressed > 0) {
        out = Object.assign({}, out, { repeated: last.suppressed });
      }
      lastSeen[key] = { kvStr: kvStr, time: now, suppressed: 0, tag: tag, ev: event, lv: level || 'I' };
      push(level || 'I', tag, event, out);
    },

    /** آخرین N رویداد، محلی روی همین دستگاه (بدون نیاز به سرور). */
    tail: function (n) {
      return ring.slice(-(n || 40)).map(function (r) {
        return new Date(r.t).toISOString().slice(11, 19) + ' [' + r.lv + '] ' + r.line;
      });
    },

    flush: flush
  };

  // خالی‌کردن شمارنده‌های سرکوب‌شده، حتی اگه رویداد دیگه تکرار نشه.
  function scheduleTailFlush(interval) {
    if (tailTimer) return;
    tailTimer = setTimeout(function () {
      tailTimer = null;
      var now = Date.now();
      for (var key in lastSeen) {
        var e = lastSeen[key];
        if (e.suppressed > 0 && (now - e.time) >= interval) {
          push(e.lv, e.tag, e.ev, { repeated: e.suppressed, tail: 1 });
          e.suppressed = 0;
          e.time = now;
        }
      }
    }, interval + 500);
  }

  // ---- سازگاری با کد موجود --------------------------------------------
  window.MHLog = MHLog;
  window.logEvent = function (tag, event, kv) { MHLog.event(tag, event, kv, 'I'); };
  window.logEventThrottled = function (tag, event, kv, ms) { MHLog.throttled(tag, event, kv, ms); };
  window.sendRemoteLog = function (msg) { push('I', 'RAW', String(msg)); };

  // ---- دام‌های خطای سراسری --------------------------------------------
  // ⚠️ وب‌ویوی تلگرام (به‌خصوص وب/دسکتاپ که Mini App رو تو iframe لود می‌کنه)
  // ممکنه msg/url/line رو به «Script error.» و ۰:۰ سانسور کنه — این محدودیت
  // امنیتی مرورگره. errorObj (پارامتر پنجم) معمولاً پرشده و stack واقعی رو
  // داره، حتی وقتی msg سانسور شده.
  window.addEventListener('error', function (ev) {
    var err = ev.error;
    MHLog.error('JSERR', 'onerror', {
      msg: ev.message,
      file: (ev.filename || '').split('/').pop(),
      line: ev.lineno,
      col: ev.colno,
      stack: err && err.stack ? String(err.stack).slice(0, 300) : ''
    });
  });

  window.addEventListener('unhandledrejection', function (ev) {
    var r = ev.reason;
    MHLog.error('JSERR', 'unhandledrejection', {
      msg: (r && r.message) || String(r),
      stack: r && r.stack ? String(r.stack).slice(0, 300) : ''
    });
  });

  window.addEventListener('pagehide', function () { flush(true); });
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') flush(true);
  });

  // صف pre-boot که shim داخل index.html پر کرده بود رو تخلیه کن.
  var pre = window.__MH_PREBOOT;
  if (pre && pre.length) {
    for (var i = 0; i < pre.length; i++) {
      push(pre[i].lv || 'I', pre[i].tag || 'BOOT', pre[i].ev || '?', pre[i].kv);
    }
    window.__MH_PREBOOT = [];
  }

  MHLog.info('BOOT', 'logger.js', { build: BUILD });
})();
