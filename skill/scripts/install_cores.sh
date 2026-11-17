#!/usr/bin/env bash
# Download sing-box and Xray cores for the current OS/arch into the given dir.
# Usage: install_cores.sh <bin-dir>
set -euo pipefail

BIN="${1:?usage: install_cores.sh <bin-dir>}"
mkdir -p "$BIN"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
MACH="$(uname -m)"
case "$MACH" in
  x86_64|amd64) ARCH=amd64 ;;
  aarch64|arm64) ARCH=arm64 ;;
  *) echo "معمارية غير مدعومة: $MACH" >&2; exit 1 ;;
esac

need() { command -v "$1" >/dev/null 2>&1 || { echo "مطلوب: $1" >&2; exit 1; }; }
need curl
need python3

pick_asset() {  # $1=api-url  $2=regex
  python3 - "$1" "$2" <<'PY'
import json, re, sys, urllib.request
api, pat = sys.argv[1], sys.argv[2]
req = urllib.request.Request(api, headers={'User-Agent': 'vpn-list'})
d = json.load(urllib.request.urlopen(req, timeout=30))
rx = re.compile(pat)
for a in d.get('assets', []):
    if rx.search(a['name']):
        print(a['browser_download_url']); break
PY
}

if [ ! -x "$BIN/sing-box" ]; then
  echo "تنزيل sing-box ($OS-$ARCH)..."
  U="$(pick_asset https://api.github.com/repos/SagerNet/sing-box/releases/latest "${OS}-${ARCH}\\.tar\\.gz$")"
  curl -fsSL "$U" -o "$TMP/sb.tgz"
  tar xzf "$TMP/sb.tgz" -C "$TMP"
  cp "$TMP"/sing-box-*/sing-box "$BIN/sing-box"
  chmod +x "$BIN/sing-box"
fi

if [ ! -x "$BIN/xray" ]; then
  echo "تنزيل Xray ($OS-$ARCH)..."
  case "$OS-$ARCH" in
    linux-amd64)  PAT='Xray-linux-64\.zip$' ;;
    linux-arm64)  PAT='Xray-linux-arm64-v8a\.zip$' ;;
    darwin-amd64) PAT='Xray-macos-64\.zip$' ;;
    darwin-arm64) PAT='Xray-macos-arm64-v8a\.zip$' ;;
    *) PAT="Xray-${OS}.*\\.zip$" ;;
  esac
  U="$(pick_asset https://api.github.com/repos/XTLS/Xray-core/releases/latest "$PAT")"
  curl -fsSL "$U" -o "$TMP/xr.zip"
  python3 - "$TMP/xr.zip" "$BIN/xray" <<'PY'
import sys, zipfile, os, shutil
z, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(z) as f:
    for n in f.namelist():
        if os.path.basename(n) == 'xray':
            with f.open(n) as src, open(dst, 'wb') as out:
                shutil.copyfileobj(src, out)
            break
os.chmod(dst, 0o755)
PY
fi

echo "النوى جاهزة في: $BIN"
