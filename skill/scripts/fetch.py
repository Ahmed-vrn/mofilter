#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch the daily source list, then every subscription, and extract share-links.

The source file is re-downloaded on every run (no caching) because it is
updated daily with new subscription URLs. Subscription bodies are decoded from
base64 when needed, and one extra level of indirection is followed if a
subscription body is itself a list of URLs.

Besides the original source list, every run also includes the Russia-first
sources from ``sources_ru.py`` (curated + cached GitHub discovery).  The
original lists are never modified; they are simply extended.
"""
import base64
import concurrent.futures as cf
import html
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

SCHEMES = r'(?:vless|vmess|trojan|ss|ssr|hy2|hysteria2|hysteria|tuic)'
# Lines used to require the link at the very start of a line.  Real feeds
# wrap links in markdown (](vless://…)), JSON ("vless://…"), YAML lists and
# HTML, so the link is now matched anywhere in the body.
LINK_RE = re.compile(r'(?i)(' + SCHEMES + r'://[^\s"\'<>\\`\u200b]+)')
URL_RE = re.compile(r'https?://[^\s"\'<>\\`\u200b]+')
TRAILING = '.,;:!?)]}>"\'`'

HEALTH = os.path.join(common.DATA, 'source_health.json')


def http_get(url, timeout=None, retries=None):
    timeout = common.FETCH_TIMEOUT if timeout is None else timeout
    retries = common.FETCH_RETRIES if retries is None else retries
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': common.USER_AGENT,
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Accept': '*/*',
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            if attempt < retries:
                time.sleep(1.5 ** attempt)
    raise last


def http_text(url, timeout=None):
    # Local files are accepted anywhere a source URL is expected, so a user can
    # hand over a saved list of subscriptions (or the agent can drop pasted
    # links/sources into a temp file).
    path = os.path.expanduser(url)
    if os.path.isfile(path):
        with open(path, encoding='utf-8', errors='ignore') as f:
            return f.read()
    return http_get(url, timeout).decode('utf-8', 'ignore')


def maybe_b64(text):
    """Return decoded text if the body looks base64-encoded, else the input."""
    head = text[:400]
    if '://' in head:
        return text
    for cand in (text, re.sub(r'\s+', '', text)):
        try:
            dec = base64.b64decode(cand + '=' * (-len(cand) % 4)).decode('utf-8', 'ignore')
            if '://' in dec:
                return dec
        except Exception:
            pass
    return text


def clean_link(raw):
    """Remove wrappers/quotes and trailing punctuation from one share-link."""
    raw = html.unescape(raw or '').strip()
    raw = raw.lstrip('(["\'`').rstrip(TRAILING)
    if '://' not in raw:
        return ''
    scheme, rest = raw.split('://', 1)
    if not rest.strip():
        return ''
    # A link must not contain control characters after cleaning.
    return scheme.lower() + '://' + rest.strip()


def extract_links(text):
    text = maybe_b64(text)
    out = set()
    for m in LINK_RE.finditer(text):
        link = clean_link(m.group(1))
        if link:
            out.add(link)
    return out


def _from_index(path):
    """Read a URL list written by sources_ru.py (comments and labels ignored)."""
    urls = []
    try:
        with open(path, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                u = line.split()[0]
                if u.startswith('http'):
                    urls.append(u)
    except OSError:
        pass
    return urls


def _normalize(u):
    """GitHub blob links -> raw links; drop empty/non-http entries."""
    u = (u or '').strip()
    if not u.startswith(('http://', 'https://')):
        return ''
    m = re.match(r'https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)', u)
    if m:
        u = 'https://raw.githubusercontent.com/%s/%s/%s/%s' % m.groups()
    return u


def _ru_sources(deep=False):
    """Curated Russia sources + cached discovery (import guarded)."""
    try:
        import sources_ru
        return sources_ru.cached_urls(deep=deep)
    except Exception as e:  # noqa: BLE001 - the skill still works without it
        print(f'  ! تعذّر تحميل سجل المصادر الروسية: {e}', flush=True)
        return []


def source_urls(source_url):
    """Fetch the source list and return the subscription URLs to download."""
    print(f'  مصدر القائمة: {source_url}', flush=True)
    text = http_text(source_url)
    urls = []

    # Add URLs from the source file
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # each line is usually "<url> <optional label words>"
        for tok in line.split():
            if tok.startswith('http'):
                u = _normalize(tok)
                if u:
                    urls.append(u)
                break

    # Original defaults (kept exactly as they were) plus the Russia-first
    # registry: these are added whichever source the user picked.
    for url in common.DEFAULT_SOURCES:
        # entries may carry trailing label words ("... wLTE"); send only the URL
        u = _normalize(url.split()[0] if url.split() else url)
        if u:
            urls.append(u)

    for u in _ru_sources(deep=common.DEEP):
        urls.append(u)

    # Extra sources from the user's file (never overwritten by the app).
    if os.path.exists(common.EXTRA):
        for u in _from_index(common.EXTRA):
            urls.append(_normalize(u))

    # de-duplicate, keep order
    seen, out = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    if common.DEEP and len(out):
        print(f'  الوضع الموسّع: {len(out)} مصدرًا (يشمل القوائم الكبيرة)', flush=True)
    return out


def fetch_all(source_url=None, workers=None):
    common.ensure_dirs()
    source_url = source_url or common.SOURCE_URL
    subs = source_urls(source_url)
    print(f'  عدد الاشتراكات في القائمة: {len(subs)}', flush=True)

    # Subscriptions are independent, so fetch them concurrently: one slow or
    # dead host must not add its full timeout to every other host's wait.
    workers = common.FETCH_WORKERS if workers is None else workers
    results = [None] * len(subs)
    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(http_text, u): (i, u) for i, u in enumerate(subs)}
        for fut in cf.as_completed(futures):
            i, _u = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as e:  # noqa: BLE001 - reported below
                results[i] = e

    links = set()
    ok = fail = 0
    health = []
    for i, u in enumerate(subs):
        raw = results[i]
        if isinstance(raw, Exception):
            fail += 1
            health.append({'url': u, 'ok': False, 'links': 0, 'error': str(raw)[:120]})
            print(f'   ✗ فشل [{i:02d}] {u[:70]} ({raw})', flush=True)
            continue
        ok += 1
        if len(raw) < 4 * 1024 * 1024:
            try:
                with open(os.path.join(common.BODIES, f'{i:02d}.body'), 'w', encoding='utf-8') as f:
                    f.write(raw)
            except OSError:
                pass
        found = extract_links(raw)
        direct = len(found)
        # one level of indirection: a subscription that is itself a URL list
        if not found:
            for u2 in URL_RE.findall(raw)[:50]:
                u2 = _normalize(html.unescape(u2).rstrip(TRAILING))
                if not u2:
                    continue
                try:
                    found |= extract_links(http_text(u2))
                except Exception:
                    pass
                if found:
                    break
        new = found - links
        links |= found
        health.append({'url': u, 'ok': True, 'links': len(found), 'direct': direct,
                       'new': len(new)})

    try:
        json.dump({'time': time.strftime('%Y-%m-%dT%H:%M:%S'),
                   'sources': ok, 'failed': fail, 'links': len(links),
                   'detail': health},
                  open(HEALTH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except OSError:
        pass

    print(f'  اشتراكات ناجحة: {ok} | فاشلة: {fail} | روابط فريدة: {len(links)}', flush=True)
    if fail:
        print('  المصادر الفاشلة تُسجّل في source_health.json — لن تُوقف التشغيل', flush=True)

    with open(common.LINKS, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted(links)) + ('\n' if links else ''))
    return sorted(links)


def main():
    links = fetch_all()
    print('حُفظ:', common.LINKS)
    return links


if __name__ == '__main__':
    main()
