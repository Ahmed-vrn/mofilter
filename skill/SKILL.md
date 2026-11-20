---
name: VPN Working List
description: Ask the user for a subscription list or server links, test which servers really work, and merge the working ones into a single file on the Desktop (~/Desktop/vpn-servers.txt), deleting the previous result first. Use when the user wants to refresh/rebuild/re-test a VPN server list, get "only the servers that actually work", or produce one importable list. App-agnostic (never touches installed apps). Includes a Russia mobile edition: carrier profiles (MTS, Megafon, Beeline, Tele2), Russian whitelist SNI validation, TSPU silent-throttling detection, and Clash split routing.
---

# VPN Working List

Builds **one clean list of VPN servers that actually work** from a subscription
list the user supplies. It is app-agnostic: the output is a normal
subscription/links file you can import into any VPN client (v2rayNG, Hiddify,
NekoBox, Clash, …). It never touches any installed application.

## MANDATORY: ask for the source every time

Before running anything, **ask the user for the subscription list / servers**.
Never reuse a URL from a previous conversation, and never silently run with the
built-in default. Accept any of:

- one or more **subscription URLs** (or a URL to a sources list),
- a **local file** containing subscriptions or share-links,
- **pasted share-links** (`vless://…`, `vmess://…`, `ss://…`, …).

Only if the user says "no source / use the default", fall back to the daily
`sources.txt`. Keep the question short, e.g.:
«أرسل رابط الاشتراك (أو قائمة الاشتراكات)، أو الصق روابط السيرفرات، أو مسار ملف.»

## What it leaves behind

Exactly **one file on the Desktop**: `~/Desktop/vpn-servers.txt` — the merged
working servers. The previous result is **deleted before every run** (using
`--single` implies cleanup). Nothing else is written to the Desktop.

## When to use

- The user wants to refresh / re-test free subscriptions.
- The user wants "only the servers that actually work, all merged into one".
- The user wants a portable merged subscription file or a Clash config.
- The user is on a **Russian mobile network** and wants servers that survive
  TSPU (use `--extra-sources --carrier <mts|megafon|beeline|tele2>`).

## Workflow

```bash
# normal run: exactly one file on the Desktop, old result deleted first
python3 scripts/run.py --single

# user pasted share-links or gave a file of links
python3 scripts/run.py --links-file /tmp/links.txt --single

# user gave a source-list URL or a local file of subscription URLs
python3 scripts/run.py --source 'URL_OR_FILE' --single

# quick trial on the first 400 links
python3 scripts/run.py --source 'URL_OR_FILE' --single --limit 400

# Russia mobile edition
python3 scripts/run.py --source 'URL_OR_FILE' --single --extra-sources --carrier megafon
python3 scripts/run.py --source 'URL_OR_FILE' --single --carrier mts --throttle

# Russia-first sources: re-check the curated lists and discover fresh GitHub ones
python3 scripts/sources_ru.py --refresh --discover
python3 scripts/run.py --single --refresh-sources           # same, inside a run
python3 scripts/run.py --single --deep-sources              # + very large lists

# reuse the previous run (no fetch)
python3 scripts/run.py --skip-fetch --single
python3 scripts/run.py --only-kept --single      # confirm last survivors only

# Optional: push the stable list into a Throne/Nekoray DB (app must be closed)
python3 scripts/throne_sync.py --dry-run         # preview only
python3 scripts/throne_sync.py                   # import (backs up the DB first)
```

- `--single [FILE]` → write the final list to `~/Desktop/vpn-servers.txt`
  (or `FILE`) and **delete the old Desktop result(s) first**.
- `--clean` → delete the old Desktop results without the one-file output.
- `--links-file FILE` → test the links in `FILE` directly (skips fetching).

1. Reads the **source the user supplied** (URL, local file, or pasted links)
   fresh on every run (no caching), extracts the share-links. Links wrapped in
   markdown / JSON / HTML / base64 are all understood.
1b. Adds the **Russia-first registry** from `sources_ru.py`: the original
   default lists are kept untouched, plus verified GitHub sources
   (`sources_ru_verified.txt`) and a small daily GitHub discovery cache
   (`sources_ru_discovered.txt`, bounded to a handful of high-Russia-share
   files). `--deep-sources` additionally pulls the very large general lists.
   A source that fails is logged in `source_health.json` and never stops the run.
2. (Russia) optionally filters links by **carrier SNI rules** and adds extra
   Russia-focused lists.
3. Tests every link by actually routing traffic through it (`sing-box` for
   normal links, `Xray` for `xhttp`), `--passes` rounds each, keeping those that
   work at least `--keep` times.
