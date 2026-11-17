#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert proxy share-links to sing-box outbounds (best-effort)."""
import base64, json, re
from urllib.parse import urlparse, parse_qs, unquote, quote
from ipaddress import ip_address


def _b64d(s):
    s = s.strip().replace('-', '+').replace('_', '/')
    s += '=' * (-len(s) % 4)
    return base64.b64decode(s).decode('utf-8', 'ignore')


def _q(u):
    p = urlparse(u)
    q = {}
    for k, v in parse_qs(p.query, keep_blank_values=True).items():
        q[k.lower()] = v[0]
    return p, q


def _is_ip(h):
    try:
        ip_address(h)
        return True
    except Exception:
        return False


def _tls(q, host, security):
    sec = (security or '').lower()
    sni = q.get('sni') or q.get('peer') or ''
    fp = q.get('fp') or ''
    alpn = q.get('alpn') or ''
    insecure = str(q.get('allowinsecure', q.get('insecure', ''))).lower() in ('1', 'true')
    pbk = q.get('pbk') or q.get('publickey') or ''
    sid = q.get('sid') or q.get('shortid') or ''
    spx = q.get('spx') or ''
    has_tls = (sec in ('tls', 'reality', 'xtls')) or bool(sni) or bool(pbk)
    if not has_tls:
        return None
    tls = {'enabled': True}
    tls['server_name'] = sni if sni else ('' if _is_ip(host) else host)
    if not tls['server_name']:
        tls.pop('server_name')
    if insecure:
        tls['insecure'] = True
    if alpn:
        tls['alpn'] = [a for a in alpn.split(',') if a]
    if fp:
        tls['utls'] = {'enabled': True, 'fingerprint': fp}
    if sec == 'reality' or pbk:
        r = {'enabled': True}
        if pbk:
            r['public_key'] = pbk
        if sid:
            r['short_id'] = sid
        tls['reality'] = r
        tls.pop('server_name', None)
        if sni:
            tls['server_name'] = sni
    return tls


def _transport(q, ttype):
    t = (ttype or '').lower()
    path = q.get('path') or ''
    host = q.get('host') or ''
    sn = q.get('servicename') or q.get('servicename') or q.get('serviceName') or q.get('service_name') or ''
    if t in ('ws', 'websocket'):
        tr = {'type': 'ws', 'path': path or '/'}
        if host:
            tr['headers'] = {'Host': host}
        return tr, True
    if t == 'grpc':
        tr = {'type': 'grpc'}
        if sn:
            tr['service_name'] = sn
        return tr, True
    if t in ('http', 'h2', 'h2c'):
        tr = {'type': 'http', 'path': path or '/'}
        if host:
            tr['host'] = [h for h in host.split(',') if h]
        return tr, True
    if t == 'httpupgrade':
        tr = {'type': 'httpupgrade', 'path': path or '/'}
        if host:
            tr['host'] = host
        return tr, True
    if t in ('xhttp', 'splithttp'):
        return None, False
    return None, True


def _repair(o):
    if not o:
        return o
    host = o.get('server', '')
    tls = o.get('tls')
    if tls and tls.get('enabled'):
        if tls.get('reality', {}).get('enabled') and 'utls' not in tls:
            tls['utls'] = {'enabled': True, 'fingerprint': 'chrome'}
        if not tls.get('server_name') and not tls.get('insecure'):
            tls['server_name'] = host
    return o


def link_to_outbound(link, tag):
    link = link.strip()
    proto = link.split('://', 1)[0].lower()
    o = None
    try:
        if proto == 'vless':
            o = _vless(link, tag)
        elif proto == 'vmess':
            o = _vmess(link, tag)
        elif proto == 'trojan':
            o = _trojan(link, tag)
        elif proto == 'ss':
            o = _ss(link, tag)
        elif proto in ('hysteria2', 'hy2'):
            o = _hy2(link, tag)
        elif proto == 'tuic':
            o = _tuic(link, tag)
    except Exception:
        return None
    return _repair(o)


def _vless(link, tag):
    p, q = _q(link)
    uuid = unquote(p.username or '')
    host = p.hostname
    port = p.port
    if not (uuid and host and port):
        return None
    o = {'type': 'vless', 'tag': tag, 'server': host, 'server_port': int(port), 'uuid': uuid}
    flow = q.get('flow') or ''
    if flow:
        o['flow'] = flow
    tls = _tls(q, host, q.get('security'))
    if tls:
        o['tls'] = tls
    tr, ok = _transport(q, q.get('type'))
    if not ok:
        return None
    if tr:
        o['transport'] = tr
    return o


