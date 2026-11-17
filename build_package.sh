#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# ============================================================
#  بناء حزمة «مفلتر السيرفرات» المتنقلة (ملف واحد قابل للنقل)
#
#  الاستخدام:
#    bash build_package.sh                 # بناء الحزمة + تشغيل الاختبارات
#    bash build_package.sh --no-test       # بناء سريع بلا اختبارات
#    bash build_package.sh --output /tmp/x # مسار إخراج مختلف
#    bash build_package.sh --version 1.4.1 # التحقق من إصدار محدد
#
#  المصادر:
#    vpn-web-app.py          التطبيق
#    skill/                  مهارة vpn-list (سكربتات + مراجع)
#    desktop/                مشغّل سطح المكتب + الأيقونات + المثبّت
#    packaging/installer-header.sh   رأس الحزمة (قالب)
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEADER="$ROOT/packaging/installer-header.sh"
OUT="$ROOT/مفلتر السيرفرات"
RUN_TESTS=1

say()  { printf '\033[36m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m✔\033[0m %s\n' "$*"; }
warn() { printf '\033[33m⚠\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m✘\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --no-test) RUN_TESTS=0 ;;
    --output) [ $# -ge 2 ] || die "--output يحتاج مسارًا"; OUT="$2"; shift ;;
    --output=*) OUT="${1#*=}" ;;
    --version) [ $# -ge 2 ] || die "--version يحتاج رقمًا"; WANT_VERSION="$2"; shift ;;
    --version=*) WANT_VERSION="${1#*=}" ;;
    -h|--help)
      awk 'NR==1 {next} /^# =+$/ { if (started) exit; started=1; next } started { sub(/^# ?/, ""); print }' "${BASH_SOURCE[0]}"
      exit 0 ;;
    *) die "خيار غير معروف: $1" ;;
  esac
  shift
done

[ -f "$ROOT/vpn-web-app.py" ] || die "vpn-web-app.py غير موجود"
[ -f "$ROOT/skill/scripts/run.py" ] || die "skill/ غير مكتمل (run.py مفقود)"
[ -f "$ROOT/desktop/install-desktop.sh" ] || die "desktop/ غير مكتمل"
[ -f "$ROOT/desktop/mofilter.png" ] || die "desktop/mofilter.png مفقود"
[ -d "$ROOT/desktop/icons" ] || die "desktop/icons مفقود"
[ -f "$HEADER" ] || die "packaging/installer-header.sh غير موجود"

