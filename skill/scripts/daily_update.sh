#!/usr/bin/env bash
# Daily refresh: run the pipeline, then rebuild the import bundle.
#
# Safety: before running, the current output is backed up. If the new run
# produces fewer than VPN_MIN_STABLE stable servers (default 1), the backup is
# restored and the previous bundle is left untouched.
#
# Environment:
#   VPN_OUT            output dir        (default ~/Desktop/vpn-list)
#   VPN_BUNDLE         bundle dir        (default ~/Desktop/vpn-ready)
#   VPN_LOG            log file          (default ~/.local/share/vpn-list/daily.log)
#   VPN_MIN_STABLE     minimum stable servers to accept a run (default 1)
#   VPN_CARRIER        mts|megafon|beeline|tele2|auto   (optional)
#   VPN_EXTRA_SOURCES  1 to add the Russia-focused lists
#   VPN_DEEP           1 to also fetch the very large general lists
#   VPN_REFRESH_SOURCES 1 to re-check the curated Russia sources + discover new ones
#   VPN_LIMIT          limit links for a quick/trial run (0 = full)
#   VPN_THRONE_SYNC    1 to import the fresh list into Throne after a run
#   VPN_THRONE_GROUP   target group name (default: «شغّال ✅»)
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${VPN_OUT:-$HOME/Desktop/vpn-list}"
BUNDLE="${VPN_BUNDLE:-$HOME/Desktop/vpn-ready}"
LOG="${VPN_LOG:-$HOME/.local/share/vpn-list/daily.log}"
MIN_STABLE="${VPN_MIN_STABLE:-1}"
BAK="${OUT}.bak"
mkdir -p "$(dirname "$LOG")" "$OUT"

{
  echo "===================== $(date -Is) ====================="
  if [ -s "$OUT/working_stable_unique.txt" ]; then
    rm -rf "$BAK"
    cp -a "$OUT" "$BAK"
    echo "[backup] previous list saved to $BAK"
  fi

  args=(--out "$OUT" --source "${VPN_SOURCE_URL:-https://raw.githubusercontent.com/solovyov-jenya2004/all_subs/refs/heads/main/sources.txt}")
  [ -n "${VPN_CARRIER:-}" ] && args+=(--carrier "$VPN_CARRIER")
  [ "${VPN_EXTRA_SOURCES:-0}" = "1" ] && args+=(--extra-sources)
  [ "${VPN_DEEP:-0}" = "1" ] && args+=(--deep-sources)
  [ "${VPN_REFRESH_SOURCES:-0}" = "1" ] && args+=(--refresh-sources)
  if [ -n "${VPN_LIMIT:-}" ] && [ "${VPN_LIMIT}" != "0" ]; then
    args+=(--limit "$VPN_LIMIT")
  fi
  python3 "$SKILL_DIR/scripts/run.py" "${args[@]}"

  n="$(wc -l < "$OUT/working_stable_unique.txt" 2>/dev/null || echo 0)"
  if [ "${n:-0}" -ge "$MIN_STABLE" ]; then
    rm -rf "$BAK"
    bash "$SKILL_DIR/scripts/build_bundle.sh" "$OUT" "$BUNDLE"
    echo "done $(date -Is)  (stable=$n)"
    # Publish the fresh list: the single Desktop file (used by the hourly
    # sync job) and the GitHub subscription that Throne downloads.
    if [ "${VPN_PUBLISH:-1}" = "1" ]; then
      SINGLE="${VPN_SINGLE_OUT:-$HOME/Desktop/vpn-servers.txt}"
      cp "$OUT/working_stable_unique.txt" "$SINGLE"
      echo "[publish] $SINGLE ($n servers)"
      python3 "$SKILL_DIR/scripts/github_sync.py" --file "$SINGLE" --public --quiet ||
        echo "[github] sync skipped/failed (exit $?)"
    else
      echo "[publish] skipped (VPN_PUBLISH=0)"
    fi
    # Optionally push the fresh list into a Throne/Nekoray-style client DB.
    # Gated by VPN_THRONE_SYNC=1 so the skill stays client-agnostic by default.
    # throne_sync.py no-ops when the client is running or the DB is missing.
    if [ "${VPN_THRONE_SYNC:-0}" = "1" ]; then
      python3 "$SKILL_DIR/scripts/throne_sync.py" \
        --list "$OUT/working_stable_unique.txt" --countries "$OUT/countries.json" ||
        echo "[throne] sync skipped/failed (exit $?)"
    fi
  else
    echo "[skip] new run produced only ${n:-0} stable server(s) < $MIN_STABLE"
    echo "[skip] previous list/bundle kept unchanged"
    if [ -d "$BAK" ]; then
      rm -rf "$OUT"
      mv "$BAK" "$OUT"
      echo "[restore] restored $OUT from backup"
    fi
  fi

  # Keep the single-file installer on the Desktop in sync with this skill.
  bash "$SKILL_DIR/scripts/build_installer.sh" --quiet ||
    echo "[installer] rebuild failed (exit $?)"
} >> "$LOG" 2>&1
