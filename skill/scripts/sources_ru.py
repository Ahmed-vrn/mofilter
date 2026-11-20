#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Russia-first source registry, health check and GitHub discovery.

The skill keeps its original source lists untouched.  This module adds a
second, verified layer on top of them:

  core   small, frequently-updated lists that are known to target Russian
         whitelist / mobile networks (always fetched).
  deep   very large general lists (thousands of links).  They are only used
         with --deep-sources, because testing them all takes hours.
  github optional discovery: the newest repositories tagged for Russia are
         scanned for subscription files, probed, and cached for a day.

Everything is standard library only.  The result is a plain list of URLs:

    <data>/sources_ru_verified.txt    curated core, refreshed by --refresh
    <data>/sources_ru_discovered.txt  auto-discovered GitHub sources (24h TTL)
    <data>/sources_ru_report.json     per-source health (links, RU share, error)

Usage
-----
    python3 sources_ru.py --list
    python3 sources_ru.py --refresh             # probe curated sources
    python3 sources_ru.py --discover            # find new GitHub sources (24h cache)
    python3 sources_ru.py --refresh --discover  # both
    python3 sources_ru.py --discover --force    # ignore the 24h cache
"""
from __future__ import annotations

import base64
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

VERIFIED = os.path.join(common.DATA, "sources_ru_verified.txt")
DISCOVERED = os.path.join(common.DATA, "sources_ru_discovered.txt")
REPORT = os.path.join(common.DATA, "sources_ru_report.json")
GITHUB_CFG = os.path.join(common.HOME, ".config", "vpn-list", "github.json")

# 24 hours: discovery is cheap but not free (GitHub API + ~20 downloads).
TTL = int(os.environ.get("VPN_SOURCES_TTL", "86400"))
PROBE_TIMEOUT = float(os.environ.get("VPN_SOURCE_TIMEOUT", "20"))
PROBE_WORKERS = int(os.environ.get("VPN_SOURCE_WORKERS", "10"))

# --------------------------------------------------------------------------
#  Curated sources (verified 2026-11-17).  Names are only for logs.
# --------------------------------------------------------------------------
CORE = [
    ("igareck-mobile", "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt"),
    ("igareck-black-mobile", "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt"),
    ("igareck-white-cidr", "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt"),
    ("igareck-white-cidr-checked", "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt"),
    # The top-level WHITE-SNI file is empty from time to time; this export is
    # regenerated with the same nodes and stays populated.
    ("igareck-white-sni-export", "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/HEAD/Export/v2rayN_PC/WHITE-SNI-RU-all-v2rayN.txt"),
    ("wlunlocker-all", "https://raw.githubusercontent.com/wlunlocker/vpn-configs/HEAD/whitelist_all.txt"),
    ("wlunlocker-cidr1", "https://raw.githubusercontent.com/wlunlocker/vpn-configs/HEAD/whitelist_cidr1_ru.txt"),
    ("wlunlocker-cidr2", "https://raw.githubusercontent.com/wlunlocker/vpn-configs/HEAD/whitelist_cidr2_ru.txt"),
    ("prometheus-white", "https://raw.githubusercontent.com/vladvarp/Prometheus/refs/heads/main/WhiteList/vless.txt"),
    ("steklo-whitelist", "https://raw.githubusercontent.com/OceaniaVPN/StekloVPN/main/configs/whitelist.txt"),
    ("zieng2-lite", "https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_lite.txt"),
    ("zieng2-universal", "https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_universal.txt"),
    ("aetris-white-lite", "https://raw.githubusercontent.com/flaafix/AetrisVPN-white-list-lite/refs/heads/main/AetrisVPN.txt"),
    ("flat447-lite", "https://raw.githubusercontent.com/FLAT447/v2ray-lists/HEAD/WHITE_LITE.txt"),
    ("avatars-ru", "https://raw.githubusercontent.com/aviamastersgh/vpn-free-russia/HEAD/ru_configs.txt"),
    ("harvester-ping", "https://raw.githubusercontent.com/luxxuria/harvester/HEAD/ping_tested.txt"),
    ("harvester-speed", "https://raw.githubusercontent.com/luxxuria/harvester/HEAD/speed_tested.txt"),
    ("goose-balanced", "https://raw.githubusercontent.com/gooseteam-hackers/GooseVPN/refs/heads/main/configs/balanced.txt"),
    ("goose-plus", "https://raw.githubusercontent.com/gooseteam-hackers/GooseVPN/refs/heads/main/configs/plus.txt"),
    ("kizyak-mobile", "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta6.txt"),
    ("vlessfo-working", "https://sub.vlessfo.ru/vlessforu/working_configs.txt"),
    ("akres-whitelist", "https://vpn.akres.fun/bwl"),
    ("gitverse-272", "https://gitverse.ru/api/repos/272/wl/raw/branch/master/whitelist"),
    ("gitverse-pizduk-wl", "https://gitverse.ru/api/repos/Pizduk/PizdukVPN/raw/branch/master/WlSubPiz.txt"),
    ("gitverse-pizduk-auto", "https://gitverse.ru/api/repos/Pizduk/PizdukVPN/raw/branch/master/WLAutoPiz.txt"),
]

# Large general lists: rich in links, but only a small share are Russia
# whitelist nodes.  Opt in with --deep-sources.
DEEP = [
    ("subzio-alive", "https://raw.githubusercontent.com/Subzio/subzio/HEAD/ALIVE.txt"),
    ("subzio-whitelist", "https://raw.githubusercontent.com/Subzio/subzio/HEAD/WHITE_LIST_PROXY_COLLECTION.txt"),
    ("histeenn-sub", "https://raw.githubusercontent.com/histeenn/VLESS-PO-GRIBI/HEAD/deploy/sub.txt"),
    ("flarefeed-vless", "https://raw.githubusercontent.com/svinakraft-maker/FlareFeed/HEAD/public/vless.txt"),
    ("flarefeed-top500", "https://raw.githubusercontent.com/svinakraft-maker/FlareFeed/HEAD/public/Top500.txt"),
    ("avatars-all", "https://raw.githubusercontent.com/aviamastersgh/vpn-free-russia/HEAD/all_configs.txt"),
    ("flat447-full", "https://raw.githubusercontent.com/FLAT447/v2ray-lists/HEAD/WHITE_FULL.txt"),
    # Whitelist-bypass feed for Russian mobile networks (vless + ss +
    # hysteria2, refreshed hourly).  Measured 2026-11-20: 474 usable
    # links, ~25% of a 30-link sample survived two sing-box passes.
    ("rjsxrd-bypass", "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/githubmirror/bypass/bypass-all.txt"),
]

# GitHub discovery: repositories carrying these topics are scanned for files
# that look like subscriptions.  Keep the list short — each topic is one API
# request and every repository tree is another.
TOPICS = ["free-vpn-russia", "vpn-russia", "russia-vpn", "vless-reality"]

FILE_HINT = re.compile(
    r"(whitelist|white[_-]?(list|sni|cidr)|(^|[/_.-])wl([/_.-]|$)|mobile|lite|vless|sub|config|all[_-]?configs)", re.I)
FILE_SKIP = re.compile(r"(\.png|\.jpg|\.jpeg|\.gif|\.svg|\.mmdb|\.db|\.log|readme|license|\.ya?ml$|\.json$|\.go$|\.py$|\.rs$|\.md$)", re.I)

SCHEMES = ("vless", "vmess", "trojan", "ss", "ssr", "hy2", "hysteria2", "hysteria", "tuic")


# --------------------------------------------------------------------------
#  Hardened URL helpers
# --------------------------------------------------------------------------
def norm_url(url):
    """Trim labels/quotes and turn a GitHub blob link into its raw form."""
    url = (url or "").strip().strip("'\"").split()[0] if (url or "").strip() else ""
    if not url.startswith(("http://", "https://")):
        return ""
    url = url.replace("&amp;", "&")
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", url)
    if m:
        url = "https://raw.githubusercontent.com/%s/%s/%s/%s" % m.groups()
    return url.split("#", 1)[0] if "raw.githubusercontent.com" in url else url


def http_get(url, timeout=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": common.USER_AGENT,
        "Cache-Control": "no-cache",
        "Accept": "*/*",
    })
    with urllib.request.urlopen(req, timeout=timeout or PROBE_TIMEOUT) as r:
        return r.read()


def read_urls(path):
    """URL list file -> [url].  '#' lines are comments, labels are ignored."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                u = norm_url(line)
                if u and u not in out:
                    out.append(u)
    except OSError:
        pass
    return out


