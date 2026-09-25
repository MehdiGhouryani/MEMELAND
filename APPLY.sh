#!/usr/bin/env bash
# اعمال پچ روی پروژه‌ی MEMELAND.
# اجرا:  ./APPLY.sh /path/to/MEMELAND-main
set -euo pipefail
TARGET="${1:?استفاده: ./APPLY.sh /path/to/MEMELAND-main}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ -d "$TARGET/memeland_site" ] && [ -d "$TARGET/signal_bot" ] || {
  echo "❌ مسیر معتبر نیست: $TARGET"; exit 1; }

BACKUP="${TARGET%/}-backup-$(date +%F-%H%M)"
echo "📦 بکاپ → $BACKUP"
cp -r "$TARGET" "$BACKUP"

echo "🔧 کپی فایل‌های وب‌اپ..."
cp -r "$HERE/memeland_site/." "$TARGET/memeland_site/"
echo "🔧 کپی فایل‌های سرور..."
cp -r "$HERE/signal_bot/." "$TARGET/signal_bot/"
echo "🔧 کپی تست‌ها..."
cp -r "$HERE/tests" "$TARGET/signal_bot/"

echo "🧪 بررسی نحوی..."
for f in "$TARGET"/memeland_site/static/js/*.js; do
  node --check "$f" >/dev/null 2>&1 && echo "   ✅ $(basename "$f")" || echo "   ⚠️  $(basename "$f") (node نصب نیست یا خطا دارد)"
done
python3 - "$TARGET" <<'PY'
import ast, sys, pathlib
root = pathlib.Path(sys.argv[1]) / "signal_bot"
bad = 0
for p in root.rglob("*.py"):
    try: ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError as e:
        print(f"   ❌ {p.relative_to(root)}: {e}"); bad += 1
print("   ✅ همه‌ی فایل‌های پایتون سالم" if not bad else f"   ❌ {bad} فایل مشکل دارد")
PY

cat <<'MSG'

✅ پچ اعمال شد.

گام بعدی:
  ۱. ربات را ری‌استارت کنید
  ۲. در ربات بزنید:  /diag        ← هر چهار بخش باید ✅ باشد
  ۳. وب‌اپ را باز کنید، بعد:  /logs 40
     باید ببینید: [BOOT] modules ... API=1 Views=1 ... و adm=true verified=1
  ۴. یک‌بار (پیرو امنیتی دور اول):
       /wipe_sessions confirm   ← همه باید دوباره وب‌اپ را باز کنند
  ۵. همگام‌سازی سیگنال‌های قدیمی:
       /sync_all          ← فقط گزارش می‌دهد
       /sync_all apply    ← اگر گزارش درست بود، اعمال کنید
       /diag              ← باید «سینک: ✅ همگام» شود

تست‌ها (اختیاری، روی دیتابیس موقت اجرا می‌شوند و به داده‌ی واقعی دست نمی‌زنند):
  cd signal_bot && python3 tests/test_integration.py

اگر چیزی خراب شد، بکاپ بالا را برگردانید.
جزئیات کامل در REPORT.md
MSG
