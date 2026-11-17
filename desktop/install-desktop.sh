#!/usr/bin/env bash
# تثبيت «مفلتر السيرفرات» كتطبيق سطح مكتب في قائمة التطبيقات وسطح المكتب.
# يعمل من مجلد الحزمة أو من داخل الحزمة المتنقلة (TMP).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${HOME:?}"
APP_HOME="$HOME_DIR/.local/share/mofilter"
ICON_ROOT="$HOME_DIR/.local/share/icons/hicolor"
APPS_DIR="$HOME_DIR/.local/share/applications"
DESKTOP_DIR="$HOME_DIR/Desktop"
ENTRY="$APPS_DIR/mofilter.desktop"

info() { printf '\033[36m%s\033[0m\n' "$*"; }
ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }

[ -f "$HERE/mofilter-desktop.py" ] || { warn "ملفات سطح المكتب ناقصة: $HERE"; exit 1; }

mkdir -p "$APP_HOME" "$APPS_DIR" "$ICON_ROOT"

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
Categories=Network;
Keywords=vpn;proxy;servers;subscription;فpn;سيرفرات;بروكسي;
StartupNotify=true
StartupWMClass=MofilterVPN
EOF
chmod 644 "$ENTRY"

if [ -d "$DESKTOP_DIR" ]; then
  cp -f "$ENTRY" "$DESKTOP_DIR/مفلتر السيرفرات.desktop"
  chmod +x "$DESKTOP_DIR/مفلتر السيرفرات.desktop"
  # KDE: اجعل الاختصار موثوقًا إن كانت الأداة متوفرة
  command -v kwriteconfig6 >/dev/null 2>&1 && \
    kwriteconfig6 --file "$DESKTOP_DIR/مفلتر السيرفرات.desktop" \
      --group Desktop Entry --key X-KDE-Trusted true 2>/dev/null || true
fi

command -v update-desktop-database >/dev/null 2>&1 && \
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
  gtk-update-icon-cache -f -t "$ICON_ROOT" >/dev/null 2>&1 || true

ok "ثُبّت تطبيق سطح المكتب: $ENTRY"
ok "أيقونة واختصار على سطح المكتب: $DESKTOP_DIR/مفلتر السيرفرات.desktop"
