#!/usr/bin/env bash
# تثبيت «مفلتر السيرفرات» كتطبيق سطح مكتب في قائمة التطبيقات وسطح المكتب.
# يعمل من مجلد الحزمة أو من داخل الحزمة المتنقلة (TMP).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${HOME:?}"
XDG_DATA="${XDG_DATA_HOME:-$HOME_DIR/.local/share}"
APP_HOME="$XDG_DATA/mofilter"
ICON_ROOT="$XDG_DATA/icons/hicolor"
APPS_DIR="$XDG_DATA/applications"
DESKTOP_DIR="$HOME_DIR/Desktop"
if [ -n "${XDG_DESKTOP_DIR:-}" ] && [ -d "${XDG_DESKTOP_DIR}" ]; then
  DESKTOP_DIR="$XDG_DESKTOP_DIR"
elif command -v xdg-user-dir >/dev/null 2>&1; then
  XDG_DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
  if [ -n "$XDG_DESK" ] && [ -d "$XDG_DESK" ]; then
    DESKTOP_DIR="$XDG_DESK"
  fi
fi
ENTRY="$APPS_DIR/mofilter.desktop"

info() { printf '\033[36m%s\033[0m\n' "$*"; }
ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }

[ -f "$HERE/mofilter-desktop.py" ] || { warn "ملفات سطح المكتب ناقصة: $HERE"; exit 1; }

mkdir -p "$APP_HOME" "$APPS_DIR" "$ICON_ROOT"

# التطبيق نفسه: انسخه إن وُجد بجانب مجلد desktop/ (نقل «تطبيق سطح المكتب» وحده)
APP_SRC=""
for cand in "$HERE/../vpn-web-app.py" "$HERE/../app/vpn-web-app.py" "$HERE/vpn-web-app.py"; do
  [ -f "$cand" ] && APP_SRC="$cand" && break
done
if [ -n "$APP_SRC" ]; then
  install -m 755 "$APP_SRC" "$APP_HOME/vpn-web-app.py"
fi
[ -f "$APP_HOME/vpn-web-app.py" ] || \
  warn "لم يُعثر على vpn-web-app.py — انسخه إلى $APP_HOME أو شغّل الحزمة الكاملة"

install -m 755 "$HERE/mofilter-desktop.py" "$APP_HOME/mofilter-desktop"

for size in 16 24 32 48 64 128 256 512 1024; do
  src="$HERE/icons/mofilter-$size.png"
  [ -f "$src" ] || continue
  dir="$ICON_ROOT/${size}x${size}/apps"
  mkdir -p "$dir"
  install -m 644 "$src" "$dir/mofilter.png"
done
[ -f "$HERE/mofilter.png" ] && install -m 644 "$HERE/mofilter.png" "$APP_HOME/mofilter.png"

# أيقونة عالية الدقة تُستخدم مباشرة في ملف .desktop (تعمل حتى بلا فهرسة أيقونات)
ICON="$APP_HOME/mofilter.png"
[ -f "$ICON" ] || ICON="$ICON_ROOT/256x256/apps/mofilter.png"

cat > "$ENTRY" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=مفلتر السيرفرات
Name[en]=VPN Server Filter
GenericName=VPN Server Filter
GenericName[en]=VPN Server Filter
Comment=فحص اشتراكات VPN واختيار السيرفرات العاملة ودمجها في ملف واحد
Comment[en]=Test VPN subscriptions, keep the working servers, merge them into one file
Exec="$APP_HOME/mofilter-desktop"
TryExec=$APP_HOME/mofilter-desktop
Icon=$ICON
Terminal=false
Categories=Network;Utility;
Keywords=vpn;proxy;servers;subscription;سيرفرات;بروكسي;فلترة;
StartupNotify=true
StartupWMClass=MofilterVPN
EOF
chmod 644 "$ENTRY"

if mkdir -p "$DESKTOP_DIR" 2>/dev/null; then
  cp -f "$ENTRY" "$DESKTOP_DIR/مفلتر السيرفرات.desktop"
  chmod +x "$DESKTOP_DIR/مفلتر السيرفرات.desktop"
  # KDE: اجعل الاختصار موثوقًا إن كانت الأداة متوفرة
  command -v kwriteconfig6 >/dev/null 2>&1 && \
    kwriteconfig6 --file "$DESKTOP_DIR/مفلتر السيرفرات.desktop" \
      --group "Desktop Entry" --key X-KDE-Trusted true 2>/dev/null || true
  # GNOME: نفس الفكرة عبر gio (يُتجاهل الخطأ على الأسطح غير الداعمة)
  command -v gio >/dev/null 2>&1 && \
    gio set "$DESKTOP_DIR/مفلتر السيرفرات.desktop" metadata::trusted true 2>/dev/null || true
fi

command -v update-desktop-database >/dev/null 2>&1 && \
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
  gtk-update-icon-cache -f -t "$ICON_ROOT" >/dev/null 2>&1 || true

ok "ثُبّت تطبيق سطح المكتب: $ENTRY"
ok "أيقونة واختصار على سطح المكتب: $DESKTOP_DIR/مفلتر السيرفرات.desktop"
