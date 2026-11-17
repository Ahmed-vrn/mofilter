#!/usr/bin/env bash
# =============================================================================
#  VPN Working List — single-file installer / launcher
#  v1.4.1
#
#  Everything the skill needs (SKILL.md, INSTALL.md, scripts/, references/) is
#  embedded at the end of this file as a compressed payload, so this one file is
#  all you need to copy to another machine.
#
#  Usage:
#     ./skill-vpn                 install (or upgrade) the skill
#     ./skill-vpn --run [args]    run the pipeline through the installed skill
#     ./skill-vpn --sync [args]   push ~/Desktop/vpn-servers.txt to GitHub
#     ./skill-vpn --status        show install / config / schedule state
#     ./skill-vpn --uninstall     remove skill, scheduler entry and config
#     ./skill-vpn --version
#     ./skill-vpn --help
#
#  Options:
#     --token TOKEN     set or replace the GitHub token
#     --repo OWNER/REPO set the target repository
#     --branch NAME     set the target branch
#     --path PATH       set the target file path inside the repo
#     --no-cron         do not install the hourly GitHub sync job
#     --dry-run         show what would happen, change nothing
#     --yes             assume "yes" for the --purge prompt
#     --purge           with --uninstall: also delete ~/Desktop/vpn-servers.txt
# =============================================================================
set -euo pipefail

VERSION="1.4.1"
SKILL_NAME="vpn-list"
SKILLS_ROOT="${OPENCODE_SKILLS_DIR:-$HOME/.config/opencode/skills}"
DEST="$SKILLS_ROOT/$SKILL_NAME"

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF_DIR="$XDG_CONFIG_HOME/vpn-list"
CONF_FILE="$CONF_DIR/github.json"
LOG_DIR="$XDG_DATA_HOME/vpn-list"
APPS_DIR="$XDG_DATA_HOME/applications"
BIN_DIR="$HOME/.local/bin"

# Desktop may be localized (e.g. ~/Рабочий стол); VPN_DESKTOP overrides it.
if [ -n "${VPN_DESKTOP:-}" ]; then
  DESKTOP_DIR="$VPN_DESKTOP"
elif [ -d "$HOME/Desktop" ]; then
  DESKTOP_DIR="$HOME/Desktop"
elif command -v xdg-user-dir >/dev/null 2>&1; then
  DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
  [ -n "$DESKTOP_DIR" ] && [ -d "$DESKTOP_DIR" ] || DESKTOP_DIR="$HOME/Desktop"
else
  DESKTOP_DIR="$HOME/Desktop"
fi
OUT_FILE="$DESKTOP_DIR/vpn-servers.txt"

GH_OWNER="Ahmed-vrn"
GH_REPO="vpn-servers"
GH_BRANCH="main"
GH_PATH="vpn-servers.txt"
# NOTE: token intentionally embedded at the owner's request.
GH_TOKEN="${VPN_GITHUB_TOKEN:-}"

CRON_TAG="# vpn-list-github-sync"
INSTALL_CRON=1
PURGE=0
ASSUME_YES=0
DRY_RUN=0
CONF_EXPLICIT_TOKEN=0
CONF_EXPLICIT_REPO=0
CONF_EXPLICIT_BRANCH=0
CONF_EXPLICIT_PATH=0
ACTION="install"
RUN_ARGS=()
SYNC_ARGS=()

TMP_UNPACK=""
cleanup() {
  if [ -n "${TMP_UNPACK:-}" ] && [ -d "$TMP_UNPACK" ]; then rm -rf -- "$TMP_UNPACK"; fi
}
trap cleanup EXIT INT TERM

c_ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
c_info() { printf '\033[36m%s\033[0m\n' "$*"; }
c_warn() { printf '\033[33m%s\033[0m\n' "$*" >&2; }
c_err()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }
die()    { c_err "error: $*"; exit 1; }

audit() {
  mkdir -p "$LOG_DIR" 2>/dev/null || true
  printf '%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG_DIR/install.log" 2>/dev/null || true
}

