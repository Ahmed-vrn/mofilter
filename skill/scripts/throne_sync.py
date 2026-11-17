#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import the working servers into a Throne (Nekoray-family) database.

The contents of one group (default «شغّال ✅») are replaced with the current
stable list, exactly like importing the share-links by hand.

Safe by design:
  * refuses to run while Throne/Nekoray is running (override with --force),
  * backs the database up (db + -wal + -shm) before every change, keeping the
    last 14 backups,
  * never creates a profile outside the selected group.

Usage:
  python3 throne_sync.py [--list FILE] [--countries FILE]
                         [--db PATH] [--group NAME] [--force] [--dry-run]

Environment:
  VPN_THRONE_DB         explicit database path
  VPN_THRONE_GROUP      target group name          (default «شغّال ✅»)
  VPN_THRONE_BACKUP_DIR backup directory           (default <data>/throne-backups)
  VPN_OUT               output dir                 (default ~/Desktop/vpn-list)
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from links2sb import link_to_outbound  # noqa: E402

DEFAULT_GROUP = 'شغّال ✅'
DATABASES = [
    '~/.config/Throne/config/throne.db',
    '~/.local/share/Throne/config/throne.db',
    '~/.config/nekoray/config/nekoray.db',
    '~/.local/share/nekoray/config/nekoray.db',
]
FLAGS = {'NL': '🇳🇱', 'RU': '🇷🇺', 'KR': '🇰🇷', 'TW': '🇹🇼', 'US': '🇺🇸', 'DE': '🇩🇪',
         'GB': '🇬🇧', 'FR': '🇫🇷', 'SE': '🇸🇪', 'FI': '🇫🇮', 'PL': '🇵🇱', 'JP': '🇯🇵',
         'SG': '🇸🇬', 'TR': '🇹🇷', 'IR': '🇮🇷', 'CA': '🇨🇦', 'CH': '🇨🇭', 'AT': '🇦🇹'}


def flag(cc):
    if cc in FLAGS:
        return FLAGS[cc]
    if len(cc) == 2 and cc.isalpha():
        return chr(0x1F1E6 + ord(cc[0]) - 65) + chr(0x1F1E6 + ord(cc[1]) - 65)
    return '🏳️'


def find_db(explicit=None):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    env = os.environ.get('VPN_THRONE_DB')
    if env and os.path.exists(env):
        return env
    for c in DATABASES:
        p = os.path.expanduser(c)
        if os.path.exists(p):
            return p
    return None


def running():
    for name in ('throne', 'nekoray', 'nekobox'):
        try:
            if subprocess.run(['pgrep', '-x', name], capture_output=True).returncode == 0:
                return True
        except Exception:
            pass
    return False


def backup(db):
    root = os.environ.get('VPN_THRONE_BACKUP_DIR') or \
        os.path.join(os.path.expanduser('~/.local/share/vpn-list'), 'throne-backups')
    d = os.path.join(root, datetime.now().strftime('%Y-%m-%d_%H%M%S'))
    os.makedirs(d, exist_ok=True)
    for suf in ('', '-wal', '-shm'):
        if os.path.exists(db + suf):
            shutil.copy2(db + suf, os.path.join(d, os.path.basename(db) + suf))
    dirs = sorted(os.path.join(root, x) for x in os.listdir(root)
                  if os.path.isdir(os.path.join(root, x)))
    for old in dirs[:-14]:
        shutil.rmtree(old, ignore_errors=True)
    return d


# --------------------------- link -> Throne profile ----------------------
def xrayvless(link, name):
    """Throne's Xray-core outbound for a VLESS link (incl. xhttp/reality)."""
    p = urlparse(link)
    q = {k.lower(): v[0] for k, v in parse_qs(p.query, keep_blank_values=True).items()}
    host, port, uid = p.hostname, int(p.port), unquote(p.username or '')
    o = {'protocol': 'vless',
         'settings': {'address': host, 'encryption': q.get('encryption') or 'none',
                      'id': uid, 'port': port},
         'streamSettings': {'network': 'xhttp'},
         'tag': name}
    if q.get('flow'):
        o['settings']['flow'] = q['flow']
    ss = o['streamSettings']
    xh = {}
    if q.get('path'):
        xh['path'] = q['path']
    if q.get('host'):
        xh['host'] = q['host']
    if q.get('mode'):
        xh['mode'] = q['mode']
    if (q.get('security') or '').lower() == 'reality' or q.get('pbk'):
        rs = {}
        if q.get('pbk'):
            rs['password'] = q['pbk']
        rs['serverName'] = q.get('sni') or host
        if q.get('fp'):
            rs['fingerprint'] = q['fp']
        if q.get('sid'):
            rs['shortId'] = q['sid']
        if q.get('spx'):
            rs['spiderX'] = q['spx']
        ss['security'] = 'reality'
        ss['realitySettings'] = rs
    else:
        ts = {'serverName': q.get('sni') or host}
        if q.get('fp'):
            ts['fingerprint'] = q['fp']
        if str(q.get('allowinsecure', q.get('insecure', ''))).lower() in ('1', 'true'):
            ts['allowInsecure'] = True
        if q.get('alpn'):
            ts['alpn'] = [a for a in q['alpn'].split(',') if a]
        o['streamSettings']['security'] = 'tls'
        o['streamSettings']['tlsSettings'] = ts
    if q.get('path') or q.get('host') or q.get('mode'):
        o['streamSettings']['xhttpSettings'] = {
            k: v for k, v in (('path', q.get('path')), ('host', q.get('host')), ('mode', q.get('mode'))) if v}
    return o


