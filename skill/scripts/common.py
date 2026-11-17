#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared configuration and paths for the vpn-list skill.

The skill is app-agnostic: the output is normal subscription/link files you can
import into any VPN client. Nothing here touches an installed application.

Environment variables
---------------------
VPN_SOURCE              daily source-list URL
VPN_DATA                data / output dir (default ~/.local/share/vpn-list)
VPN_BIN                 cores dir (default <data>/bin)
VPN_EXTRA               file with extra subscription URLs (one per line)
VPN_PASSES              number of connectivity rounds (default 3)
VPN_KEEP                 rounds needed to keep a server (default 2)

Russia mobile edition
---------------------
VPN_CARRIER             mts | megafon | beeline | tele2 | auto (default auto)
VPN_THROTTLE            1/true/yes/on to force silent-throttling detection
VPN_THROTTLE_KBPS       throttled below this KB/s (default 50)
VPN_THROTTLE_TEST_SIZE  throughput test size in KB (default 100)
VPN_SUSTAINED_SECONDS   sustained-test duration in seconds (default 30)
VPN_THROTTLE_URL        throughput test URL (default speed.cloudflare.com)
VPN_GEO_CACHE           1/true to cache geolocation (default true)
"""
import os

HOME = os.path.expanduser('~')
XDG_DATA = os.environ.get('XDG_DATA_HOME') or os.path.join(HOME, '.local', 'share')

DATA = os.environ.get('VPN_DATA', os.path.join(XDG_DATA, 'vpn-list'))
WORK = os.path.join(DATA, 'work')
BODIES = os.path.join(DATA, 'bodies')
OUT = DATA

BIN = os.environ.get('VPN_BIN', os.path.join(DATA, 'bin'))
SB = os.path.join(BIN, 'sing-box')
XRAY = os.path.join(BIN, 'xray')

SOURCE_URL = os.environ.get(
    'VPN_SOURCE',
    'https://raw.githubusercontent.com/solovyov-jenya2004/all_subs/refs/heads/main/sources.txt')
EXTRA = os.environ.get('VPN_EXTRA', os.path.join(DATA, 'extra_sources.txt'))

# Default sources list (includes both original and additional sources)
DEFAULT_SOURCES = [
    # Original sources provided by user
    'https://raw.githubusercontent.com/vladvarp/Prometheus/refs/heads/main/WhiteList/vless.txt',
    'https://raw.githubusercontent.com/flaafix/AetrisVPN/refs/heads/main/AetrisVPN.txt',
    'https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_lite.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt',
    'https://raw.githubusercontent.com/gooseteam-hackers/GooseVPN/refs/heads/main/configs/balanced.txt wLTE',
    'https://raw.githubusercontent.com/OceaniaVPN/StekloVPN/main/configs/whitelist.txt',
    'https://raw.githubusercontent.com/gooseteam-hackers/GooseVPN/refs/heads/main/configs/plus.txt wLTE',
    'https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_universal.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt',
    'https://raw.githubusercontent.com/flaafix/AetrisVPN-white-list-lite/refs/heads/main/AetrisVPN.txt',
    'https://etoneya.su/whitelist',
    'https://vpn.akres.fun/bwl',
    'https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/refs/heads/main/kizyakbeta6.txt LTE',
    'https://gitverse.ru/api/repos/gidro/white/raw/branch/master/subscription.txt',
    'https://gitverse.ru/api/repos/Pizduk/PizdukVPN/raw/branch/master/WlSubPiz.txt',
    'https://gitverse.ru/api/repos/Pizduk/PizdukVPN/raw/branch/master/WLAutoPiz.txt',
    'https://gitverse.ru/api/repos/272/wl/raw/branch/master/whitelist',
    'https://gitverse.ru/api/repos/Pizduk/PizdukVPN/raw/branch/master/WaHapp',
    
    # Additional high-quality sources
    'https://sub.vlessfo.ru/vlessforu/working_configs.txt',  # added by user request (2026-11-03)
    'https://raw.githubusercontent.com/solovyov-jenya2004/all_subs/refs/heads/main/sources.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_SS+All_RUS.txt',
]

PASSES = int(os.environ.get('VPN_PASSES', '3'))
KEEP = int(os.environ.get('VPN_KEEP', '2'))

# Deep mode: also fetch the very large general lists (~2000 extra links).
DEEP = os.environ.get('VPN_DEEP', '').lower() in ('1', 'true', 'yes', 'on')

# Russian domains that are visible in the current whitelist/mobile profiles.
# Used for *ranking* and for the carrier filter (suffix match), never to
# discard a link on its own: the live connectivity test still decides.
RU_SNI_HINTS = (
    # universal / state
    'gosuslugi.ru', 'mos.ru', 'nalog.gov.ru', 'nalog.ru', 'rt.ru', 'sm.ru',
    # social & mail
    'vk.com', 'vkvideo.ru', 'userapi.com', 'ok.ru', 'mail.ru', 'max.ru',
    # yandex
    'yandex.ru', 'yandex.net', 'yastatic.net', 'api-maps.yandex.ru',
    # market / media
    'ozon.ru', 'wildberries.ru', 'avito.ru', 'dzen.ru', 'rutube.ru',
    'kinopoisk.ru', '2gis.ru', 'rbc.ru', 'lenta.ru', 'ria.ru',
    # banking / retail chains
    'sberbank.ru', 'sber.ru', 'tinkoff.ru', 'tbank.ru', 'vtb.ru',
    'x5.ru', '5post-gate.x5.ru', 'magnit.ru', 'auchan.ru',
    # operators
    'mts.ru', 'megafon.ru', 'beeline.ru', 'tele2.ru',
)

# --- Russia mobile edition ------------------------------------------------
CARRIER = os.environ.get('VPN_CARRIER', 'auto').lower()
THROTTLE = os.environ.get('VPN_THROTTLE', '').lower() in ('1', 'true', 'yes', 'on')
THROTTLE_KBPS = int(os.environ.get('VPN_THROTTLE_KBPS', '50'))
THROTTLE_TEST_SIZE = int(os.environ.get('VPN_THROTTLE_TEST_SIZE', '100'))
SUSTAINED_SECONDS = int(os.environ.get('VPN_SUSTAINED_SECONDS', '30'))
THROTTLE_URL = os.environ.get(
    'VPN_THROTTLE_URL', 'https://speed.cloudflare.com/__down?bytes={bytes}')
GEO_CACHE = os.environ.get('VPN_GEO_CACHE', 'true').lower() in ('1', 'true', 'yes', 'on')

# Fetch tuning: a dead subscription host must not stall the whole run.
FETCH_TIMEOUT = float(os.environ.get('VPN_FETCH_TIMEOUT', '25'))
FETCH_RETRIES = int(os.environ.get('VPN_FETCH_RETRIES', '1'))
FETCH_WORKERS = int(os.environ.get('VPN_FETCH_WORKERS', '12'))


def desktop_dir():
    """The user's real Desktop: VPN_DESKTOP, else ~/Desktop, else XDG."""
    override = os.environ.get('VPN_DESKTOP')
    if override:
        return os.path.expanduser(override)
    fallback = os.path.expanduser('~/Desktop')
    if os.path.isdir(fallback):
        return fallback
    try:
        import subprocess
        q = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True,
                           text=True, timeout=3).stdout.strip()
        if q and os.path.isdir(q):
            return q
    except Exception:
        pass
    return fallback


