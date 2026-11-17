#!/usr/bin/env python3
"""Push the merged working-servers file to a GitHub repository.

Standard library only: no `requests`, no pip install needed.

Configuration (first match wins):
  1. command-line flags
  2. environment: GITHUB_TOKEN, VPN_GITHUB_REPO, VPN_GITHUB_BRANCH, VPN_GITHUB_PATH
  3. ~/.config/vpn-list/github.json

Example config file:
  {
    "owner": "Ahmed-vrn",
    "repo": "vpn-servers",
    "branch": "main",
    "path": "vpn-servers.txt",
    "token": "ghp_..."
  }

Usage:
  python3 scripts/github_sync.py                # upload if content changed
  python3 scripts/github_sync.py --dry-run      # show what would happen
  python3 scripts/github_sync.py --file /path/to/list.txt
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
_cfg_home = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
DEFAULT_CONFIG = _cfg_home / "vpn-list" / "github.json"
try:
    import common  # same directory; keeps the Desktop path consistent with run.py
    _DESKTOP = Path(common.DESKTOP)
except Exception:
    _DESKTOP = Path.home() / "Desktop"
DEFAULT_FILE = _DESKTOP / "vpn-servers.txt"
UA = "vpn-list-skill/1.0"


def load_config() -> dict:
    if DEFAULT_CONFIG.exists():
        try:
            return json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"warning: cannot read {DEFAULT_CONFIG}: {exc}", file=sys.stderr)
    return {}


def api(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", UA)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except ValueError:
            payload = {"message": raw[:400]}
        return exc.code, payload
    except urllib.error.URLError as exc:
        return 0, {"message": f"network error: {exc.reason}"}


def api_retry(method: str, url: str, token: str, body: dict | None = None,
              attempts: int = 5) -> tuple[int, dict]:
    """Like api(), but waits out GitHub's short 'repository has been locked'
    window that follows a visibility change."""
    status, payload = 0, {}
    for i in range(attempts):
        status, payload = api(method, url, token, body)
        msg = str(payload.get("message", "")).lower()
        if status == 403 and "locked" in msg and i + 1 < attempts:
            time.sleep(1.5 * (i + 1))
            continue
        return status, payload
    return status, payload


def main() -> int:
    cfg = load_config()

    ap = argparse.ArgumentParser(description="Upload the working VPN list to GitHub")
    ap.add_argument("--file", default=os.environ.get("VPN_LIST_FILE", str(DEFAULT_FILE)))
    ap.add_argument("--owner", default=os.environ.get("VPN_GITHUB_OWNER", cfg.get("owner", "")))
    ap.add_argument("--repo", default=os.environ.get("VPN_GITHUB_REPO", cfg.get("repo", "")))
    ap.add_argument("--branch", default=os.environ.get("VPN_GITHUB_BRANCH", cfg.get("branch", "main")))
    ap.add_argument("--path", default=os.environ.get("VPN_GITHUB_PATH", cfg.get("path", "vpn-servers.txt")))
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", cfg.get("token", "")))
    ap.add_argument("--message", default="Update working VPN servers")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--create-repo", action="store_true",
                    help="create the repository if it does not exist")
    ap.add_argument("--public", action="store_true",
                    help="allow a public repository (default: the repository is forced private)")
    ap.add_argument("--force", action="store_true", help="upload even if content is unchanged")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--clean", action="store_true",
                    help="delete all other files in the repository (keep only vpn-servers.txt)")
    args = ap.parse_args()

    # A public repository is required when a client (Throne/Nekoray) must be
    # able to download the subscription without a token. Honour the config
    # file and the environment so unattended runs keep the same visibility.
    env_public = os.environ.get("VPN_GITHUB_PUBLIC", "").lower() in ("1", "true", "yes", "on")
    if not args.public and (cfg.get("public") is True or env_public):
        args.public = True

    # Allow --repo OWNER/REPO as well as a bare repo name.
    if "/" in args.repo:
        args.owner, args.repo = args.repo.split("/", 1)

    def say(msg: str) -> None:
        if not args.quiet:
            print(msg, flush=True)

    src = Path(args.file).expanduser()
    if not src.is_file():
        print(f"error: list file not found: {src}", file=sys.stderr)
        return 1

    servers = [ln.strip() for ln in src.read_text(encoding="utf-8", errors="replace").splitlines()]
    servers = [ln for ln in servers if ln and not ln.startswith("#")]
    if not servers:
        print(f"error: no servers in {src}", file=sys.stderr)
        return 1

    if not args.token:
        print("error: no GitHub token (set GITHUB_TOKEN or ~/.config/vpn-list/github.json)", file=sys.stderr)
        return 1
    if not args.owner or not args.repo:
        print("error: owner/repo not configured", file=sys.stderr)
        return 1

    content = (
        "# Working VPN Servers\n"
        f"# Total servers: {len(servers)}\n"
        "# Source: VPN Working List skill\n\n"
        + "\n".join(servers)
        + "\n"
    )

    url = f"{API}/repos/{args.owner}/{args.repo}/contents/{urllib.parse.quote(args.path)}"
    say(f"repo: {args.owner}/{args.repo}@{args.branch}  file: {args.path}  servers: {len(servers)}")

    # Preflight: distinguish "repository missing / no access" from "file missing".
    repo_status, repo_info = api("GET", f"{API}/repos/{args.owner}/{args.repo}", args.token)
    if repo_status == 404:
        if args.create_repo:
            created, payload = api("POST", f"{API}/user/repos", args.token, {
                "name": args.repo,
                "description": "Working VPN servers (auto-updated by the vpn-list skill)",
                "private": not args.public,
                "auto_init": True,
            })
            if created not in (200, 201):
                print(f"error: could not create repository ({created}): {payload.get('message')}",
                      file=sys.stderr)
                return 1
            say(f"created repository {args.owner}/{args.repo}")
        else:
            print(
                f"error: repository {args.owner}/{args.repo} was not found or is not visible "
                f"to this token.\n"
                f"       create it on GitHub, or re-run with --create-repo,\n"
                f"       and make sure the token has 'Contents: read and write' on it.",
                file=sys.stderr,
            )
            return 1
    elif repo_status in (401, 403):
        print(f"error: GitHub rejected the token ({repo_status}): {repo_info.get('message')}",
              file=sys.stderr)
        return 1
    elif repo_status != 200:
        print(f"error: cannot read repository ({repo_status}): {repo_info.get('message')}",
              file=sys.stderr)
        return 1

    # Privacy: the list of servers that actually work is sensitive. Keep the
    # repository private unless the user explicitly asked for a public one.
    if repo_status == 200 and not args.public and not repo_info.get("private", False):
        if args.dry_run:
            say(f"[dry-run] repository {args.owner}/{args.repo} is public; would switch it to private")
        else:
            pstatus, pinfo = api("PATCH", f"{API}/repos/{args.owner}/{args.repo}",
                                 args.token, {"private": True})
            if pstatus == 200:
                say(f"repository {args.owner}/{args.repo} was public; switched to private")
            else:
                print(f"warning: could not make the repository private ({pstatus}): "
                      f"{pinfo.get('message')}", file=sys.stderr)

    status, current = api("GET", f"{url}?ref={urllib.parse.quote(args.branch)}", args.token)

    sha = None
    if status == 200:
        sha = current.get("sha")
        try:
            remote = base64.b64decode(current.get("content", "")).decode("utf-8", "replace")
        except (ValueError, TypeError):
            remote = ""
        if not args.force and remote.strip() == content.strip():
            say("up to date: remote content is identical, nothing to do")
            return 0
    elif status == 404:
        say("remote file does not exist yet, it will be created")
    elif status in (401, 403):
        print(f"error: GitHub rejected the token ({status}): {current.get('message')}", file=sys.stderr)
        return 1
    else:
        print(f"error: cannot read remote file ({status}): {current.get('message')}", file=sys.stderr)
        return 1

    if args.dry_run:
        say("[dry-run] would upload")
        return 0

    body = {
        "message": args.message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": args.branch,
    }
    if sha:
        body["sha"] = sha

    status, result = api_retry("PUT", url, args.token, body)
    if status in (200, 201):
        commit = (result.get("commit") or {}).get("sha", "")[:8]
        say(f"uploaded: https://github.com/{args.owner}/{args.repo}/blob/{args.branch}/{args.path} ({commit})")
        # After upload, check if the repo is still public and try to make it private.
        if not args.public:
            time.sleep(0.5)
            rstatus, rinfo = api("GET", f"{API}/repos/{args.owner}/{args.repo}", args.token)
            if rstatus == 200 and not rinfo.get("private", False):
                say(f"repository {args.owner}/{args.repo} is still public; trying again to make it private")
                pstatus, pinfo = api("PATCH", f"{API}/repos/{args.owner}/{args.repo}",
                                     args.token, {"private": True})
                if pstatus == 200:
                    say(f"repository {args.owner}/{args.repo} is now private")
                else:
                    print(f"warning: could not make the repository private ({pstatus}): "
                          f"{pinfo.get('message')}", file=sys.stderr)
        # Clean up other files if requested (after successful upload)
        if args.clean:
            clean_other_files(args, say)
        return 0

    print(f"error: upload failed ({status}): {result.get('message')}", file=sys.stderr)
    return 1


def clean_other_files(args, say_func):
    """Delete all files in the repository except vpn-servers.txt."""
    list_url = f"{API}/repos/{args.owner}/{args.repo}/contents"
    status, files = api("GET", list_url, args.token)
    
    if status != 200:
        say_func(f"warning: could not list repository contents ({status}): {files.get('message')}")
        return
    
    deleted_count = 0
    for file_info in files:
        # Skip directories and our target file
        if file_info.get("type") != "file" or file_info.get("name") == args.path:
            continue
        
        if args.dry_run:
            say_func(f"[dry-run] would delete: {file_info.get('path', file_info.get('name'))}")
            deleted_count += 1
            continue
        
        # Delete the file
        del_url = f"{API}/repos/{args.owner}/{args.repo}/contents/{urllib.parse.quote(file_info['path'])}"
        del_status, _ = api("DELETE", del_url, args.token, {
            "message": f"Remove old file: {file_info['name']}",
            "sha": file_info["sha"]
        })
        
        if del_status in (200, 204):
            say_func(f"deleted: {file_info['path']}")
            deleted_count += 1
        else:
            say_func(f"warning: failed to delete {file_info['path']} ({del_status})")
    
    if deleted_count > 0:
        say_func(f"cleaned up {deleted_count} old file(s)")


if __name__ == "__main__":
    sys.exit(main())
