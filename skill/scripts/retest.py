#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test links by actually routing traffic through them.

Stage 1 - connectivity (always on):
    sing-box handles every protocol except xhttp/splithttp; those are tested
    with Xray. Each link is probed PASSES times and counted on success.

Stage 2 - silent throttling (optional, Russia edition): traffic is downloaded
    through each *candidate* proxy and measured. Links below the throughput
    threshold are reported as "throttled"; links that cannot sustain repeated
    requests are reported as "unstable".

Carrier profiles (mts/megafon/beeline/tele2) additionally validate the SNI of
Reality/TLS links against the Russian whitelist domains that survive TSPU.
"""
import base64
import concurrent.futures as cf
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402
from links2sb import link_to_outbound  # noqa: E402


CARRIER_PROFILES = {
    'megafon': {'requires_ru_sni': True,
                'allowed_sni': ['rutube.ru', 'vkvideo.ru', 'ozon.ru', 'kinopoisk.ru',
                                'wildberries.ru'] + list(common.RU_SNI_HINTS),
                'throttle_kbps': 80},
    'mts':     {'requires_ru_sni': True,
                'allowed_sni': ['sun6-21.userapi.com', 'web.max.ru', 'download.max.ru',
                                'calls.max.ru'] + list(common.RU_SNI_HINTS),
                'throttle_kbps': 50},
    'beeline': {'requires_ru_sni': False,
                'allowed_sni': ['yandex.ru', 'yandex.net', 'vk.com', 'mail.ru'] + list(common.RU_SNI_HINTS),
                'throttle_kbps': 50},
    'tele2':   {'requires_ru_sni': False,
                'allowed_sni': [],
                'throttle_kbps': 50},
    'auto':    {'requires_ru_sni': False,
                'allowed_sni': [],
                'throttle_kbps': 50},
}


# ------------------------- helpers ---------------------------------------
def hostport(u):
    try:
        if u.startswith('vmess://'):
            b = u[8:]
            j = json.loads(base64.b64decode(b + '=' * (-len(b) % 4)).decode('utf-8', 'ignore'))
            return (j.get('add'), int(j.get('port')))
        p = urlparse(u)
        return (p.hostname, p.port) if p.hostname and p.port else None
    except Exception:
        return None


def extract_sni(link):
    try:
        if link.startswith('vmess://'):
            b = link[8:]
            j = json.loads(base64.b64decode(b + '=' * (-len(b) % 4)).decode('utf-8', 'ignore'))
            return j.get('sni') or j.get('host') or ''
        p = urlparse(link)
        q = {k.lower(): v[0] for k, v in parse_qs(p.query, keep_blank_values=True).items()}
        return (q.get('sni') or q.get('servername') or q.get('peer') or q.get('host') or '')
    except Exception:
        return ''


def is_ru_sni(sni):
    """True when the SNI belongs to a domain seen in the Russian whitelists."""
    s = (sni or '').lower().strip('.')
    if not s:
        return False
    return any(s == h or s.endswith('.' + h) for h in common.RU_SNI_HINTS)


def rank_links(links):
    """Order links for testing: RU whitelist SNI first, then any SNI, then none.

    ``sorted`` is stable, so the original order is preserved inside a group.
    """
    def score(link):
        sni = extract_sni(link)
        if not sni:
            return 0
        return 2 if is_ru_sni(sni) else 1
    return sorted(links, key=score, reverse=True)


def usable_links(links):
    """Drop links the cores cannot build an outbound from (saves test time)."""
    good, bad = [], 0
    for link in links:
        low = link.lower()
        if 'xhttp' in low or 'splithttp' in low:
            good.append(link)          # tested by Xray
            continue
        if link_to_outbound(link, 'probe'):
            good.append(link)
        else:
            bad += 1
    if bad:
        print(f'  استُبعد لعدم صلاحية الصيغة: {bad}', flush=True)
    return good


def validate_sni(sni, carrier):
    if not sni:
        return {'valid': False, 'reason': 'no_sni'}
    allowed = CARRIER_PROFILES.get(carrier, CARRIER_PROFILES['auto']).get('allowed_sni', [])
    if not allowed:
        return {'valid': True, 'reason': 'any_sni', 'sni': sni}
    for a in allowed:
        if sni == a or sni.endswith('.' + a):
            return {'valid': True, 'reason': 'ru_whitelist', 'sni': sni}
    return {'valid': False, 'reason': 'foreign_sni', 'sni': sni}


def _http_ok(url, timeout=5):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': common.USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def detect_whitelist_environment():
    vk = _http_ok('https://vk.com', 5)
    goog = _http_ok('https://www.google.com', 5)
    return 'whitelist' if (vk and not goog) else 'blacklist'


def filter_links(links, carrier=None):
    """Drop malformed links and SNIs that do not match the carrier whitelist."""
    links = usable_links(links)
    carrier = carrier or common.CARRIER
    profile = CARRIER_PROFILES.get(carrier, CARRIER_PROFILES['auto'])
    requires = profile.get('requires_ru_sni', False)
    if carrier == 'auto':
        env = detect_whitelist_environment()
        print(f'  البيئة: {env}', flush=True)
        if env == 'whitelist':
            requires = True
            print('  بيئة القائمة البيضاء — يُفضّل SNI روسي', flush=True)
    if not requires:
        return links
    allowed = profile.get('allowed_sni', [])
    out, rejected = [], 0
    for l in links:
        sni = extract_sni(l)
        if not sni:
            rejected += 1
            continue
        if allowed and not any(sni == a or sni.endswith('.' + a) for a in allowed):
            rejected += 1
            continue
        out.append(l)
    if rejected:
        print(f'  استُبعد لعدم مطابقة SNI: {rejected}', flush=True)
    return out


def _wait_for_port(port, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.create_connection(('127.0.0.1', port), timeout=1)
            s.close()
            return True
        except Exception:
            time.sleep(0.5)
    return False


# ------------------------- sing-box phase --------------------------------
def phase_singbox(links, workers=64):
    conv = []
    for i, l in enumerate(links):
        o = link_to_outbound(l, f'p{i}')
        if o:
            conv.append({'link': l, 'out': o})
    print(f'  sing-box: قابلة للتحويل {len(conv)}', flush=True)

    n = 0
    while True:
        cfg = {'log': {'level': 'error'},
               'experimental': {'clash_api': {'external_controller': '127.0.0.1:19092'}},
               'outbounds': [x['out'] for x in conv]}
        path = os.path.join(common.WORK, 're_sb.json')
        json.dump(cfg, open(path, 'w'), ensure_ascii=False)
        r = subprocess.run([common.SB, 'check', '-c', path], capture_output=True, text=True)
        if r.returncode == 0:
            break
        m = re.search(r'outbound\[(\d+)\]', r.stderr)
        if not m:
            print('  check فشل:', r.stderr.strip()[:200])
            break
        del conv[int(m.group(1))]
        n += 1
    if n:
        print('  أُزيل غير صالح:', n, flush=True)

    cfg = {'log': {'level': 'error'},
           'experimental': {'clash_api': {'external_controller': '127.0.0.1:19091'}},
           'outbounds': [x['out'] for x in conv]}
    path = os.path.join(common.WORK, 're_big.json')
    json.dump(cfg, open(path, 'w'), ensure_ascii=False)
    log = open(os.path.join(common.WORK, 're_sb.log'), 'w')
    p = subprocess.Popen([common.SB, 'run', '-c', path], stdout=log, stderr=log)
    if not _wait_for_port(19091, timeout=15):
        print('sing-box failed to start')
        p.kill()
        log.close()
        return {}
    counts = {x['link']: 0 for x in conv}

    def _delay(tag, url, ms):
        try:
            q = urllib.parse.urlencode({'url': url, 'timeout': ms})
            with urllib.request.urlopen(
                    f'http://127.0.0.1:19091/proxies/{tag}/delay?{q}', timeout=ms / 1000 + 3) as r:
                return json.loads(r.read().decode()).get('delay')
        except Exception:
            return None

    for rnd in range(common.PASSES):
        def task(x):
            d = _delay(x['out']['tag'], common.T1, 4000)
            if d is None:
                d = _delay(x['out']['tag'], common.T2, 4000)
            return x['link'], d
        ok = 0
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            for link, d in ex.map(task, conv):
                if d is not None:
                    counts[link] += 1
                    ok += 1
        print(f'  جولة {rnd + 1}: ناجح {ok}/{len(conv)}', flush=True)
    try:
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=10)
    except Exception:
        p.kill()
    log.close()
    return counts


# ------------------------- Xray phase (xhttp) ----------------------------
def xray_out(link, tag):
    p = urlparse(link)
    d = {k.lower(): v[0] for k, v in parse_qs(p.query, keep_blank_values=True).items()}
    host, port = p.hostname, p.port
    if not (host and port):
        return None
    ss = {'network': 'xhttp', 'xhttpSettings': {'path': d.get('path', '/') or '/'}}
    if d.get('host'):
        ss['xhttpSettings']['host'] = d['host']
    if d.get('mode'):
        ss['xhttpSettings']['mode'] = d['mode']
    sec = (d.get('security') or '').lower()
    sni = d.get('sni') or ''
    fp = d.get('fp') or ''
    if sec == 'reality':
        ss['security'] = 'reality'
        ss['realitySettings'] = {'serverName': sni or host, 'fingerprint': fp or 'chrome',
                                 'publicKey': d.get('pbk', ''), 'shortId': d.get('sid', '')}
    else:
        ss['security'] = 'tls'
        ts = {'serverName': sni or host}
        if str(d.get('allowinsecure', d.get('insecure', ''))).lower() in ('1', 'true'):
            ts['allowInsecure'] = True
        if d.get('fp'):
            ts['fingerprint'] = d['fp']
        ss['tlsSettings'] = ts
    if link.startswith('vless://'):
        user = {'id': unquote(p.username or ''), 'encryption': 'none'}
        if d.get('flow'):
            user['flow'] = d['flow']
        return {'tag': tag, 'protocol': 'vless',
                'settings': {'vnext': [{'address': host, 'port': int(port), 'users': [user]}]},
                'streamSettings': ss}
    pw = unquote(p.username or '')
    return {'tag': tag, 'protocol': 'trojan',
            'settings': {'servers': [{'address': host, 'port': int(port), 'password': pw}]},
            'streamSettings': ss}


def curl_test(port, url, tmo):
    try:
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                            '-x', f'socks5h://127.0.0.1:{port}', '--max-time', str(tmo), url],
                           capture_output=True, text=True, timeout=tmo + 3)
        return r.stdout.strip() == '204'
    except Exception:
        return False


def test_xray(links, workers=64):
    inbounds, outbounds, rules, items = [], [], [], []
    for l in links:
        tag = f'o{len(items)}'
        ob = xray_out(l, tag)
        if not ob:
            continue
        port = 21000 + len(items)
        itag = f'i{len(items)}'
        inbounds.append({'tag': itag, 'listen': '127.0.0.1', 'port': port,
                         'protocol': 'socks', 'settings': {'udp': False}})
        outbounds.append(ob)
        rules.append({'type': 'field', 'inboundTag': [itag], 'outboundTag': tag})
        items.append({'link': l, 'port': port})
    if not items:
        return {}
    outbounds.append({'tag': 'direct', 'protocol': 'freedom'})
    cfg = {'log': {'loglevel': 'warning'}, 'inbounds': inbounds, 'outbounds': outbounds,
           'routing': {'domainStrategy': 'AsIs', 'rules': rules}}
    path = os.path.join(common.WORK, 're_xray.json')
    json.dump(cfg, open(path, 'w'), ensure_ascii=False)
    log = open(os.path.join(common.WORK, 're_xray.log'), 'w')
    p = subprocess.Popen([common.XRAY, 'run', '-c', path], stdout=log, stderr=log)
    if not _wait_for_port(21000, timeout=15):
        print('xray failed to start')
        p.kill()
        log.close()
        return {}
    counts = {x['link']: 0 for x in items}
    for rnd in range(common.PASSES):
        def task(it):
            return it['link'], (curl_test(it['port'], common.T1, 6) or curl_test(it['port'], common.T2, 6))
        ok = 0
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            for link, good in ex.map(task, items):
                if good:
                    counts[link] += 1
                    ok += 1
        print(f'  جولة {rnd + 1}: ناجح {ok}/{len(items)}', flush=True)
    try:
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=10)
    except Exception:
        p.kill()
    log.close()
    return counts


def run_all(links, workers=64):
    xh = [l for l in links if 'xhttp' in l.lower() or 'splithttp' in l.lower()]
    nonset = set(xh)
    non = [l for l in links if l not in nonset]
    print(f'  إجمالي {len(links)} | غير xhttp {len(non)} | xhttp {len(xh)}', flush=True)
    c = {}
    c.update(phase_singbox(non, workers=workers))
    c.update(test_xray(xh, workers=workers))
    return c


# ------------------------- throttling phase ------------------------------
def _curl_kbps(port, url, timeout):
    """Download *url* through the local SOCKS port; return KB/s or None."""
    try:
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{size_download} %{time_total}',
                            '-x', f'socks5h://127.0.0.1:{port}', '--max-time', str(timeout), url],
                           capture_output=True, text=True, timeout=timeout + 3)
        parts = r.stdout.split()
        if len(parts) != 2:
            return None
        size, secs = float(parts[0]), float(parts[1])
        if size <= 0 or secs <= 0:
            return None
        return size / 1024.0 / secs
    except Exception:
        return None


def throttle_test(links, carrier=None):
    """Measure throughput + sustained stability of *links*.

    Returns (throttled, unstable, kbps_map). Links whose throughput could not
    be measured are not marked as throttled (conservative).
    """
    carrier = carrier or common.CARRIER
    profile = CARRIER_PROFILES.get(carrier, CARRIER_PROFILES['auto'])
    throttle_kbps = profile.get('throttle_kbps', common.THROTTLE_KBPS)
    size_kb = common.THROTTLE_TEST_SIZE
    sust = common.SUSTAINED_SECONDS
    url = common.THROTTLE_URL.format(bytes=size_kb * 1024)

    conv = []
    for l in links:
        o = link_to_outbound(l, f't{len(conv)}')
        if not o:
            continue
        conv.append({'link': l, 'out': o, 'in': f'i{len(conv)}', 'port': 22000 + len(conv)})
    if not conv:
        return set(), set(), {}

    inbounds = [{'type': 'socks', 'tag': c['in'], 'listen': '127.0.0.1', 'listen_port': c['port']}
                for c in conv]
    rules = [{'inbound': [c['in']], 'outbound': c['out']['tag']} for c in conv]
    cfg = {'log': {'level': 'error'}, 'inbounds': inbounds,
           'outbounds': [c['out'] for c in conv], 'route': {'rules': rules}}
    path = os.path.join(common.WORK, 're_throttle.json')
    json.dump(cfg, open(path, 'w'), ensure_ascii=False)
    chk = subprocess.run([common.SB, 'check', '-c', path], capture_output=True, text=True)
    if chk.returncode != 0:
        print('  check فشل (خنق):', chk.stderr.strip()[:200], flush=True)
        return set(), set(), {}

    log = open(os.path.join(common.WORK, 're_throttle.log'), 'w')
    p = subprocess.Popen([common.SB, 'run', '-c', path], stdout=log, stderr=log)
    if not _wait_for_port(conv[0]['port'], timeout=15):
        print('  تعذّر بدء sing-box (خنق)', flush=True)
        p.kill()
        log.close()
        return set(), set(), {}

    throttled, unstable, kbps_map = set(), set(), {}

    def task(c):
        kbps = _curl_kbps(c['port'], url, 20)
        good = True
        for _ in range(5):
            if not (curl_test(c['port'], common.T1, 5) or curl_test(c['port'], common.T2, 5)):
                good = False
                break
            time.sleep(sust / 5.0)
        return c['link'], kbps, good

    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        for link, kbps, good in ex.map(task, conv):
            if kbps is not None:
                kbps_map[link] = round(kbps, 1)
                if kbps < throttle_kbps:
                    throttled.add(link)
            if not good:
                unstable.add(link)
    try:
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=10)
    except Exception:
        p.kill()
    log.close()
    print(f'  مخنوق: {len(throttled)} | غير مستقرّ: {len(unstable)}', flush=True)
    return throttled, unstable, kbps_map
