#!/usr/bin/env bash
# Rebuild the single-file installer (skill-vpn) from the installed skill.
#
# The header lives in scripts/installer_header.sh and the payload is the skill
# directory itself, so this file is always produced from the current sources.
# It is idempotent: when nothing changed the existing file is left untouched.
#
# Usage:
#   scripts/build_installer.sh [OUTPUT] [--quiet]
# Environment:
#   VPN_INSTALLER_OUT   output path (default ~/Desktop/skill-vpn)
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${VPN_INSTALLER_OUT:-$HOME/Desktop/skill-vpn}"
QUIET=0
for arg in "$@"; do
  case "$arg" in
    --quiet) QUIET=1 ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) OUT="$arg" ;;
  esac
done
say() { [ "$QUIET" -eq 1 ] || echo "$@"; }

VERSION="$(cat "$SKILL_DIR/.version" 2>/dev/null || echo 0.0.0)"
HEADER="$SKILL_DIR/scripts/installer_header.sh"
[ -f "$HEADER" ] || { echo "error: missing $HEADER" >&2; exit 1; }
command -v tar >/dev/null || { echo "error: tar not found" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

sed -e "s/^#  v[0-9][0-9.]*$/#  v$VERSION/" \
    -e "s/^VERSION=\"[^\"]*\"$/VERSION=\"$VERSION\"/" \
    "$HEADER" > "$TMP/header.sh"

mkdir -p "$TMP/stage"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude '*.bak' \
        --exclude '.version' "$SKILL_DIR/" "$TMP/stage/"
else
  tar -cf - --exclude='__pycache__' --exclude='*.pyc' --exclude='*.bak' \
      --exclude='.version' -C "$SKILL_DIR" . | tar -xf - -C "$TMP/stage"
fi

tar -czf "$TMP/payload.tar.gz" -C "$TMP/stage" .
base64 -w 76 "$TMP/payload.tar.gz" > "$TMP/payload.b64" 2>/dev/null \
  || base64 "$TMP/payload.tar.gz" > "$TMP/payload.b64"
cat "$TMP/header.sh" "$TMP/payload.b64" > "$TMP/skill-vpn.new"
chmod +x "$TMP/skill-vpn.new"

if [ -f "$OUT" ] && cmp -s "$TMP/skill-vpn.new" "$OUT"; then
  say "installer up to date: $OUT (v$VERSION)"
  exit 0
fi

mkdir -p "$(dirname "$OUT")"
mv "$TMP/skill-vpn.new" "$OUT"
say "installer rebuilt: $OUT (v$VERSION)"
