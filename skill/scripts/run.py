#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vpn-list — one-shot pipeline (app-agnostic, Russia-capable).

fetch daily source list -> download subscriptions -> extract share-links ->
filter by carrier/SNI -> test which servers really work (sing-box + Xray) ->
optionally detect silent throttling -> merge the working servers into one list
-> geolocate -> build Clash config(s).

It never touches any installed app; the output files can be imported into any
VPN client.

Usage:
  python3 run.py --single                  # ASK-FIRST workflow: one file on the Desktop
  python3 run.py --source URL              # use another source list (URL or local file)
  python3 run.py --links-file FILE         # test the share-links in FILE directly
  python3 run.py --limit 400               # quick trial on the first 400 links
  python3 run.py --passes 3 --keep 2
  python3 run.py --out DIR                 # write the files somewhere else
  python3 run.py --extra-sources           # add Russia-specific source lists
  python3 run.py --carrier megafon         # apply a carrier profile
  python3 run.py --throttle                # force throttling detection
  python3 run.py --skip-fetch              # reuse links.txt from the last run
  python3 run.py --only-kept               # reuse links.txt+counts.json, confirm survivors only
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402
import fetch  # noqa: E402
import retest  # noqa: E402
import enrich  # noqa: E402
import clash_build  # noqa: E402


# Extra Russia-focused subscription lists (used with --extra-sources).
# The three original lists are kept first; the rest come from the verified
# registry in sources_ru.py (same order as the curated core).
RU_EXTRA_SOURCES = [
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt',
    'https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-SNI-RU-all.txt',
]
try:
    import sources_ru
    for _u in sources_ru.curated_urls():
        if _u not in RU_EXTRA_SOURCES:
            RU_EXTRA_SOURCES.append(_u)
except Exception:  # noqa: BLE001 - registry is optional
    pass


def hp(u):
    try:
        if u.startswith('vmess://'):
            b = u[8:]
            j = json.loads(base64.b64decode(b + '=' * (-len(b) % 4)).decode('utf-8', 'ignore'))
            return (j.get('add'), j.get('port'))
        p = urlparse(u)
        return (p.hostname, p.port) if p.hostname and p.port else None
    except Exception:
        return None


def uniq(seq):
    seen, out = set(), []
    for l in seq:
        k = hp(l) or l
        if k in seen:
            continue
        seen.add(k)
        out.append(l)
    return out


# One-file mode: the only thing this skill leaves on the Desktop.
DESKTOP = common.DESKTOP
DEFAULT_SINGLE = os.path.expanduser(
    os.environ.get('VPN_SINGLE_OUT') or os.path.join(DESKTOP, 'vpn-servers.txt'))
OLD_DESKTOP_RESULTS = [
    os.path.join(DESKTOP, 'vpn-list'),
    os.path.join(DESKTOP, 'vpn-ready'),
    os.path.join(DESKTOP, 'vpn-ready.tar.gz'),
    os.path.join(DESKTOP, 'working_stable_unique.txt'),
    os.path.join(DESKTOP, 'working_stable_base64.txt'),
    os.path.join(DESKTOP, 'vpn-list-run.log'),
]


def delete_path(path):
    """Remove a file or directory if it exists (silently)."""
    if not path:
        return
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        elif os.path.exists(path) or os.path.islink(path):
            os.remove(path)
    except Exception as e:
        print(f'  ! تعذّر حذف {path}: {e}', flush=True)


def clean_old_results(single):
    """Always remove the previous run's output(s) before writing new ones."""
    targets = [single] if single else []
    targets += [p for p in OLD_DESKTOP_RESULTS if p != single]
    for p in targets:
        delete_path(p)
    print(f'  حُذفت النتائج القديمة ({len(targets)} مسار)', flush=True)


def read_links_file(path):
    """Read share-links from a file, accepting anything the user pasted."""
    text = open(os.path.expanduser(path), encoding='utf-8', errors='ignore').read()
    if '://' not in text:
        text = _decode_maybe_b64(text)
    links = re.findall(r'(?im)^\s*(?:vless|vmess|trojan|ss|ssr|hy2|hysteria2|hysteria|tuic)://\S+', text)
    return [l.strip() for l in links]


