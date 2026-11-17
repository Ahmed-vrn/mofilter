# Installing this skill on another machine

The whole skill travels as **one file**: `skill-vpn` (a bash script with an
embedded, compressed copy of this directory).

```bash
# 1. copy skill-vpn to the target machine, then:
chmod +x skill-vpn
./skill-vpn
```

That is the whole install. It does:

- unpacks `SKILL.md`, `scripts/`, `references/` into
  `~/.config/opencode/skills/vpn-list/`
- checks `python3` (>= 3.8); no third-party Python packages are needed
- writes `~/.config/vpn-list/github.json` (mode 600) with the GitHub target
- adds an hourly GitHub-sync job: `cron` if available, otherwise a
  `systemd --user` timer
- adds a menu entry and a `vpn-list` command in `~/.local/bin`
- verifies the install by compiling every script and running `run.py --help`

## Everyday use

```bash
vpn-list --single                      # ask for a source, test, write ~/Desktop/vpn-servers.txt
vpn-list --source 'URL' --single       # explicit subscription URL
vpn-list --links-file /tmp/links.txt --single
./skill-vpn --sync                     # push the result to GitHub now
./skill-vpn --sync --dry-run           # show what would be uploaded
./skill-vpn --status                   # install / config / schedule / last sync
./skill-vpn --uninstall                # remove everything (add --purge to delete the result file)
```

## GitHub target

Default: `Ahmed-vrn/vpn-servers`, branch `main`, file `vpn-servers.txt`.
Change it at install time:

```bash
./skill-vpn --repo OWNER/REPO --branch main --token ghp_xxx
```

The token is only needed for **uploading**. Anyone can download the list
without a token from:
`https://raw.githubusercontent.com/Ahmed-vrn/vpn-servers/main/vpn-servers.txt`

If the repository does not exist yet, create it first (or let the sync do it):

```bash
python3 ~/.config/opencode/skills/vpn-list/scripts/github_sync.py --create-repo --public
```

## Tuning a run

| Variable | Default | Meaning |
|---|---|---|
| `VPN_PASSES` | 3 | connectivity rounds per server |
| `VPN_KEEP` | 2 | rounds a server must pass to be kept |
| `VPN_FETCH_TIMEOUT` | 25 | seconds per subscription request |
| `VPN_FETCH_RETRIES` | 1 | retries per subscription |
| `VPN_FETCH_WORKERS` | 12 | subscriptions fetched in parallel |

## Security note

The token is stored in plain text in `~/.config/vpn-list/github.json`
(mode 600). If the token has ever been shared, pasted in a chat, or committed
to a repository, revoke it at <https://github.com/settings/tokens> and install
again with `./skill-vpn --token NEW_TOKEN`. Prefer a fine-grained token limited
to that single repository with *Contents: read and write*.