def _vmess(link, tag):
    p = urlparse(link[8:])
    b = link[8:]
    j = json.loads(_b64d(b))
    host = j.get('add')
    port = j.get('port')
    uuid = j.get('id')
    if not (uuid and host and port):
        return None
    o = {'type': 'vmess', 'tag': tag, 'server': host, 'server_port': int(port), 'uuid': uuid,
         'security': j.get('scy') or 'auto'}
    if j.get('aid') and int(j['aid']) != 0:
        o['alter_id'] = int(j['aid'])
    net = (j.get('net') or 'tcp').lower()
    if str(j.get('tls', '')).lower() in ('tls', 'reality', 'true', '1'):
        tls = {'enabled': True}
        sni = j.get('sni') or j.get('host') or ''
        if sni:
            tls['server_name'] = sni
        if str(j.get('allowInsecure', '')).lower() in ('1', 'true'):
            tls['insecure'] = True
        if j.get('fp'):
            tls['utls'] = {'enabled': True, 'fingerprint': j['fp']}
        o['tls'] = tls
    path = j.get('path') or ''
    hh = j.get('host') or ''
    if net == 'ws':
        tr = {'type': 'ws', 'path': path or '/'}
        if hh:
            tr['headers'] = {'Host': hh}
        o['transport'] = tr
    elif net == 'grpc':
        tr = {'type': 'grpc'}
        if path:
            tr['service_name'] = path
        o['transport'] = tr
    elif net in ('h2', 'http'):
        tr = {'type': 'http', 'path': path or '/'}
        if hh:
            tr['host'] = [hh]
        o['transport'] = tr
    return o


def _trojan(link, tag):
    p, q = _q(link)
    pw = unquote(p.username or '')
    host = p.hostname
    port = p.port
    if not (pw and host and port):
        return None
    o = {'type': 'trojan', 'tag': tag, 'server': host, 'server_port': int(port), 'password': pw}
    tls = _tls(q, host, q.get('security') or 'tls') or {'enabled': True, 'server_name': q.get('sni') or host}
    o['tls'] = tls
    tr, ok = _transport(q, q.get('type'))
    if not ok:
        return None
    if tr:
        o['transport'] = tr
    return o


def _ss(link, tag):
    body = link[5:]
    if '#' in body:
        body = body.split('#', 1)[0]
    plugin = None
    if '?' in body:
        body, qs = body.split('?', 1)
        plugin = {}
        for kv in qs.split('&'):
            if '=' in kv:
                k, v = kv.split('=', 1)
                plugin[k.lower()] = unquote(v)
    body = body.rstrip('/')
    if '@' in body:
        userinfo, hp = body.rsplit('@', 1)
        try:
            dec = _b64d(userinfo)
            ui = dec if ':' in dec else unquote(userinfo)
        except Exception:
            ui = unquote(userinfo)
        if ':' not in ui:
            return None
        method, password = ui.split(':', 1)
        hp = hp.split('/')[0]
        if ':' not in hp:
            return None
        host, port = hp.rsplit(':', 1)
    else:
        dec = _b64d(unquote(body))
        if '@' not in dec or ':' not in dec:
            return None
        ui, hp = dec.rsplit('@', 1)
        method, password = ui.split(':', 1)
        host, port = hp.rsplit(':', 1)
    try:
        port = int(port)
    except Exception:
        return None
    o = {'type': 'shadowsocks', 'tag': tag, 'server': host, 'server_port': port,
         'method': method, 'password': password}
    o = {'type': 'shadowsocks', 'tag': tag, 'server': host, 'server_port': port,
         'method': method, 'password': password}
    if plugin and plugin.get('plugin'):
        pl = plugin['plugin']
        if pl in ('v2ray-plugin', 'obfs-local', 'simple-obfs'):
            o['plugin'] = pl
            opts = []
            for k, v in plugin.items():
                if k == 'plugin':
                    continue
                opts.append(f'{k}={v}' if v not in ('', 'true') else k)
            o['plugin_opts'] = ';'.join(opts)
    return o


def _hy2(link, tag):
    p, q = _q(link)
    pw = unquote(p.username or '') or unquote(p.password or '')
    host = p.hostname
    port = p.port
    if not (host and port):
        return None
    o = {'type': 'hysteria2', 'tag': tag, 'server': host, 'server_port': int(port)}
    if pw:
        o['password'] = pw
    tls = {'enabled': True, 'server_name': q.get('sni') or ('' if _is_ip(host) else host)}
    if not tls['server_name']:
        tls.pop('server_name')
    if str(q.get('insecure', q.get('allowinsecure', ''))).lower() in ('1', 'true'):
        tls['insecure'] = True
    if q.get('alpn'):
        tls['alpn'] = [a for a in q['alpn'].split(',') if a]
    o['tls'] = tls
    if q.get('obfs'):
        ob = {'type': q['obfs']}
        if q.get('obfs-password'):
            ob['password'] = q['obfs-password']
        o['obfs'] = ob
    return o


def _tuic(link, tag):
    p, q = _q(link)
    uuid = unquote(p.username or '')
    pw = unquote(p.password or '')
    host = p.hostname
    port = p.port
    if not (host and port):
        return None
    o = {'type': 'tuic', 'tag': tag, 'server': host, 'server_port': int(port)}
    if uuid:
        o['uuid'] = uuid
    if pw:
        o['password'] = pw
    tls = {'enabled': True, 'server_name': q.get('sni') or ('' if _is_ip(host) else host)}
    if not tls['server_name']:
        tls.pop('server_name')
    if str(q.get('allow_insecure', q.get('insecure', ''))).lower() in ('1', 'true'):
        tls['insecure'] = True
    o['tls'] = tls
    return o


if __name__ == '__main__':
    import sys
    links = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    out = []
    bad = 0
    for i, l in enumerate(links):
        o = link_to_outbound(l, f'p{i}')
        if o:
            out.append({'link': l, 'out': o})
        else:
            bad += 1
    json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False)
    print(f'total={len(links)} converted={len(out)} failed={bad}')
