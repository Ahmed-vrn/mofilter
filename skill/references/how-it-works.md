# How vpn-list works

## Files

```
scripts/
  run.py            one-shot pipeline (entry point, files only)
  fetch.py          fetch daily source list + subscriptions -> links.txt
  sources_ru.py     Russia-first source registry + health probe + GitHub discovery
  retest.py         connectivity test (sing-box + Xray) + throttling stage
  links2sb.py       share-link -> sing-box outbound converter
  enrich.py         geolocation / country annotation (cached)
  clash_build.py    build clash.yaml + clash_simple.yaml
  install_cores.sh  download sing-box + Xray for the current OS/arch
  daily_update.sh   scheduled run: refresh + backup/restore guard + bundle (+ Throne sync)
  build_bundle.sh   assemble the importable bundle (refuses an empty one)
  throne_sync.py    optional: import the stable list into a Throne/Nekoray DB
  common.py         shared paths + configuration
references/
  how-it-works.md
  carrier-profiles.md
  whitelist-sni.md
  throttling-detection.md
```

Outputs go to `VPN_DATA` (default `~/.local/share/vpn-list/`):

| File | Meaning |
| --- | --- |
| `links.txt` | every link extracted from every subscription |
| `working_all.txt` | links that passed ≥ KEEP rounds |
| `working_unique.txt` | same, one server per host:port |
| `working_stable.txt` | links that passed ALL rounds (3/3) |
| `working_stable_unique.txt` | **the merged working list** (main output) |
| `working_stable_base64.txt` / `working_unique_base64.txt` | base64 subscription form |
| `working_by_country.txt` | stable list sorted/annotated by country |
| `countries.json` | link -> country code |
| `working_throttled.txt` / `working_unstable.txt` | excluded by the throttling stage |
| `carrier_report.json` | per-run stats |
| `source_health.json` | last fetch: every subscription, its link count and error |
| `sources_ru_verified.txt` / `sources_ru_discovered.txt` | Russia source registry cache |
| `sources_ru_report.json` | probe report (links + RU-SNI share per source) |
| `clash.yaml` / `clash_simple.yaml` | Clash/Mihomo configs of the stable servers |

## Pipeline

1. **fetch** — re-download the source list, then every subscription, decode
   base64 bodies, follow one level of URL indirection, extract share-links.
   Extraction accepts links at any position (markdown, JSON, HTML, YAML-like
   lists) and strips wrapping quotes/punctuation. The original default lists
   are extended with the verified Russia registry and a bounded GitHub
   discovery cache; dead sources are recorded but never abort the run.
2. **filter** (Russia) — drop links the cores cannot build (missing host,
   port, uuid) and links whose SNI is not acceptable for the chosen carrier
   profile. When only a slice is tested, links with a Russian whitelist SNI are
   ordered first.
3. **connectivity test** — non-`xhttp` links run in a single sing-box instance
   exposing a Clash API; each server is probed with
   `GET /proxies/{tag}/delay?url=...`. `xhttp`/`splithttp` links run in Xray
   with one local SOCKS inbound per server and are probed with
   `curl -x socks5h://... -w %{http_code}`. Success = HTTP 204 from
   `generate_204` (gstatic, then cloudflare fallback). Kept when it succeeds in
   at least `KEEP` of `PASSES` rounds; "stable" means all rounds.
4. **confirmation** — every link that won at least one round is re-tested in
   small batches (≤120 links, 32 workers). A single instance holding thousands
   of outbounds loses packets and reports false failures, so this low-load pass
   is what decides the stable list. `--only-kept` reuses `links.txt` and
   `counts.json` and runs only this step, to salvage a previous run.
5. **throttling** (optional) — candidates that passed connectivity are measured
   for throughput (download through the proxy) and sustained stability; slow or
   flaky servers go to `working_throttled.txt` / `working_unstable.txt` and are
   excluded from the stable output. See `throttling-detection.md`.
6. **enrich** — resolve hosts and geolocate with ip-api (cached in
   `geo_cache.json`); write `working_by_country.txt` and `countries.json`.
7. **Clash** — build `clash.yaml` (with Russia split routing: RU domains direct,
   everything else proxied) and `clash_simple.yaml` (plain global routing).

## Using the result

Import `working_stable_unique.txt` (or its base64 form) as a subscription in any
client, or load `clash.yaml` / `clash_simple.yaml` in a Clash/Mihomo-based
client. Nothing in this skill modifies an installed application.

**Optional client import.** `daily_update.sh` can push the fresh stable list into
one group of a Throne/Nekoray database when `VPN_THRONE_SYNC=1` (set in the
scheduled unit). `throne_sync.py` replaces that group's profiles, backs up the DB
first, and refuses to run while the client is open — so an open app is never
corrupted and the next run simply catches up.