APP_VERSION="$(grep -m1 '^APP_VERSION = ' "$ROOT/vpn-web-app.py" | sed -E 's/.*"([^"]+)".*/\1/')"
SKILL_VERSION="$(tr -d '[:space:]' < "$ROOT/skill/.version" 2>/dev/null || true)"
DESKTOP_VERSION="$(grep -m1 '^VERSION = ' "$ROOT/desktop/mofilter-desktop.py" | sed -E 's/.*"([^"]+)".*/\1/')"
[ -n "$APP_VERSION" ] || die "تعذّر قراءة APP_VERSION"
[ "$APP_VERSION" = "$SKILL_VERSION" ] \
  || die "عدم تطابق الإصدار: التطبيق $APP_VERSION ≠ المهارة ${SKILL_VERSION:-?} — وحّدهما أولًا"
[ "$APP_VERSION" = "$DESKTOP_VERSION" ] \
  || die "عدم تطابق الإصدار: التطبيق $APP_VERSION ≠ مشغّل سطح المكتب ${DESKTOP_VERSION:-?}"
if [ -n "${WANT_VERSION:-}" ] && [ "$WANT_VERSION" != "$APP_VERSION" ]; then
  die "الإصدار المطلوب $WANT_VERSION ≠ إصدار المشروع $APP_VERSION"
fi

say "التحقق من سلامة المصادر"
python3 -m py_compile "$ROOT/vpn-web-app.py" "$ROOT/desktop/mofilter-desktop.py"
python3 -m py_compile "$ROOT"/skill/scripts/*.py
bash -n "$HEADER"
bash -n "$ROOT/desktop/install-desktop.sh"
ok "المصادر سليمة — الإصدار $APP_VERSION"

if [ "$RUN_TESTS" = "1" ]; then
  say "تشغيل الاختبارات"
  ( cd "$ROOT" && python3 test_selftest.py )
  ok "الاختبارات ناجحة"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say "تجهيز محتويات الحزمة"
STAGE="$TMP/stage"
mkdir -p "$STAGE/app" "$STAGE/skill" "$STAGE/desktop"
install -m 755 "$ROOT/vpn-web-app.py" "$STAGE/app/vpn-web-app.py"

# المهارة: كل شيء عدا مخلفات بايثون والنسخ الاحتياطية
rm -rf "$STAGE/skill"
mkdir -p "$STAGE/skill"
if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '__pycache__/' --exclude '*.pyc' --exclude '*.pyo' \
    --exclude '*.bak' --exclude '*.tmp' \
    "$ROOT/skill/" "$STAGE/skill/"
else
  tar -cf - --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' \
      --exclude='*.bak' --exclude='*.tmp' -C "$ROOT/skill" . \
    | tar -xf - -C "$STAGE/skill"
fi

# سطح المكتب: نفس محتويات الحزمة القديمة (بلا make-icons.py)
install -m 755 "$ROOT/desktop/install-desktop.sh" "$STAGE/desktop/install-desktop.sh"
install -m 755 "$ROOT/desktop/mofilter-desktop.py" "$STAGE/desktop/mofilter-desktop.py"
install -m 644 "$ROOT/desktop/mofilter.png" "$STAGE/desktop/mofilter.png"
cp -a "$ROOT/desktop/icons" "$STAGE/desktop/icons"

chmod -R u+rwX,go+rX "$STAGE"
find "$STAGE" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

say "توليد الحمولة"
tar -czf "$TMP/payload.tar.gz" -C "$STAGE" .
base64 -w 76 "$TMP/payload.tar.gz" > "$TMP/payload.b64" 2>/dev/null \
  || base64 "$TMP/payload.tar.gz" > "$TMP/payload.b64"

sed "s/__VERSION__/$APP_VERSION/g" "$HEADER" > "$TMP/header.sh"
cat "$TMP/header.sh" "$TMP/payload.b64" > "$TMP/mofilter.new"
chmod +x "$TMP/mofilter.new"

say "التحقق من الحزمة الناتجة"
bash -n "$TMP/mofilter.new"
GOT="$("$TMP/mofilter.new" --version)"
[ "$GOT" = "مفلتر السيرفرات $APP_VERSION" ] || die "إصدار الحزمة غير صحيح: $GOT"

# فك الحمولة ومقارنة الملفات الأساسية
mkdir -p "$TMP/check"
sed -n '/^__PAYLOAD__$/,$p' "$TMP/mofilter.new" | tail -n +2 | base64 -d | tar -xzf - -C "$TMP/check"
cmp -s "$TMP/check/app/vpn-web-app.py" "$ROOT/vpn-web-app.py" \
  || die "التطبيق داخل الحزمة لا يطابق المصدر"
[ "$(tr -d '[:space:]' < "$TMP/check/skill/.version")" = "$APP_VERSION" ] \
  || die "إصدار المهارة داخل الحزمة غير صحيح"
[ -f "$TMP/check/skill/scripts/run.py" ] || die "المهارة داخل الحزمة ناقصة"
[ -f "$TMP/check/desktop/install-desktop.sh" ] || die "سطح المكتب داخل الحزمة ناقص"
ok "الحمولة سليمة"

mkdir -p "$(dirname "$OUT")"
if [ -f "$OUT" ]; then
  cp -p "$OUT" "$OUT.bak" 2>/dev/null || true
fi
mv "$TMP/mofilter.new" "$OUT"
chmod +x "$OUT"

SIZE="$(du -h "$OUT" | cut -f1)"
SHA="$(sha256sum "$OUT" | cut -d' ' -f1)"
ok "تم بناء: $OUT"
printf '  الإصدار : %s\n  الحجم  : %s\n  SHA256 : %s\n' "$APP_VERSION" "$SIZE" "$SHA"