def _decode_maybe_b64(text):
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


def write_out(name, items):
    with open(os.path.join(common.OUT, name), 'w', encoding='utf-8') as f:
        f.write('\n'.join(items) + ('\n' if items else ''))


def ensure_cores():
    if os.path.exists(common.SB) and os.path.exists(common.XRAY):
        return True
    script = os.path.join(HERE, 'install_cores.sh')
    print('== تنزيل النوى (sing-box + Xray) ==', flush=True)
    subprocess.run(['bash', script, common.BIN])
    return os.path.exists(common.SB) and os.path.exists(common.XRAY)


def main():
    ap = argparse.ArgumentParser(description='vpn-list pipeline (files only)')
    ap.add_argument('--source', default=None, help='subscription-source URL (or local file)')
    ap.add_argument('--links-file', default=None,
                    help='test the share-links in this file directly (skips fetching)')
    ap.add_argument('--single', nargs='?', const=DEFAULT_SINGLE, default=None,
                    metavar='FILE',
                    help=f'write only one result file (default {DEFAULT_SINGLE})')
    ap.add_argument('--clean', action='store_true',
                    help='delete previous results on the Desktop before running')
    ap.add_argument('--out', default=common.OUT, help='output directory')
    ap.add_argument('--limit', type=int, default=0, help='test at most N links (quick run)')
    ap.add_argument('--passes', type=int, default=common.PASSES)
    ap.add_argument('--keep', type=int, default=common.KEEP)
    ap.add_argument('--carrier', default=common.CARRIER,
                    help='mts | megafon | beeline | tele2 | auto')
    ap.add_argument('--throttle', dest='throttle', action='store_true', default=None,
                    help='force silent-throttling detection')
    ap.add_argument('--no-throttle', dest='throttle', action='store_false',
                    help='disable silent-throttling detection')
    ap.add_argument('--skip-fetch', action='store_true', help='reuse the existing links.txt')
    ap.add_argument('--extra-sources', action='store_true', help='add the Russia-focused lists')
    ap.add_argument('--deep-sources', action='store_true',
                    help='also fetch the very large general lists (thousands of links)')
    ap.add_argument('--refresh-sources', action='store_true',
                    help='re-check the curated Russia sources and discover new GitHub ones first')
    ap.add_argument('--only-kept', action='store_true',
                    help='reuse links.txt + counts.json, confirm survivors only (fast salvage)')
    ap.add_argument('--no-confirm', action='store_true',
                    help='skip the low-load confirmation pass')
    a = ap.parse_args()
    if a.only_kept:
        a.skip_fetch = True
    if a.single:
        a.single = os.path.expanduser(a.single)
    if a.links_file:
        a.links_file = os.path.expanduser(a.links_file)
        a.skip_fetch = True
    
    # Ask for source URL if not provided — but never block an unattended run
    # (systemd/cron): fall back to the default source list instead of prompting.
    if not a.source and not a.links_file and not sys.stdin.isatty():
        a.source = common.SOURCE_URL
        print(f'لا إدخال تفاعلي: استخدام المصدر الافتراضي {a.source}', flush=True)
    if not a.source and not a.links_file:
        print('VPN Working List - اختر مصدر الاشتراكات', flush=True)
        print('1. الافتراضي (sources.txt)', flush=True)
        print('2. رابط مخصص', flush=True)
        print('3. ملف محلي', flush=True)
        choice = input('اختر (1/2/3): ').strip()
        
        if choice == '1':
            a.source = common.SOURCE_URL
            print(f'استخدم المصدر الافتراضي: {a.source}', flush=True)
            print(f'  - يحتوي على {len(common.DEFAULT_SOURCES)} مصدراً مختلفاً', flush=True)
        elif choice == '2':
            a.source = input('أدخل رابط الاشتراكات: ').strip()
            if not a.source:
                print('خطأ: يجب تحديد رابط', file=sys.stderr)
                sys.exit(1)
        elif choice == '3':
            local_file = input('أدخل مسار الملف المحلي: ').strip()
            if not local_file or not os.path.exists(local_file):
                print('خطأ: الملف غير موجود', file=sys.stderr)
                sys.exit(1)
            a.links_file = os.path.expanduser(local_file)
            a.skip_fetch = True
        else:
            print('خيار غير صالح', file=sys.stderr)
            sys.exit(1)

    # "Always delete the old results": one-file mode wipes the previous Desktop
    # outputs (and the target file) before doing any work.
    if a.single or a.clean:
        print('== 0/6 حذف النتائج القديمة ==', flush=True)
        clean_old_results(a.single)

    if a.deep_sources:
        common.DEEP = True
    if a.refresh_sources:
        try:
            import sources_ru
            print('== فحص المصادر الروسية ==', flush=True)
            sources_ru.refresh(discover=True, deep=common.DEEP, force=False)
        except Exception as exc:  # noqa: BLE001 - never block the run
            print(f'  ! تعذّر تحديث سجل المصادر: {exc}', flush=True)

    if a.out and os.path.abspath(a.out) != os.path.abspath(common.OUT):
        common.set_out(a.out)
    common.PASSES = a.passes
    common.KEEP = a.keep
    common.CARRIER = a.carrier
    common.ensure_dirs()
    os.makedirs(common.OUT, exist_ok=True)
    if not ensure_cores():
        print('✘ تعذّر توفير النوى (sing-box/Xray).')
        return 1

    t0 = time.time()

    # ---- 1/6 fetch ----------------------------------------------------
    if a.links_file:
        print('== 1/6 الروابط (من ملف) ==', flush=True)
        links = sorted(set(read_links_file(a.links_file)))
        if not links:
            print('✘ لا توجد روابط صالحة في الملف.')
            return 1
        with open(common.LINKS, 'w', encoding='utf-8') as f:
            f.write('\n'.join(links) + '\n')
        print(f'  روابط فريدة: {len(links)}', flush=True)
    elif a.skip_fetch and os.path.exists(common.LINKS):
        print('== 1/6 الجلب (متخطّى) ==', flush=True)
        links = [l.strip() for l in open(common.LINKS, encoding='utf-8') if l.strip()]
    else:
        print('== 1/6 جلب الاشتراكات ==', flush=True)
        if a.extra_sources:
            with open(common.EXTRA, 'w', encoding='utf-8') as f:
                f.write('\n'.join(RU_EXTRA_SOURCES) + '\n')
            print(f'  مصادر إضافية: {len(RU_EXTRA_SOURCES)}', flush=True)
        links = sorted(fetch.fetch_all(a.source))
        if not links:
            print('✘ لم تُستخرج أي روابط.')
            return 1
        # When only a slice is tested, start with the links that carry a
        # Russian whitelist SNI — they are the ones that survive TSPU.
        links = retest.rank_links(links)
        if a.limit and len(links) > a.limit:
            links = links[:a.limit]
        print(f'  روابط فريدة: {len(links)}', flush=True)

    # ---- 2/6 connectivity test ---------------------------------------
    counts_path = os.path.join(common.WORK, 'counts.json')
    if a.only_kept:
        if not (os.path.exists(common.LINKS) and os.path.exists(counts_path)):
            print('✘ --only-kept needs links.txt and counts.json from a previous run.')
            return 1
        print('\n== 2/6 إعادة استخدام نتائج سابقة ==', flush=True)
        links = [l.strip() for l in open(common.LINKS, encoding='utf-8') if l.strip()]
        counts = json.load(open(counts_path, encoding='utf-8'))
    else:
        print('\n== 2/6 اختبار الاتصال ==', flush=True)
        links = retest.filter_links(links, carrier=a.carrier)
        counts = retest.run_all(links)
        with open(counts_path, 'w', encoding='utf-8') as f:
            json.dump(counts, f, ensure_ascii=False)

    # ---- 2b/6 confirmation pass (fixes false negatives under load) ----
    survivors = [l for l in links if counts.get(l, 0) >= 1]
    if survivors and not a.no_confirm and len(survivors) < len(links):
        print(f'\n== 2b/6 تأكيد الناجين ({len(survivors)}) بحمل منخفض ==', flush=True)
        conf = {}
        for i in range(0, len(survivors), 120):
            for k, v in retest.run_all(survivors[i:i + 120], workers=32).items():
                conf[k] = max(conf.get(k, 0), v)
        for k in survivors:
            counts[k] = conf.get(k, 0)
        with open(counts_path, 'w', encoding='utf-8') as f:
            json.dump(counts, f, ensure_ascii=False)

    keep2 = [l for l in links if counts.get(l, 0) >= common.KEEP]
    stable = [l for l in links if counts.get(l, 0) >= common.PASSES]

    # ---- 3/6 throttling detection (optional) -------------------------
    throttle = a.throttle
    if throttle is None:
        throttle = (a.carrier != 'auto') or common.THROTTLE
    throttled, unstable, kbps_map = set(), set(), {}
    if throttle:
        print('\n== 3/6 كشف الخنق الصامت ==', flush=True)
        throttled, unstable, kbps_map = retest.throttle_test(stable, carrier=a.carrier)
    else:
        print('\n== 3/6 كشف الخنق (معطّل) ==', flush=True)

    stable_f = [l for l in stable if l not in throttled and l not in unstable]
    keep_f = [l for l in keep2 if l not in throttled and l not in unstable]
    su = uniq(stable_f)
    ku = uniq(keep_f)

    # ---- 4/6 write lists ---------------------------------------------
    print('\n== 4/6 كتابة الملفات ==', flush=True)
    write_out('working_all.txt', keep_f)
    write_out('working_unique.txt', ku)
    write_out('working_stable.txt', stable_f)
    write_out('working_stable_unique.txt', su)
    write_out('working_throttled.txt', sorted(throttled))
    write_out('working_unstable.txt', sorted(unstable))
    write_out('working_unique_base64.txt', [base64.b64encode(('\n'.join(ku) + '\n').encode()).decode()])
    write_out('working_stable_base64.txt', [base64.b64encode(('\n'.join(su) + '\n').encode()).decode()])
    if a.single:
        if su:
            os.makedirs(os.path.dirname(a.single) or '.', exist_ok=True)
            with open(a.single, 'w', encoding='utf-8') as f:
                f.write('\n'.join(su) + '\n')
            print(f'  ✔ ملف واحد فقط: {a.single}  ({len(su)} سيرفر)', flush=True)
        else:
            print('  ! لا سيرفرات مستقرة — لم يُكتب ملف نهائي', flush=True)
    print(f'  مستقرّ {common.PASSES}/{common.PASSES}: {len(stable)} | مقبول ≥{common.KEEP}: {len(keep2)} | '
          f'فريد مستقرّ: {len(su)} | مخنوق: {len(throttled)} | غير مستقرّ: {len(unstable)}')

    # ---- 5/6 geolocation ---------------------------------------------
    if a.single:
        print('\n== 5/6 تحديد الدول (متخطّى في وضع الملف الواحد) ==', flush=True)
    else:
        print('\n== 5/6 تحديد الدول ==', flush=True)
        enrich.main(su)

    # ---- 6/6 Clash ---------------------------------------------------
    if a.single:
        print('\n== 6/6 بناء Clash (متخطّى في وضع الملف الواحد) ==', flush=True)
    else:
        print('\n== 6/6 بناء Clash ==', flush=True)
        clash_build.main()

    report = {'carrier': a.carrier, 'throttle': bool(throttle), 'total_tested': len(links),
              'stable': len(stable), 'kept': len(keep2), 'unique_stable': len(su),
              'throttled': len(throttled), 'unstable': len(unstable),
              'throughput_kbps': kbps_map}
    json.dump(report, open(common.CARRIER_REPORT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    print(f'\n✔ تمّ ({int(time.time() - t0)} ثانية). الملفات في: {common.OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