4. **Confirms the survivors** in small batches under low load. Testing thousands
   of outbounds at once produces false negatives on a crowded link; the
   confirmation pass re-tests every link that passed a round and is what makes
   the stable list trustworthy. `--only-kept` reuses `links.txt` + `counts.json`
   and skips straight to this step (fast salvage of a previous run).
5. (Russia) optionally detects **silent throttling**: throughput and sustained
   stability are measured per candidate and slow/unstable servers are moved to
   `working_throttled.txt` / `working_unstable.txt`.
6. Writes the merged lists, geolocates them, and (unless `--single`) builds Clash
   configs; with `--single` only `~/Desktop/vpn-servers.txt` is left on the
   Desktop.

## Output files

**Default (one-file mode, `--single`):** only
`~/Desktop/vpn-servers.txt` — the merged working servers. Any previous Desktop
result is deleted first.

The pipeline also writes its working files to the data dir
(`~/.local/share/vpn-list/`, not the Desktop):

| File | Meaning |
| --- | --- |
| `working_stable_unique.txt` | **the merged working list** (one server per host) — import this |
| `working_stable_base64.txt` | same list as a base64 subscription |
| `working_stable.txt` | all links that passed every round (may repeat a server) |
| `working_all.txt` / `working_unique.txt` | links that passed ≥ `--keep` rounds |
| `working_unique_base64.txt` | the ≥`--keep` list as base64 |
| `working_by_country.txt` + `countries.json` | stable list sorted/annotated by country |
| `working_throttled.txt` | connected but throttled (excluded from the stable list) |
| `working_unstable.txt` | failed the sustained test (excluded from the stable list) |
| `carrier_report.json` | per-run stats + measured throughput |
| `source_health.json` | per-subscription result of the last fetch (links/new/error) |
| `sources_ru_verified.txt` | curated Russia sources that answered (rewritten by `--refresh`) |
| `sources_ru_discovered.txt` | GitHub sources found automatically (24h cache, bounded) |
| `sources_ru_report.json` | full probe report: links, RU-SNI share, errors |
| `clash.yaml` | Clash/Mihomo config of the stable servers, with Russia split routing |
| `clash_simple.yaml` | same proxies, plain global routing (no split) |

## Russia-first source registry

`sources_ru.py` is the single place that decides which Russia subscriptions
are worth fetching. The original lists stay in `common.DEFAULT_SOURCES`; the
registry adds verified ones next to them.

| Tier | Content | When |
| --- | --- | --- |
| core | ~25 curated GitHub/GitVerse lists (whitelist, mobile, CIDR) | every run |
| discovered | newest GitHub repos on the Russia topics, probed and capped (~1200 links, ≥15% RU SNI) | once per 24h, automatic |
| deep | very large mixed lists (thousands of links), including the
`whoahaow/rjsxrd` whitelist-bypass feed (vless + ss + hysteria2, hourly) | `--deep-sources` / `VPN_DEEP=1` / the app's "مصادر عميقة" switch |

```bash
python3 scripts/sources_ru.py --list                 # show curated + deep
python3 scripts/sources_ru.py --refresh              # health check -> verified file
python3 scripts/sources_ru.py --discover --force     # new GitHub sources now
python3 scripts/sources_ru.py --refresh --discover   # both
```

Selection rules for discovered sources: a file must answer, carry at least 5
links, be reasonably small (≤800 links) and have a visible share of **Russian
whitelist SNI** domains (≥15% under 300 links, ≥35% above). This keeps a
generic 4 000-link list from drowning a Russia-only run.

Links are also pre-validated before testing (impossible host/port/uuid combos
are dropped) and, when `--limit` is used, ordered with Russian-whitelist SNI
first — so a 200-link trial tests the useful 200, not an alphabetical slice.

## Requirements

- `python3`, `curl` (plus `tar`/`unzip` support).
- The cores (sing-box ~80 MB, Xray ~35 MB) are downloaded automatically on the
  first run into `<data>/bin/`. They are **not** bundled with the skill.

