#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a Clash/Mihomo config from the stable, country-annotated links."""
import json, os, base64, sys
from urllib.parse import urlparse, parse_qs, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

OUT = common.OUT
SRC = common.BY_COUNTRY


def scalar(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if v is None:
        return 'null'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s and all(c.isalnum() or c in '_-.@/:+ ' for c in s):
        return s
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def dump(o, indent=0):
    pad = '  ' * indent
    lines = []
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)) and len(v) > 0:
                lines.append(f'{pad}{k}:')
                lines.append(dump(v, indent + 1))
            else:
                lines.append(f'{pad}{k}: {scalar(v)}')
    elif isinstance(o, list):
        for it in o:
            if isinstance(it, dict):
                first = True
                for k, v in it.items():
                    pre = '- ' if first else '  '
                    pad2 = pad + pre
                    if isinstance(v, (dict, list)) and len(v) > 0:
                        lines.append(f'{pad2}{k}:')
                        lines.append(dump(v, indent + 2))
                    else:
                        lines.append(f'{pad2}{k}: {scalar(v)}')
                    first = False
            else:
                lines.append(f'{pad}- {scalar(it)}')
    else:
        lines.append(f'{pad}{scalar(o)}')
    return '\n'.join(lines)


def q(u):
    p = urlparse(u)
    d = {k.lower(): v[0] for k, v in parse_qs(p.query, keep_blank_values=True).items()}
    return p, d


def to_clash(link, name):
    proto = link.split('://', 1)[0].lower()
    try:
        if proto == 'vless':
            p, d = q(link)
            o = {'name': name, 'type': 'vless', 'server': p.hostname, 'port': int(p.port),
                 'uuid': unquote(p.username or ''), 'udp': True}
            if d.get('fp'):
                o['client-fingerprint'] = d['fp']
            if d.get('flow'):
                o['flow'] = d['flow']
            sec = (d.get('security') or '').lower()
            if sec == 'reality':
                o['tls'] = True
                o['servername'] = d.get('sni') or p.hostname
                o['reality-opts'] = {'public-key': d.get('pbk', ''), 'short-id': d.get('sid', '')}
                if str(d.get('insecure', '')).lower() in ('1', 'true'):
                    o['skip-cert-verify'] = True
            elif sec == 'tls' or d.get('sni'):
                o['tls'] = True
                o['servername'] = d.get('sni') or p.hostname
                if d.get('alpn'):
                    o['alpn'] = [a for a in d['alpn'].split(',') if a]
                if str(d.get('allowinsecure', d.get('insecure', ''))).lower() in ('1', 'true'):
                    o['skip-cert-verify'] = True
            t = (d.get('type') or 'tcp').lower()
            if t in ('ws', 'websocket'):
                o['network'] = 'ws'
                o['ws-opts'] = {'path': d.get('path', '/') or '/'}
                if d.get('host'):
                    o['ws-opts']['headers'] = {'Host': d['host']}
            elif t == 'grpc':
                o['network'] = 'grpc'
                o['grpc-opts'] = {'grpc-service-name': d.get('servicename') or d.get('service_name') or ''}
            elif t in ('http', 'h2'):
                o['network'] = 'h2'
                o['h2-opts'] = {'path': d.get('path', '/') or '/'}
                if d.get('host'):
                    o['h2-opts']['host'] = [d['host']]
            elif t == 'httpupgrade':
                o['network'] = 'ws'
                o['ws-opts'] = {'path': d.get('path', '/') or '/', 'v2ray-http-upgrade': True}
                if d.get('host'):
                    o['ws-opts']['headers'] = {'Host': d['host']}
            return o
        if proto == 'vmess':
            b = link[8:]
            j = json.loads(base64.b64decode(b + '=' * (-len(b) % 4)).decode('utf-8', 'ignore'))
            o = {'name': name, 'type': 'vmess', 'server': j.get('add'), 'port': int(j.get('port')),
                 'uuid': j.get('id'), 'alterId': int(j.get('aid') or 0), 'cipher': j.get('scy') or 'auto', 'udp': True}
            if str(j.get('tls', '')).lower() in ('tls', 'reality', 'true', '1'):
                o['tls'] = True
                o['servername'] = j.get('sni') or j.get('host') or ''
                if str(j.get('allowInsecure', '')).lower() in ('1', 'true'):
                    o['skip-cert-verify'] = True
            net = (j.get('net') or 'tcp').lower()
            if net == 'ws':
                o['network'] = 'ws'
                o['ws-opts'] = {'path': j.get('path') or '/'}
                if j.get('host'):
                    o['ws-opts']['headers'] = {'Host': j['host']}
            elif net == 'grpc':
                o['network'] = 'grpc'
                o['grpc-opts'] = {'grpc-service-name': j.get('path') or ''}
            elif net in ('h2', 'http'):
                o['network'] = 'h2'
                o['h2-opts'] = {'path': j.get('path') or '/'}
                if j.get('host'):
                    o['h2-opts']['host'] = [j['host']]
            return o
        if proto == 'trojan':
            p, d = q(link)
            o = {'name': name, 'type': 'trojan', 'server': p.hostname, 'port': int(p.port),
                 'password': unquote(p.username or ''), 'udp': True,
                 'sni': d.get('sni') or p.hostname}
            if str(d.get('allowinsecure', d.get('insecure', ''))).lower() in ('1', 'true'):
                o['skip-cert-verify'] = True
            if d.get('alpn'):
                o['alpn'] = [a for a in d['alpn'].split(',') if a]
            if d.get('fp'):
                o['client-fingerprint'] = d['fp']
            if (d.get('type') or '').lower() == 'ws':
                o['network'] = 'ws'
                o['ws-opts'] = {'path': d.get('path', '/') or '/'}
                if d.get('host'):
                    o['ws-opts']['headers'] = {'Host': d['host']}
            return o
        if proto == 'ss':
            body = link[5:].split('#', 1)[0]
            if '@' in body:
                ui, hp = body.rsplit('@', 1)
                try:
                    dec = base64.b64decode(ui + '=' * (-len(ui) % 4)).decode('utf-8', 'ignore')
                    ui = dec if ':' in dec else unquote(ui)
                except Exception:
                    ui = unquote(ui)
                method, pw = ui.split(':', 1)
                hp = hp.split('?', 1)[0].rstrip('/')
                host, port = hp.rsplit(':', 1)
            else:
                dec = base64.b64decode(body + '=' * (-len(body) % 4)).decode('utf-8', 'ignore')
                ui, hp = dec.rsplit('@', 1)
                method, pw = ui.split(':', 1)
                host, port = hp.rsplit(':', 1)
            return {'name': name, 'type': 'ss', 'server': host, 'port': int(port), 'cipher': method, 'password': pw}
        if proto in ('hysteria2', 'hy2'):
            p, d = q(link)
            o = {'name': name, 'type': 'hysteria2', 'server': p.hostname, 'port': int(p.port),
                 'password': unquote(p.username or '')}
            if d.get('sni'):
                o['sni'] = d['sni']
            if str(d.get('insecure', d.get('allowinsecure', ''))).lower() in ('1', 'true'):
                o['skip-cert-verify'] = True
            if d.get('alpn'):
                o['alpn'] = [a for a in d['alpn'].split(',') if a]
            if d.get('obfs'):
                o['obfs'] = d['obfs']
                if d.get('obfs-password'):
                    o['obfs-password'] = d['obfs-password']
            return o
    except Exception:
        return None
    return None