def write_urls(path, urls, header=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        if header:
            fh.write("\n".join("# " + h for h in header.splitlines()) + "\n")
        fh.write("\n".join(urls) + ("\n" if urls else ""))
    os.replace(tmp, path)


def is_fresh(path, ttl=None):
    try:
        return (time.time() - os.path.getmtime(path)) < (TTL if ttl is None else ttl)
    except OSError:
        return False


# --------------------------------------------------------------------------
#  Probing a single source
# --------------------------------------------------------------------------
def _sni_of(link):
    try:
        if link.startswith("vmess://"):
            b = link[8:]
            data = json.loads(base64.b64decode(b + "=" * (-len(b) % 4)).decode("utf-8", "ignore"))
            return str(data.get("sni") or data.get("host") or "")
        q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query, keep_blank_values=True)
        q = {k.lower(): v[0] for k, v in q.items()}
        return q.get("sni") or q.get("peer") or q.get("host") or q.get("servername") or ""
    except Exception:
        return ""


def is_ru_sni(sni):
    s = (sni or "").lower().strip(".")
    if not s:
        return False
    return any(s == h or s.endswith("." + h) for h in common.RU_SNI_HINTS)


def probe(url, timeout=None):
    """Download one source and measure how useful it is."""
    t0 = time.time()
    res = {"url": url, "ok": False, "links": 0, "ru": 0, "bytes": 0,
           "error": "", "seconds": 0.0}
    try:
        raw = http_get(url, timeout)
        res["bytes"] = len(raw)
        text = raw.decode("utf-8", "ignore")
        # Reuse the skill's extractor (handles base64, markdown and JSON bodies).
        import fetch
        links = sorted(fetch.extract_links(text))
        res["links"] = len(links)
        res["ru"] = sum(1 for l in links if is_ru_sni(_sni_of(l)))
        res["ok"] = bool(links)
    except Exception as exc:  # noqa: BLE001 - reported in the table/report
        res["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:80])
    res["seconds"] = round(time.time() - t0, 1)
    return res


def probe_many(urls, workers=None):
    urls = list(dict.fromkeys(u for u in urls if u))
    results = []
    with cf.ThreadPoolExecutor(max_workers=max(1, workers or PROBE_WORKERS)) as ex:
        for res in ex.map(probe, urls):
            results.append(res)
    return results


def _short(url, width=72):
    """Readable one-line label for logs (drops the noisy raw prefix)."""
    label = url.replace("https://raw.githubusercontent.com/", "").replace("https://", "")
    return label if len(label) <= width else label[:width - 1] + "…"


def _score(res):
    # Russia-whitelist links first, then total links.
    return (min(res.get("ru", 0), 200), res.get("links", 0))


# --------------------------------------------------------------------------
#  Refresh (health check of curated + previously verified sources)
# --------------------------------------------------------------------------
def refresh(discover=False, deep=False, force=False, quiet=False):
    """Probe sources, rewrite the verified list, optionally discover new ones."""
    os.makedirs(common.DATA, exist_ok=True)
    sources = [(n, u) for n, u in (CORE + (DEEP if deep else []))]
    extras = read_urls(common.EXTRA)
    previous = read_urls(VERIFIED)
    discovered = read_urls(DISCOVERED)

    seen, urls = set(), []
    for _name, u in sources:
        if u not in seen:
            seen.add(u)
            urls.append(u)
    for u in previous + discovered + extras:
        if u not in seen:
            seen.add(u)
            urls.append(u)

    if not force and is_fresh(VERIFIED):
        if not quiet:
            print("  المصادر الموثّقة حديثة — لا حاجة لإعادة الفحص (VPN_SOURCES_TTL)", flush=True)
        urls = list(dict.fromkeys(read_urls(VERIFIED) + extras))
        results = None
    else:
        if not quiet:
            print("  فحص %d مصدرًا…" % len(urls), flush=True)
        results = probe_many(urls)

    if results is None:
        # Still allow discovery even when the health cache is fresh.
        if discover:
            github_discover(force=force, quiet=quiet)
        return read_urls(VERIFIED)

    alive = [r for r in results if r["ok"] and r["links"] >= 3]
    alive.sort(key=_score, reverse=True)
    keep = [r["url"] for r in alive]
    write_urls(VERIFIED, keep,
               "vpn-list — verified Russia sources\n"
               "checked: %s\n"
               "alive: %d of %d (>=3 links)\n"
               "regenerate: python3 sources_ru.py --refresh" % (
                   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                   len(alive), len(results)))
    try:
        dead = [{"url": r["url"], "error": r["error"], "links": r["links"]}
                for r in results if not (r["ok"] and r["links"] >= 3)]
        json.dump({"checked": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "alive": len(alive), "total": len(results),
                   "sources": sorted(results, key=_score, reverse=True),
                   "dead": dead},
                  open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except OSError:
        pass

    if not quiet:
        for r in sorted(results, key=_score, reverse=True):
            mark = "✔" if r["ok"] and r["links"] >= 3 else "✘"
            extra = ("%d رابطًا، روسي %d" % (r["links"], r["ru"])) if r["ok"] else r["error"]
            print("   %s %-62s %s" % (mark, _short(r["url"]), extra), flush=True)
        print("  صالح: %d/%d — الملف: %s" % (len(alive), len(results), VERIFIED), flush=True)

    if discover:
        github_discover(force=force, quiet=quiet)
    return keep


# --------------------------------------------------------------------------
#  GitHub discovery
# --------------------------------------------------------------------------
def _github_token():
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        return tok
    try:
        with open(GITHUB_CFG, encoding="utf-8") as fh:
            return str(json.load(fh).get("token") or "").strip()
    except Exception:
        return ""


def _api(url, token=""):
    req = urllib.request.Request(url, headers={
        "User-Agent": "vpn-list-sources",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _repo_files(repo, token):
    tree = _api("https://api.github.com/repos/%s/git/trees/HEAD?recursive=1" % repo, token)
    paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
    cands = []
    for p in paths:
        if FILE_SKIP.search(p) or not FILE_HINT.search(p):
            continue
        depth = p.count("/")
        weight = 0
        low = p.lower()
        if "white" in low or "wl" in low:
            weight += 5
        if "mobile" in low or "lite" in low:
            weight += 4
        if "vless" in low:
            weight += 3
        if low.endswith((".txt", ".conf")):
            weight += 2
        if depth == 0:
            weight += 2
        if "all_configs" in low:
            weight -= 3  # enormous mixed list, low Russia share
        cands.append((weight, -depth, p))
    cands.sort(reverse=True)
    out = []
    for _w, _d, p in cands[:2]:
        out.append("https://raw.githubusercontent.com/%s/HEAD/%s" % (repo, urllib.parse.quote(p)))
    return out


def github_discover(force=False, quiet=False, days=30, max_repos=12):
    """Find recently updated Russia repositories and probe their files."""
    if not force and is_fresh(DISCOVERED):
        if not quiet:
            print("  اكتشاف GitHub حديث — يُستخدم المخزّن (VPN_SOURCES_TTL)", flush=True)
        return read_urls(DISCOVERED)

    token = _github_token()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    repos, seen = [], set()
    api_errors = []

    for topic in TOPICS:
        q = urllib.parse.quote("topic:%s pushed:>%s" % (topic, since))
        try:
            data = _api("https://api.github.com/search/repositories"
                        "?q=%s&sort=updated&order=desc&per_page=10" % q, token)
        except Exception as exc:  # noqa: BLE001
            api_errors.append("%s: %s" % (topic, str(exc)[:60]))
            continue
        for item in data.get("items", []):
            full = item.get("full_name") or ""
            if not full or full in seen or item.get("archived"):
                continue
            seen.add(full)
            repos.append(full)

    if not quiet:
        print("  GitHub: فحص %d مستودعًا%s" % (
            min(len(repos), max_repos),
            "" if token else " (بلا توكن — حدّ الـ API أقل)"), flush=True)
        for err in api_errors:
            print("   ! GitHub API: %s" % err, flush=True)

    candidates = []
    for repo in repos[:max_repos]:
        try:
            candidates.extend(_repo_files(repo, token))
        except Exception:
            continue

    previous = read_urls(DISCOVERED)
    # The cache is fully regenerated: a source that stops being useful (or
    # turns into a huge mixed list) disappears after the next discovery run.
    known = set(previous) | set(p for _n, p in CORE) | set(p for _n, p in DEEP)
    fresh = [u for u in dict.fromkeys(candidates) if u not in known]
    results = probe_many(fresh[:30]) if fresh else []

    # A discovered source must be *useful for Russia*, not merely alive:
    # at least a handful of links and a visible share of Russian whitelist
    # SNIs.  Very large mixed lists are rejected unless half of them match.
    good = []
    for r in results:
        if not r["ok"] or r["links"] < 5:
            continue
        ratio = (r["ru"] / float(r["links"])) if r["links"] else 0.0
        if r["links"] <= 300 and r["ru"] >= 3 and ratio >= 0.15:
            good.append(r)
        elif 300 < r["links"] <= 800 and r["ru"] >= 10 and ratio >= 0.35:
            good.append(r)
    good.sort(key=lambda r: (r["ru"] / float(r["links"]), r["ru"]), reverse=True)

    # Bound the total: discovery must stay a supplement, not the whole run.
    accepted, budget = [], 1200
    for r in good:
        if r["links"] > budget:
            continue
        budget -= r["links"]
        accepted.append(r)
        if len(accepted) >= 8:
            break
    good = accepted
    accepted = [r["url"] for r in good]

    merged = list(dict.fromkeys(accepted))
    # Never let the cache grow without bound.
    merged = merged[:30]
    write_urls(DISCOVERED, merged,
               "vpn-list — auto-discovered Russia sources (GitHub)\n"
               "discovered: %s · new: %d · accepted: %d\n"
               "ttl: %d seconds · regenerate: python3 sources_ru.py --discover --force" % (
                   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                   len(fresh), len(accepted), TTL))
    if not quiet:
        for r in sorted(results, key=_score, reverse=True)[:12]:
            if r["ok"]:
                print("   %s %-62s %d رابطًا (روسي %d)" % (
                    "✔" if r in good else "·", _short(r["url"]), r["links"], r["ru"]), flush=True)
        print("  اكتشاف GitHub: +%d مصدرًا صالحًا (المجموع %d)" % (len(accepted), len(merged)), flush=True)
    return merged


# --------------------------------------------------------------------------
#  Helpers used by fetch.py / the web app
# --------------------------------------------------------------------------
def curated_urls(deep=False):
    urls = [u for _n, u in CORE]
    if deep:
        urls += [u for _n, u in DEEP]
    return urls


def cached_urls(deep=False, discover_if_stale=True):
    """URLs that should always take part in a run (core + caches)."""
    urls = curated_urls(deep)
    if discover_if_stale and not is_fresh(DISCOVERED):
        try:
            github_discover(quiet=True)
        except Exception:
            pass
    for path in (VERIFIED, DISCOVERED, common.EXTRA):
        urls += read_urls(path)
    out, seen = [], set()
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--list" in argv:
        print("core:")
        for n, u in CORE:
            print("  %-24s %s" % (n, u))
        print("deep (--deep-sources):")
        for n, u in DEEP:
            print("  %-24s %s" % (n, u))
        return 0
    res = refresh(discover="--discover" in argv, deep="--deep" in argv,
                  force="--force" in argv)
    if "--json" in argv:
        print(json.dumps({"verified": res, "report": REPORT}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