## Configuration (environment variables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `VPN_SOURCE` | the daily GitHub `sources.txt` | source-list URL or local file |
| `VPN_SINGLE_OUT` | `~/Desktop/vpn-servers.txt` | target of `--single` |
| `VPN_DATA` | `~/.local/share/vpn-list` | data / output dir |
| `VPN_EXTRA` | `<data>/extra_sources.txt` | extra subscription URLs (one per line) |
| `VPN_DEEP` | off | also fetch the very large general lists |
| `VPN_SOURCES_TTL` | `86400` | seconds before the GitHub discovery cache is refreshed |
| `VPN_SOURCE_TIMEOUT` | `20` | seconds per source during a health probe |
| `VPN_PASSES` / `VPN_KEEP` | `3` / `2` | test rounds / rounds needed to keep |
| `VPN_CARRIER` | `auto` | `mts` `megafon` `beeline` `tele2` `auto` |
| `VPN_THROTTLE` | off | force silent-throttling detection |
| `VPN_THROTTLE_KBPS` | `50` | throttled below this KB/s (Megafon profile: 80) |
| `VPN_THROTTLE_TEST_SIZE` | `100` | throughput test size in KB |
| `VPN_SUSTAINED_SECONDS` | `30` | sustained-test duration (seconds) |
| `VPN_GEO_CACHE` | on | cache geolocation in `geo_cache.json` |
| `VPN_MIN_STABLE` | `1` | min stable servers for `daily_update.sh` to accept a run |
| `VPN_THRONE_SYNC` | off | set `1` to import the fresh list into Throne after a run |
| `VPN_THRONE_GROUP` | `شغّال ✅` | target group name in the client DB |
| `VPN_THRONE_DB` | auto-detected | explicit path to `throne.db` |
| `VPN_THRONE_BACKUP_DIR` | `<data>/throne-backups` | where DB backups are kept (last 14) |

Throttling is enabled automatically when a specific carrier is chosen, or with
`--throttle`; disable it with `--no-throttle`.

## Optional: import into a client (Throne / Nekoray)

The skill is **app-agnostic** and normally never touches an installed app. If you
want the freshly tested servers to appear in **Throne** (or a Nekoray-style
client) automatically, `scripts/throne_sync.py` writes them into one group:

- Replaces the contents of the target group (default `شغّال ✅`) with the current
  `working_stable_unique.txt`, named `🇽🇽 CC-n` from `countries.json`.
- **Refuses to run while the client is running** (close it first, or `--force`),
  and **backs up the DB** (db + `-wal`/`-shm`) before every change.
- `--dry-run` previews; `--db`, `--group`, `--list`, `--countries` override paths.
- Enable it for the scheduler with `VPN_THRONE_SYNC=1` (already set in the
  `vpn-list.service` unit on this machine). If the client is open at 06:00 the
  sync simply skips and the next run picks it up.

## Publishing the result (optional)

`scripts/github_sync.py` uploads `~/Desktop/vpn-servers.txt` to a GitHub
repository, so the same list can be imported elsewhere by URL. Standard library
only — no `requests`, no pip.

```bash
python3 scripts/github_sync.py --dry-run   # preview, no write
python3 scripts/github_sync.py             # upload only if content changed
```

Settings come from `~/.config/vpn-list/github.json` (or the environment:
`GITHUB_TOKEN`, `VPN_GITHUB_OWNER`, `VPN_GITHUB_REPO`, `VPN_GITHUB_BRANCH`,
`VPN_GITHUB_PATH`). The single-file installer `skill-vpn` writes that config and
adds an hourly cron entry that keeps the repository in sync.

## Important notes

- **Always ask for the source first.** Never reuse an older URL and never run
  with the built-in default unless the user explicitly says so.
- **One file only:** use `--single` so the result is just
  `~/Desktop/vpn-servers.txt`. It is deleted (together with the old Desktop
  outputs) before every run, so there is never a stale result.
- A full run tests thousands of servers and can take **15–40 minutes**
  (longer with throttling). Tell the user before starting; use `--limit` for a
  quick trial.
- **Safe daily refresh:** `scripts/daily_update.sh` backs up the current output
  before running and, if the new run yields fewer than `VPN_MIN_STABLE` stable
  servers (default 1), restores the backup and keeps the previous bundle — so a
  bad night can never wipe a good list. `scripts/build_bundle.sh` likewise
  refuses to build an empty bundle. The scheduled task is separate from the
  interactive one-file workflow.
- The carrier profiles and SNI whitelist are best-effort guidance, not a
  guarantee; see `references/`.

## Tuning

| Variable | Default | Meaning |
|---|---|---|
| `VPN_PASSES` | 3 | connectivity rounds per server |
| `VPN_KEEP` | 2 | rounds a server must pass to be kept |
| `VPN_FETCH_TIMEOUT` | 25 | seconds per subscription request |
| `VPN_FETCH_RETRIES` | 1 | retries per subscription |
| `VPN_FETCH_WORKERS` | 12 | subscriptions fetched in parallel |

Subscriptions are fetched concurrently, so one dead host costs one timeout
instead of blocking every other source.

## Reference files

- `references/how-it-works.md` — pipeline and testing method.
- `references/carrier-profiles.md` — per-carrier reality/xhttp/SNI behaviour.
- `references/whitelist-sni.md` — Russian whitelist SNI domains.
- `references/throttling-detection.md` — how silent throttling is detected.