def build_config(proxies, allnames, split_routing=True):
    groups = [
        {'name': 'AUTO', 'type': 'url-test',
         'url': 'https://www.gstatic.com/generate_204',
         'interval': 300, 'tolerance': 50, 'lazy': True, 'proxies': allnames},
        {'name': 'PROXY', 'type': 'select', 'proxies': ['AUTO'] + allnames + ['DIRECT']},
    ]
    if split_routing:
        groups.insert(0, {'name': 'RU-DIRECT', 'type': 'select', 'proxies': ['DIRECT', 'PROXY']})
        rules = ['GEOIP,LAN,DIRECT,no-resolve',
                 'GEOSITE,category-ru,RU-DIRECT',
                 'DOMAIN-SUFFIX,.ru,RU-DIRECT',
                 'DOMAIN-SUFFIX,yandex.net,RU-DIRECT',
                 'DOMAIN-SUFFIX,vk.com,RU-DIRECT',
                 'DOMAIN-SUFFIX,mail.ru,RU-DIRECT',
                 'DOMAIN-SUFFIX,userapi.com,RU-DIRECT',
                 'GEOIP,CN,DIRECT',
                 'MATCH,PROXY']
    else:
        rules = ['GEOIP,LAN,DIRECT,no-resolve', 'GEOIP,CN,DIRECT', 'MATCH,PROXY']
    return {
        'mixed-port': 7890,
        'allow-lan': False,
        'mode': 'rule',
        'log-level': 'info',
        'external-controller': '127.0.0.1:9090',
        'dns': {'enable': True, 'nameserver': ['1.1.1.1', '8.8.8.8'],
                'enhanced-mode': 'fake-ip', 'fake-ip-range': '198.18.0.1/16'},
        'proxies': proxies,
        'proxy-groups': groups,
        'rules': rules,
    }


def main():
    src = common.BY_COUNTRY
    links = [l.strip() for l in open(src) if l.strip()]
    proxies, names = [], set()
    for idx, l in enumerate(links):
        base = l.split('#', 1)[0]
        frag = l.split('#', 1)[1] if '#' in l else ''
        name = unquote(frag) if frag else f'server-{idx+1}'
        o = to_clash(base + ('#' + frag if frag else ''), name)
        if not o:
            continue
        nm = o['name']; k = 2
        while nm in names:
            nm = f"{o['name']}-{k}"; k += 1
        o['name'] = nm; names.add(nm)
        proxies.append(o)
    allnames = [p['name'] for p in proxies]
    with open(common.CLASH, 'w') as f:
        f.write(dump(build_config(proxies, allnames, split_routing=True)) + '\n')
    with open(common.CLASH_SIMPLE, 'w') as f:
        f.write(dump(build_config(proxies, allnames, split_routing=False)) + '\n')
    print(f'عدد السيرفرات: {len(proxies)}')
    print('حُفظ:', common.CLASH)
    print('حُفظ:', common.CLASH_SIMPLE)


if __name__ == '__main__':
    main()