usage() {
  cat <<'EOF'
VPN Working List — single-file installer / launcher

Usage:
  ./skill-vpn                 install (or upgrade) the skill
  ./skill-vpn --run [args]    run the pipeline through the installed skill
  ./skill-vpn --sync [args]   push ~/Desktop/vpn-servers.txt to GitHub (see --help below)
  ./skill-vpn --status        show install / config / schedule state
  ./skill-vpn --uninstall     remove skill, scheduler entry and config
  ./skill-vpn --version       print the installer version
  ./skill-vpn --help          this message

Options:
  --token TOKEN      set or replace the GitHub token
  --repo OWNER/REPO  set the target repository
  --branch NAME      set the target branch
  --path PATH        set the target file path inside the repo
  --no-cron          do not install the hourly GitHub sync job
  --dry-run          show what would happen, change nothing
  --yes              assume "yes" for the --purge prompt
  --purge            with --uninstall: also delete ~/Desktop/vpn-servers.txt

Sync options (after --sync):
  --clean            delete all other files in the repository (keep only vpn-servers.txt)
  --public           allow a public repository (default: private)
  --force            upload even if content is unchanged
  --dry-run          show what would happen, change nothing

Examples:
  ./skill-vpn
  ./skill-vpn --token ghp_xxx --repo Ahmed-vrn/vpn-servers
  ./skill-vpn --run --source 'https://example.com/sub' --single
  ./skill-vpn --sync --dry-run
EOF
}

# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h)   usage; exit 0 ;;
    --version)   printf 'skill-vpn %s\n' "$VERSION"; exit 0 ;;
    --run)       ACTION="run"; shift; RUN_ARGS=("$@"); break ;;
    --sync)      ACTION="sync"; shift; SYNC_ARGS=("$@"); break ;;
    --status)    ACTION="status"; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    --reinstall) ACTION="install"; shift ;;
    --token)     [ $# -ge 2 ] || die "--token needs a value"
                 GH_TOKEN="$2"; CONF_EXPLICIT_TOKEN=1; shift 2 ;;
    --repo)      [ $# -ge 2 ] || die "--repo needs OWNER/REPO"
                 GH_OWNER="${2%%/*}"; GH_REPO="${2##*/}"; CONF_EXPLICIT_REPO=1; shift 2 ;;
    --branch)    [ $# -ge 2 ] || die "--branch needs a value"
                 GH_BRANCH="$2"; CONF_EXPLICIT_BRANCH=1; shift 2 ;;
    --path)      [ $# -ge 2 ] || die "--path needs a value"
                 GH_PATH="$2"; CONF_EXPLICIT_PATH=1; shift 2 ;;
    --no-cron)   INSTALL_CRON=0; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --yes)       ASSUME_YES=1; shift ;;
    --purge)     PURGE=1; shift ;;
    *)           die "unknown argument: $1 (try --help)" ;;
  esac
done

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
need() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