DESKTOP = desktop_dir()

T1 = 'https://www.gstatic.com/generate_204'
T2 = 'http://cp.cloudflare.com/generate_204'

USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'

# output paths (inside OUT) -- all (re)assigned by set_out()
LINKS = ALL = STABLE = STABLE_UNIQUE = STABLE_B64 = UNIQUE_B64 = None
BY_COUNTRY = COUNTRIES = THROTTLED = UNSTABLE = CARRIER_REPORT = None
CLASH = CLASH_SIMPLE = GEO_CACHE_FILE = None


def set_out(path):
    """Point every output path at *path*."""
    global OUT, LINKS, ALL, STABLE, STABLE_UNIQUE, STABLE_B64, UNIQUE_B64
    global BY_COUNTRY, COUNTRIES, THROTTLED, UNSTABLE, CARRIER_REPORT
    global CLASH, CLASH_SIMPLE, GEO_CACHE_FILE
    OUT = path
    LINKS = os.path.join(path, 'links.txt')
    ALL = os.path.join(path, 'working_all.txt')
    STABLE = os.path.join(path, 'working_stable.txt')
    STABLE_UNIQUE = os.path.join(path, 'working_stable_unique.txt')
    STABLE_B64 = os.path.join(path, 'working_stable_base64.txt')
    UNIQUE_B64 = os.path.join(path, 'working_unique_base64.txt')
    BY_COUNTRY = os.path.join(path, 'working_by_country.txt')
    COUNTRIES = os.path.join(path, 'countries.json')
    THROTTLED = os.path.join(path, 'working_throttled.txt')
    UNSTABLE = os.path.join(path, 'working_unstable.txt')
    CARRIER_REPORT = os.path.join(path, 'carrier_report.json')
    CLASH = os.path.join(path, 'clash.yaml')
    CLASH_SIMPLE = os.path.join(path, 'clash_simple.yaml')
    GEO_CACHE_FILE = os.path.join(path, 'geo_cache.json')


set_out(OUT)


def ensure_dirs():
    for d in (DATA, WORK, BODIES, BIN):
        os.makedirs(d, exist_ok=True)
