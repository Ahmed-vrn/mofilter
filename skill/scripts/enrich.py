#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geolocate kept servers (with cache) and annotate them by country."""
import concurrent.futures as cf
import json
import os
import socket
import sys
import time
import urllib.request
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402


def ccflag(cc):
    if not cc or len(cc) != 2 or not cc.isalpha():
        return ''
    return chr(0x1F1E6 + ord(cc[0].upper()) - 65) + chr(0x1F1E6 + ord(cc[1].upper()) - 65)


def _host_of(link):
    if link.startswith('vmess://'):
        import base64
        try:
            b = link[8:]
            j = json.loads(base64.b64decode(b + '=' * (-len(b) % 4)).decode('utf-8', 'ignore'))
            return j.get('add')
        except Exception:
            return None
    return urlparse(link).hostname


def _resolve(host):
    if not host:
        return None
    try:
        socket.inet_aton(host)
        return host
    except Exception:
        try:
            return socket.gethostbyname(host)
        except Exception:
            return None


def load_cache():
    if not common.GEO_CACHE or not os.path.exists(common.GEO_CACHE_FILE):
        return {}
    try:
        return json.load(open(common.GEO_CACHE_FILE, encoding='utf-8'))
    except Exception:
        return {}


def save_cache(cache):
    if not common.GEO_CACHE:
        return
    try:
        json.dump(cache, open(common.GEO_CACHE_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
    except Exception:
        pass


def main(links=None):
    if links is None:
        links = [l.strip() for l in open(common.STABLE_UNIQUE, encoding='utf-8') if l.strip()]

    cache = load_cache()
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        resolved = list(ex.map(_resolve, [_host_of(l) for l in links]))
    ipmap = {l: ip for l, ip in zip(links, resolved)}
    ips = sorted({ip for ip in resolved if ip})

    todo = [ip for ip in ips if ip not in cache]
    for i in range(0, len(todo), 100):
        batch = [{'query': ip} for ip in todo[i:i + 100]]
        req = urllib.request.Request('http://ip-api.com/batch?fields=query,country,countryCode',
                                     data=json.dumps(batch).encode(),
                                     headers={'Content-Type': 'application/json'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=25) as r:
                    for e in json.loads(r.read().decode()):
                        cache[e['query']] = [e.get('countryCode') or '??', e.get('country') or 'Unknown']
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    print('  تحذير: فشل تحديد الدول:', e)
        time.sleep(4)
    save_cache(cache)

    rows = []
    for l in links:
        ip = ipmap.get(l)
        cc, country = cache.get(ip, ('??', 'Unknown')) if ip else ('??', 'Unknown')
        rows.append((cc, country, l, ip))
    rows.sort(key=lambda x: (x[0], x[1]))

    from collections import Counter
    print('  الدول:', dict(Counter(cc for cc, _, _, _ in rows)))

    names = {}
    with open(common.BY_COUNTRY, 'w', encoding='utf-8') as f:
        for cc, country, l, ip in rows:
            names[cc] = names.get(cc, 0) + 1
            base = l.split('#', 1)[0]
            f.write(f'{base}#{ccflag(cc)}{cc}-{names[cc]}\n')

    json.dump({l: cc for cc, _, l, _ in rows}, open(common.COUNTRIES, 'w', encoding='utf-8'),
              ensure_ascii=False)
    return rows
