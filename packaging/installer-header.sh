#!/usr/bin/env bash
# ============================================================
#  مفلتر السيرفرات — حزمة متنقلة (تطبيق سطح مكتب + مهارة vpn-list)
#  الإصدار __VERSION__  ·  التطبيق __VERSION__
#
#  هذا الملف يُولَّد آليًا بواسطة build_package.sh — لا تعدّله يدويًا.
#
#  الاستخدام:
#    bash "مفلتر السيرفرات"                  تثبيت ثم فتح نافذة التطبيق
#    bash "مفلتر السيرفرات" --no-open        تشغيل الخادم بلا نافذة
#    bash "مفلتر السيرفرات" --no-desktop     دون تثبيت اختصار سطح المكتب
#    bash "مفلتر السيرفرات" --port 9000      منفذ مخصص
# ============================================================
set -euo pipefail

SELF="$0"
case "$SELF" in
  /*) ;;
  *) SELF="$PWD/${SELF#./}" ;;
esac

VERSION="__VERSION__"
APP_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/mofilter"
SKILL_HOME="${OPENCODE_SKILLS_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills}/vpn-list"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/vpn-list"
GH_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/vpn-list/github.json"
GH_TOKEN="__GITHUB_TOKEN__"

c_info() { printf '\033[36m%s\033[0m\n' "$*"; }
c_ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
c_warn() { printf '\033[33m%s\033[0m\n' "$*" >&2; }
die()    { printf '\033[31mخطأ: %s\033[0m\n' "$*" >&2; exit 1; }

show_help() {
  cat <<'EOF'
مفلتر السيرفرات — حزمة متنقلة

  bash "مفلتر السيرفرات"                  تثبيت ثم فتح نافذة التطبيق
  bash "مفلتر السيرفرات" --no-open        تشغيل الخادم بلا نافذة
  bash "مفلتر السيرفرات" --no-desktop     دون تثبيت اختصار سطح المكتب
  bash "مفلتر السيرفرات" --port 9000      منفذ مخصص
  bash "مفلتر السيرفرات" --keep-skill     أبقِ المهارة المثبتة دون ترقية
  bash "مفلتر السيرفرات" --help           هذه المساعدة
  bash "مفلتر السيرفرات" --version        رقم الإصدار

يثبّت المهارة إن لم تكن موجودة، ويُرقّيها إلى إصدار الحزمة إن كانت أقدم
(مع نسخة احتياطية)، ويثبّت تطبيق سطح المكتب (أيقونة + اختصار في القائمة
وسطح المكتب)، ثم يفتحه في نافذة مستقلة بلا شريط عنوان.
EOF
}

KEEP_SKILL=0
INSTALL_DESKTOP=1
NO_OPEN=0
PORT_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) show_help; exit 0 ;;
    -V|--version) echo "مفلتر السيرفرات $VERSION"; exit 0 ;;
    --keep-skill) KEEP_SKILL=1 ;;
    --no-desktop) INSTALL_DESKTOP=0 ;;
    --no-open) NO_OPEN=1 ;;
    --port) [ $# -ge 2 ] || die "--port يحتاج رقمًا"; PORT_ARG="$2"; shift ;;
    --port=*) PORT_ARG="${1#*=}" ;;
    *) die "خيار غير معروف: $1 (جرّب --help)" ;;
  esac
  shift
done

if [ -n "$PORT_ARG" ] && ! printf '%s' "$PORT_ARG" | grep -Eq '^[0-9]+$'; then
  die "منفذ غير صالح: $PORT_ARG"
fi

command -v python3 >/dev/null 2>&1 || die "python3 غير مثبت على هذا الجهاز"
command -v base64  >/dev/null 2>&1 || die "أداة base64 غير متوفرة"
command -v tar     >/dev/null 2>&1 || die "أداة tar غير متوفرة"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

c_info "فك الحزمة…"
sed -n '/^__PAYLOAD__$/,$p' "$SELF" | tail -n +2 | base64 -d | tar -xzf - -C "$TMP" \
  || die "تعذّر فك الحزمة (الملف تالف أو ناقص)"

[ -f "$TMP/app/vpn-web-app.py" ] || die "الحزمة لا تحتوي على التطبيق"
[ -f "$TMP/skill/scripts/run.py" ] || die "الحزمة لا تحتوي على مهارة vpn-list"

mkdir -p "$APP_HOME" "$(dirname "$SKILL_HOME")"
cp -f "$TMP/app/vpn-web-app.py" "$APP_HOME/vpn-web-app.py"
chmod +x "$APP_HOME/vpn-web-app.py"

NEW_VER="$(cat "$TMP/skill/.version" 2>/dev/null | tr -d '[:space:]' || true)"
CUR_VER="$(cat "$SKILL_HOME/.version" 2>/dev/null | tr -d '[:space:]' || true)"

if [ -f "$SKILL_HOME/scripts/run.py" ]; then
  if [ "$KEEP_SKILL" = "1" ]; then
    c_ok "المهارة موجودة مسبقًا — أُبقيت كما هي (--keep-skill)"
  elif [ -n "$NEW_VER" ] && [ "$NEW_VER" != "$CUR_VER" ] \
       && [ "$(printf '%s\n%s\n' "${CUR_VER:-0}" "$NEW_VER" | sort -V | tail -1)" = "$NEW_VER" ]; then
    # ترقية آمنة: نسخة احتياطية أولًا، ثم نسخ الملفات الجديدة فوق القديمة
    BK="$APP_HOME/skill-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$APP_HOME"
    cp -a "$SKILL_HOME" "$BK" 2>/dev/null || true
    cp -a "$TMP/skill/." "$SKILL_HOME/"
    c_ok "حُدّثت المهارة: ${CUR_VER:-?} → $NEW_VER (نسخة احتياطية: $BK)"
  else
    c_ok "المهارة موجودة بنفس الإصدار أو أحدث — أُبقيت كما هي"
  fi
else
  mkdir -p "$SKILL_HOME"
  cp -a "$TMP/skill/." "$SKILL_HOME/"
  c_ok "ثُبّتت المهارة في $SKILL_HOME"
fi

if [ -n "$GH_TOKEN" ]; then
  c_info "ضبط توكن GitHub…"
  python3 - "$GH_CONFIG" "$GH_TOKEN" <<'PY'
import json
import os
import sys

path, token = sys.argv[1], sys.argv[2]
data = {}
if os.path.isfile(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        data = {}
data.setdefault("owner", "Ahmed-vrn")
data.setdefault("repo", "vpn-servers")
data.setdefault("branch", "main")
data.setdefault("path", "vpn-servers.txt")
data.setdefault("public", True)
data["token"] = token
os.makedirs(os.path.dirname(path), exist_ok=True)
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
PY
  c_ok "توكن GitHub جاهز: $GH_CONFIG"
fi

if [ ! -x "$DATA_HOME/bin/sing-box" ] && [ ! -x "$DATA_HOME/bin/xray" ]; then
  c_warn "نوى الفحص (sing-box/Xray) غير موجودة — ستُنزَّل تلقائيًا عند أول تحديث (~50 MB تنزيلًا)."
fi

DESKTOP_OK=0
if [ "$INSTALL_DESKTOP" = "1" ] && [ -f "$TMP/desktop/install-desktop.sh" ]; then
  if bash "$TMP/desktop/install-desktop.sh" >/dev/null; then
    DESKTOP_OK=1
    c_ok "تطبيق سطح المكتب جاهز — ابحث عن «مفلتر السيرفرات» في قائمة التطبيقات"
  else
    c_warn "تعذّر تثبيت اختصار سطح المكتب — يمكنك تشغيل التطبيق من الطرفية."
  fi
fi

c_ok "التطبيق جاهز: $APP_HOME/vpn-web-app.py"

if [ "$DESKTOP_OK" = "1" ] && [ "$NO_OPEN" = "0" ] && [ -z "$PORT_ARG" ]; then
  exec "$APP_HOME/mofilter-desktop"
fi

RUN_ARGS=()
[ "$NO_OPEN" = "1" ] && RUN_ARGS+=(--no-open)
[ -n "$PORT_ARG" ] && RUN_ARGS+=(--port "$PORT_ARG")
python3 "$APP_HOME/vpn-web-app.py" ${RUN_ARGS[@]+"${RUN_ARGS[@]}"}
__PAYLOAD__