def throne_entry(link, name):
    """Return (type, outbound_json) for *link*, or None if unsupported."""
    low = link.lower()
    if low.startswith('vless://') and ('xhttp' in low or 'splithttp' in low):
        return 'xrayvless', json.dumps(xrayvless(link, name), ensure_ascii=False)
    o = link_to_outbound(link, name)
    if not o:
        return None
    return o.get('type', 'vless'), json.dumps(o, ensure_ascii=False)


# --------------------------- database ------------------------------------
def main():
    ap = argparse.ArgumentParser(description='import working servers into Throne')
    ap.add_argument('--list', default=None, help='stable list file')
    ap.add_argument('--countries', default=None, help='countries.json')
    ap.add_argument('--db', default=None, help='Throne database path')
    ap.add_argument('--group', default=os.environ.get('VPN_THRONE_GROUP') or DEFAULT_GROUP)
    ap.add_argument('--force', action='store_true', help='run even if Throne is running')
    ap.add_argument('--dry-run', action='store_true', help='do not write anything')
    a = ap.parse_args()

    out_dir = os.path.expanduser(os.environ.get('VPN_OUT', '~/Desktop/vpn-list'))
    list_path = a.list or os.path.join(out_dir, 'working_stable_unique.txt')
    ctry_path = a.countries or os.path.join(out_dir, 'countries.json')

    if not os.path.exists(list_path):
        print(f'[throne] no list at {list_path} — nothing to do')
        return 0
    links = [l.strip() for l in open(list_path, encoding='utf-8') if l.strip()]
    if not links:
        print('[throne] list is empty — nothing to do')
        return 0

    db = find_db(a.db)
    if not db:
        print('[throne] database not found — skipping (set VPN_THRONE_DB to override)')
        return 0

    if running() and not a.force and not a.dry_run:
        print('[throne] Throne is running — skipping sync (close it or use --force)')
        return 0

    countries = {}
    if os.path.exists(ctry_path):
        try:
            countries = json.load(open(ctry_path, encoding='utf-8'))
        except Exception:
            countries = {}

    rows = []
    for i, l in enumerate(links, 1):
        cc = countries.get(l, 'XX')
        name = f'{flag(cc)} {cc}-{i}'
        e = throne_entry(l, name)
        if e:
            rows.append((e[0], name, e[1]))
        else:
            print(f'[throne] skip (unsupported): {l[:60]}')
    if not rows:
        print('[throne] no importable profiles — nothing to do')
        return 0

    grp = a.group
    if a.dry_run:
        print(f'[throne] DRY-RUN: would put {len(rows)} profiles into group «{grp}» of {db}')
        return 0

    bdir = backup(db)
    con = sqlite3.connect(db)
    try:
        cols = {r[1] for r in con.execute('PRAGMA table_info(profiles)')}
        if not {'id', 'type', 'name', 'gid', 'outbound_json'} <= cols:
            print('[throne] unsupported database schema — aborting')
            return 1
        cur = con.cursor()
        row = cur.execute('SELECT id FROM groups WHERE name=? AND archive=0 ORDER BY id LIMIT 1',
                          (grp,)).fetchone()
        if row:
            gid = row[0]
            created = False
        else:
            gid = cur.execute('SELECT COALESCE(MAX(id),0)+1 FROM groups').fetchone()[0]
            cur.execute('INSERT INTO groups (id, name, profiles_json) VALUES (?,?,?)', (gid, grp, '[]'))
            created = True
        if not cur.execute('SELECT 1 FROM groups_order WHERE group_id=?', (gid,)).fetchone():
            order = cur.execute('SELECT COALESCE(MAX(display_order),-1)+1 FROM groups_order').fetchone()[0]
            cur.execute('INSERT INTO groups_order (group_id, display_order) VALUES (?,?)', (gid, order))

        cur.execute('DELETE FROM profiles WHERE gid=?', (gid,))
        last = cur.execute('SELECT COALESCE(profile_last_id,0) FROM entity_ids').fetchone()[0] or 0
        now = int(time.time())
        ids = []
        for t, name, oj in rows:
            last += 1
            cur.execute('INSERT INTO profiles (id, type, name, gid, latency, outbound_json, '
                        'created_at, updated_at, latency_at) VALUES (?,?,?,?,0,?,?,?,0)',
                        (last, t, name, gid, oj, now, now))
            ids.append(last)
        cur.execute('UPDATE entity_ids SET profile_last_id=?', (last,))
        cur.execute('UPDATE groups SET profiles_json=?, updated_at=? WHERE id=?',
                    (json.dumps(ids), now, gid))
        if created:
            try:
                cur.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)',
                            ('current_group', str(gid)))
            except Exception:
                pass
        con.commit()
        try:
            con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        except Exception:
            pass
    finally:
        con.close()

    print(f'[throne] imported {len(rows)} profiles into «{grp}» (db={db})')
    print(f'[throne] backup: {bdir}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # never break the daily job
        print(f'[throne] error: {exc}')
        raise SystemExit(1)