# Refuse to delete anything outside the directories this installer owns.
safe_rm() {
  local p="$1"
  [ -n "$p" ] || die "safe_rm: empty path"
  case "$p" in
    /|"$HOME"|"$HOME/") die "safe_rm: refusing to delete '$p'" ;;
  esac
  case "$p" in
    "$SKILLS_ROOT"/*|"$APPS_DIR"/*|"$BIN_DIR"/*|"$CONF_DIR"/*|"$LOG_DIR"/*)
      rm -rf -- "$p" ;;
    *) die "safe_rm: refusing to delete '$p' (outside allowed roots)" ;;
  esac
}

pick_python() {
  local p
  for p in python3 python; do
    if command -v "$p" >/dev/null 2>&1; then
      if "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' 2>/dev/null; then
        command -v "$p"; return 0
      fi
    fi
  done
  return 1
}

# Merge the target settings into an existing config, preserving other keys.
write_config() {
  local py="$1"
  mkdir -p "$CONF_DIR"
  chmod 700 "$CONF_DIR" 2>/dev/null || true
  ( umask 077
    VPN_OWNER="$GH_OWNER" VPN_REPO="$GH_REPO" VPN_BRANCH="$GH_BRANCH" \
    VPN_PATH="$GH_PATH" VPN_TOKEN="$GH_TOKEN" VPN_CFG="$CONF_FILE" \
    "$py" - <<'PY'
import json, os
cfg = os.environ["VPN_CFG"]
try:
    with open(cfg) as f:
        d = json.load(f)
    if not isinstance(d, dict):
        d = {}
except Exception:
    d = {}
d.update(owner=os.environ["VPN_OWNER"], repo=os.environ["VPN_REPO"],
         branch=os.environ["VPN_BRANCH"], path=os.environ["VPN_PATH"],
         token=os.environ["VPN_TOKEN"], public=True)
with open(cfg, "w") as f:
    json.dump(d, f, indent=2)
PY
  )
  chmod 600 "$CONF_FILE"
}

b64decode() {
  if base64 -d </dev/null >/dev/null 2>&1; then base64 -d
  elif base64 -D </dev/null >/dev/null 2>&1; then base64 -D
  elif command -v openssl >/dev/null 2>&1; then openssl base64 -d
  else die "no working base64 decoder (base64/openssl)"
  fi
}

# ---------------------------------------------------------------------------
# scheduler: cron if present, otherwise a systemd user timer
# ---------------------------------------------------------------------------
cron_backup() {
  mkdir -p "$LOG_DIR"
  if crontab -l >/dev/null 2>&1; then
    crontab -l > "$LOG_DIR/crontab.bak.$(date +%Y%m%d-%H%M%S)" 2>/dev/null \
      && c_info "crontab backed up in $LOG_DIR"
  fi
}

install_cron() {
  local py="$1" line tmp
  mkdir -p "$LOG_DIR"
  line="0 * * * * cd \"$DEST\" && [ -s \"$OUT_FILE\" ] && \"$py\" \"$DEST/scripts/github_sync.py\" --quiet --public >> \"$LOG_DIR/github-sync.log\" 2>&1; \"$DEST/scripts/build_installer.sh\" --quiet >> \"$LOG_DIR/github-sync.log\" 2>&1 $CRON_TAG"
  cron_backup
  tmp="$(mktemp)"
  { crontab -l 2>/dev/null | grep -Fv "$CRON_TAG" || true; echo "$line"; } > "$tmp"
  if [ "$DRY_RUN" -eq 1 ]; then
    c_info "[dry-run] would install cron line:"; echo "  $line"; rm -f "$tmp"; return 0
  fi
  if crontab "$tmp"; then
    rm -f "$tmp"; c_ok "hourly GitHub sync installed in crontab"; return 0
  fi
  rm -f "$tmp"; c_warn "could not write crontab"; return 1
}

install_timer() {
  local py="$1" ud="$XDG_CONFIG_HOME/systemd/user"
  mkdir -p "$ud"
  cat > "$ud/vpn-list-sync.service" <<EOF
[Unit]
Description=VPN Working List - GitHub sync
ConditionPathExists="$OUT_FILE"

[Service]
Type=oneshot
WorkingDirectory=$DEST
ExecStart="$py" "$DEST/scripts/github_sync.py" --quiet --public
ExecStart="$DEST/scripts/build_installer.sh" --quiet
EOF
  cat > "$ud/vpn-list-sync.timer" <<EOF
[Unit]
Description=Hourly VPN Working List GitHub sync

[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
EOF
  if [ "$DRY_RUN" -eq 1 ]; then
    c_info "[dry-run] would write systemd user units in $ud"; return 0
  fi
  systemctl --user daemon-reload || { c_warn "systemd daemon-reload failed"; return 1; }
  systemctl --user enable --now vpn-list-sync.timer || { c_warn "could not enable the systemd timer"; return 1; }
  c_ok "hourly GitHub sync installed as a systemd user timer"
}

install_scheduler() {
  local py="$1"
  if command -v crontab >/dev/null 2>&1; then
    if install_cron "$py"; then return 0; fi
  fi
  if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
    if install_timer "$py"; then return 0; fi
  fi
  c_warn "no cron and no systemd user session found — automatic sync not installed"
  c_warn "run '$0 --sync' manually, or install cron and re-run the installer"
  return 0
}

remove_scheduler() {
  if command -v crontab >/dev/null 2>&1 && crontab -l 2>/dev/null | grep -Fq "$CRON_TAG"; then
    local tmp; tmp="$(mktemp)"
    cron_backup
    crontab -l 2>/dev/null | grep -Fv "$CRON_TAG" > "$tmp"
    crontab "$tmp" && c_ok "cron entry removed"
    rm -f "$tmp"
  fi
  # Only touch the user manager if this HOME actually owns the unit files;
  # otherwise (e.g. a throwaway HOME) we would stop the real user's timer.
  local ud="$XDG_CONFIG_HOME/systemd/user" had_unit=0
  if [ -f "$ud/vpn-list-sync.timer" ] || [ -f "$ud/vpn-list-sync.service" ]; then
    had_unit=1
  fi
  if [ "$had_unit" -eq 1 ] && command -v systemctl >/dev/null 2>&1; then
    systemctl --user disable --now vpn-list-sync.timer >/dev/null 2>&1 || true
  fi
  rm -f "$ud/vpn-list-sync.timer" "$ud/vpn-list-sync.service"
  if [ "$had_unit" -eq 1 ] && command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload >/dev/null 2>&1 || true
  fi
}

# ---------------------------------------------------------------------------
# menu entry + CLI wrapper
# ---------------------------------------------------------------------------
install_menu_entry() {
  local py="$1"
  if [ "$DRY_RUN" -eq 1 ]; then
    c_info "[dry-run] would create $APPS_DIR/vpn-list.desktop and $BIN_DIR/vpn-list"
    return 0
  fi
  mkdir -p "$APPS_DIR" "$BIN_DIR"
  cat > "$APPS_DIR/vpn-list.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=VPN Working List
Comment=Test and merge working VPN servers
Exec=bash -lc 'cd "$DEST" && "$py" scripts/run.py --single; echo; read -rp "Enter to close..."'
Icon=network-vpn
Terminal=true
Categories=Network;Utility;
EOF
  chmod +x "$APPS_DIR/vpn-list.desktop"

  cat > "$BIN_DIR/vpn-list" <<EOF
#!/usr/bin/env bash
exec "$py" "$DEST/scripts/run.py" "\$@"
EOF
  chmod +x "$BIN_DIR/vpn-list"

  cat > "$BIN_DIR/vpn-web" <<EOF
#!/usr/bin/env bash
exec "$py" "$DEST/web/vpnweb.py" "\$@"
EOF
  chmod +x "$BIN_DIR/vpn-web"
}

verify_install() {
  local py="$1"
  [ -f "$DEST/SKILL.md" ] || { c_err "missing SKILL.md"; return 1; }
  [ -f "$DEST/scripts/run.py" ] || { c_err "missing scripts/run.py"; return 1; }
  [ -f "$DEST/scripts/github_sync.py" ] || { c_err "missing scripts/github_sync.py"; return 1; }
  [ -f "$DEST/.version" ] || { c_err "missing .version"; return 1; }
  [ "$(cat "$DEST/.version" 2>/dev/null)" = "$VERSION" ] \
    || { c_err "version mismatch in .version"; return 1; }
  "$py" -m py_compile "$DEST"/scripts/*.py || { c_err "py_compile failed"; return 1; }
  "$py" "$DEST/scripts/run.py" --help >/dev/null 2>&1 || { c_err "run.py --help failed"; return 1; }
  return 0
}

# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------
do_install() {
  need tar; need gzip; need awk; need tail
  local PY
  PY="$(pick_python)" || die "python3 >= 3.8 is required"
  c_info "python: $PY"
  c_info "version: $VERSION"

  if [ "$DRY_RUN" -eq 1 ]; then
    c_info "[dry-run] would install to: $DEST"
    c_info "[dry-run] would write config: $CONF_FILE"
    [ "$INSTALL_CRON" -eq 1 ] && c_info "[dry-run] would install the hourly scheduler"
    return 0
  fi

  mkdir -p "$SKILLS_ROOT"
  if [ -e "$DEST" ]; then
    local bak="$LOG_DIR/backups/vpn-list-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$(dirname "$bak")"
    mv "$DEST" "$bak"
    c_info "previous install backed up to $bak"
  fi

  # unpack next to DEST so the final move is a same-filesystem rename
  TMP_UNPACK="$(mktemp -d "$SKILLS_ROOT/.$SKILL_NAME.XXXXXX")"
  local start
  start="$(awk '/^__PAYLOAD_BELOW__$/{print NR+1; exit}' "$0")"
  [ -n "${start:-}" ] || die "payload marker not found (is this file truncated?)"
  tail -n +"$start" "$0" | b64decode | tar -xzf - -C "$TMP_UNPACK" \
    || die "failed to unpack payload (file truncated or corrupted?)"

  mv "$TMP_UNPACK" "$DEST"
  TMP_UNPACK=""

  printf '%s\n' "$VERSION" > "$DEST/.version"
  chmod +x "$DEST"/scripts/*.sh 2>/dev/null || true
  chmod +x "$DEST"/scripts/*.py 2>/dev/null || true
  mkdir -p "$LOG_DIR" "$CONF_DIR"

  if [ "$CONF_EXPLICIT_TOKEN" -eq 1 ] || [ "$CONF_EXPLICIT_REPO" -eq 1 ] \
     || [ "$CONF_EXPLICIT_BRANCH" -eq 1 ] || [ "$CONF_EXPLICIT_PATH" -eq 1 ] \
     || [ ! -f "$CONF_FILE" ]; then
    write_config "$PY"
    c_ok "GitHub config written to $CONF_FILE (mode 600)"
  else
    chmod 600 "$CONF_FILE" 2>/dev/null || true
    c_info "keeping existing GitHub config at $CONF_FILE"
  fi

  install_menu_entry "$PY"
  [ "$INSTALL_CRON" -eq 1 ] && install_scheduler "$PY"

  verify_install "$PY" || die "install verification failed"
  c_ok "install verified"
  audit "install v$VERSION -> $DEST"

  echo
  c_ok "VPN Working List v$VERSION installed at $DEST"
  echo
  echo "  Run:        vpn-list --single"
  echo "              $PY $DEST/scripts/run.py --single"
  echo "  With URL:   vpn-list --source 'URL' --single"
  echo "  Sync now:   $0 --sync"
  echo "  Status:     $0 --status"
  echo "  Uninstall:  $0 --uninstall"
  echo
  if [ -f "$OUT_FILE" ]; then
    echo "  Result file: $OUT_FILE ($(grep -c . "$OUT_FILE" 2>/dev/null || echo 0) lines)"
  else
    echo "  Result file: $OUT_FILE (not created yet — run the skill once)"
  fi
  echo
  c_warn "security: the GitHub token is stored in plain text in $CONF_FILE."
  c_warn "If it was ever shared or committed anywhere, revoke it at"
  c_warn "https://github.com/settings/tokens and re-run: ./skill-vpn --token NEW_TOKEN"
}

do_status() {
  local PY; PY="$(pick_python || true)"
  echo "installer : v$VERSION"
  echo "skill dir : $DEST $([ -d "$DEST" ] && echo '[ok]' || echo '[missing]')"
  [ -f "$DEST/.version" ] && echo "installed : v$(cat "$DEST/.version" 2>/dev/null)"
  echo "SKILL.md  : $([ -f "$DEST/SKILL.md" ] && echo '[ok]' || echo '[missing]')"
  echo "scripts   : $(find "$DEST/scripts" -maxdepth 1 -name '*.py' 2>/dev/null | wc -l) python files"
  echo "result    : $OUT_FILE $([ -f "$OUT_FILE" ] && echo "[$(grep -c . "$OUT_FILE" 2>/dev/null || echo 0) lines]" || echo '[not created]')"
  if [ -f "$CONF_FILE" ] && [ -n "$PY" ]; then
    echo "github cfg: $CONF_FILE [ok]"
    echo "  target    : $("$PY" -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("owner","")+"/"+d.get("repo",""), d.get("branch",""), d.get("path",""))' "$CONF_FILE" 2>/dev/null || echo 'unreadable')"
    echo "  token     : $("$PY" -c 'import json,sys;d=json.load(open(sys.argv[1]));t=d.get("token","");print((t[:7]+"..."+t[-4:]) if t else "(none)")' "$CONF_FILE" 2>/dev/null || echo 'unreadable')"
  else
    echo "github cfg: missing or python unavailable"
  fi
  if command -v crontab >/dev/null 2>&1 && crontab -l 2>/dev/null | grep -Fq "$CRON_TAG"; then
    echo "schedule  : [ok] hourly (cron)"
  elif command -v systemctl >/dev/null 2>&1 \
       && [ -f "$XDG_CONFIG_HOME/systemd/user/vpn-list-sync.timer" ] \
       && systemctl --user is-enabled vpn-list-sync.timer >/dev/null 2>&1; then
    echo "schedule  : [ok] hourly (systemd timer: $(systemctl --user is-active vpn-list-sync.timer 2>/dev/null || echo unknown))"
  else
    echo "schedule  : [not installed]"
  fi
  if [ -f "$LOG_DIR/github-sync.log" ]; then
    echo "last sync :"
    tail -n 3 "$LOG_DIR/github-sync.log" | sed 's/^/  /'
  fi
}

do_sync() {
  [ -d "$DEST" ] || die "skill is not installed; run $0 first"
  local PY; PY="$(pick_python)" || die "python3 >= 3.8 is required"
  [ -f "$CONF_FILE" ] || die "missing $CONF_FILE; run $0 --token <TOKEN>"
  audit "sync"
  exec "$PY" "$DEST/scripts/github_sync.py" ${SYNC_ARGS[@]+"${SYNC_ARGS[@]}"}
}

do_run() {
  [ -d "$DEST" ] || die "skill is not installed; run $0 first"
  local PY; PY="$(pick_python)" || die "python3 >= 3.8 is required"
  audit "run"
  exec "$PY" "$DEST/scripts/run.py" ${RUN_ARGS[@]+"${RUN_ARGS[@]}"}
}

do_uninstall() {
  if [ "$DRY_RUN" -eq 1 ]; then
    c_info "[dry-run] would remove:"
    echo "  $DEST"
    echo "  $APPS_DIR/vpn-list.desktop"
    echo "  $BIN_DIR/vpn-list"
    echo "  $LOG_DIR/backups"
    echo "  $CONF_FILE"
    echo "  cron/systemd timer entry"
    [ "$PURGE" -eq 1 ] && echo "  $OUT_FILE"
    return 0
  fi
  if [ "$PURGE" -eq 1 ] && [ "$ASSUME_YES" -eq 0 ]; then
    printf 'This will delete %s. Continue? [y/N] ' "$OUT_FILE"
    read -r ans || true
    case "${ans:-}" in y|Y|yes|YES) ;; *) die "aborted" ;; esac
  fi
  remove_scheduler
  safe_rm "$APPS_DIR/vpn-list.desktop" 2>/dev/null || true
  safe_rm "$BIN_DIR/vpn-list" 2>/dev/null || true
  local b
  for b in "$DEST" "$SKILLS_ROOT/$SKILL_NAME".bak.*; do
    if [ -d "$b" ]; then safe_rm "$b" && c_ok "removed $b"; fi
  done
  if [ -d "$LOG_DIR/backups" ]; then safe_rm "$LOG_DIR/backups" || true; fi
  if [ -f "$CONF_FILE" ]; then safe_rm "$CONF_FILE" || true; fi
  rmdir "$CONF_DIR" 2>/dev/null || true
  if [ "$PURGE" -eq 1 ]; then rm -f -- "$OUT_FILE"; c_ok "removed $OUT_FILE"; fi
  audit "uninstall (purge=$PURGE)"
  rm -f "$LOG_DIR/install.log" "$LOG_DIR/github-sync.log" "$LOG_DIR"/crontab.bak.* 2>/dev/null || true
  rmdir "$LOG_DIR" 2>/dev/null || true
  c_ok "VPN Working List uninstalled"
}

case "$ACTION" in
  install)   do_install ;;
  status)    do_status ;;
  sync)      do_sync ;;
  run)       do_run ;;
  uninstall) do_uninstall ;;
esac

exit 0
__PAYLOAD_BELOW__
