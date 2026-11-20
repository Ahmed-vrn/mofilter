#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPN Working List — تطبيق ويب مستقل بملف واحد
================================================
خادم ويب محلي (127.0.0.1) لواجهة عربية تُدير مهارة vpn-list:
  • عرض السيرفرات العاملة الحالية مع البحث والنسخ
  • تشغيل تحديث كامل / فحص سريع / إعادة فحص المحفوظ
  • متابعة سجل التشغيل لحظة بلحظة
  • تنزيل الملفات الجاهزة (vpn-servers.txt، clash.yaml، …)

يعمل بلا أي تثبيت أو حزم خارجية — بايثون 3 القياسي فقط.

الاستخدام:
    python3 vpn-web-app.py                 # يفتح المتصفح تلقائيًا
    python3 vpn-web-app.py --no-open       # بلا فتح المتصفح
    python3 vpn-web-app.py --port 9000     # منفذ محدد
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

APP_VERSION = "1.5.0"
# أيقونة التطبيق (64px) مضمّنة كي تظهر نافذة سطح المكتب بأيقونة صحيحة حتى بلا ملفات خارجية.
ICON_B64 = "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"
HOME = os.path.expanduser("~")
XDG_DATA = os.path.expanduser(os.environ.get("XDG_DATA_HOME") or os.path.join(HOME, ".local", "share"))
XDG_CONFIG = os.path.expanduser(os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"))


def _desktop_dir():
    """سطح المكتب الحقيقي (XDG) مع الرجوع إلى ~/Desktop."""
    env = os.environ.get("XDG_DESKTOP_DIR", "").strip()
    if env and os.path.isdir(os.path.expanduser(env)):
        return os.path.expanduser(env)
    if shutil.which("xdg-user-dir"):
        try:
            out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
            if out and os.path.isdir(out):
                return out
        except Exception:
            pass
    return os.path.join(HOME, "Desktop")


DESKTOP = _desktop_dir()
SKILL_DIR = os.path.join(os.environ.get("OPENCODE_SKILLS_DIR")
                         or os.path.join(XDG_CONFIG, "opencode", "skills"), "vpn-list")
RUN_PY = os.path.join(SKILL_DIR, "scripts", "run.py")
DATA_DIR = os.path.join(XDG_DATA, "vpn-list")
RESULTS_DIR = os.path.join(DESKTOP, "vpn-list")
READY_DIR = os.path.join(DESKTOP, "vpn-ready")
SERVERS_FILE = os.path.join(DESKTOP, "vpn-servers.txt")
APP_LOG = os.path.join(DATA_DIR, "webapp.log")
SYNC_PY = os.path.join(SKILL_DIR, "scripts", "github_sync.py")
GITHUB_CFG = os.path.join(XDG_CONFIG, "vpn-list", "github.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "webapp-settings.json")
MERGED_LINKS = os.path.join(DATA_DIR, "webapp-merged-links.txt")
ALL_LINKS = os.path.join(DATA_DIR, "webapp-all-links.txt")
RAW_LINKS = os.path.join(DATA_DIR, "webapp-raw-links.txt")

# قوائم روسية احتياطية — تُستخدم فقط إن لم تتوفر وحدة sources_ru في المهارة.
# المصدر الحقيقي هو سجل sources_ru.py (أساسي + موسّع + مكتشف من GitHub).
RU_EXTRA_SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/wlunlocker/vpn-configs/HEAD/whitelist_all.txt",
    "https://raw.githubusercontent.com/wlunlocker/vpn-configs/HEAD/whitelist_cidr1_ru.txt",
    "https://raw.githubusercontent.com/wlunlocker/vpn-configs/HEAD/whitelist_cidr2_ru.txt",
    "https://raw.githubusercontent.com/FLAT447/v2ray-lists/HEAD/WHITE_LITE.txt",
    "https://raw.githubusercontent.com/aviamastersgh/vpn-free-russia/HEAD/ru_configs.txt",
]

# يجلب الاشتراكات الحديثة، يدمجها مع المخزّنة، ثم يكتب الملف المدمج
FETCH_CODE = r"""
import json, os, sys
skill = os.environ["WEBAPP_SKILL"]
data = os.environ["WEBAPP_DATA"]
sys.path.insert(0, os.path.join(skill, "scripts"))
import common, fetch

# سجل المصادر الروسية: أساسي + موسّع + مكتشف من GitHub (حديثًا فقط)
source_count = 0
try:
    import sources_ru
    try:
        urls = sources_ru.cached_urls(deep=os.environ.get("WEBAPP_DEEP") == "1")
        source_count = len(urls)
    except Exception as exc:
        print("  ! سجل المصادر: %s" % exc, flush=True)
except Exception:
    # نسخة مهارة قديمة بلا sources_ru — استخدم القوائم الاحتياطية كما كان
    try:
        extras = [u.strip() for u in os.environ.get("WEBAPP_RU_EXTRA", "").split(",") if u.strip()]
        if extras:
            with open(common.EXTRA, "w", encoding="utf-8") as fh:
                fh.write("\n".join(extras) + "\n")
    except OSError:
        pass

print("== 0/6 بحث عن اشتراكات حديثة ==", flush=True)
if source_count:
    print("  المصادر الروسية الجاهزة: %d" % source_count, flush=True)
links_path = os.path.join(data, "links.txt")
old = []
if os.path.isfile(links_path):
    with open(links_path, encoding="utf-8", errors="ignore") as fh:
        old = [ln.strip() for ln in fh if "://" in ln]
fresh = fetch.fetch_all()
seen, merged = set(), []
for u in list(fresh) + old:
    if u not in seen:
        seen.add(u)
        merged.append(u)
with open(os.environ["WEBAPP_RAW"], "w", encoding="utf-8") as fh:
    fh.write("\n".join(merged) + "\n")
# fetch_all كتب links.txt بالروابط الجديدة فقط — نعيد المخزّن كما كان
with open(links_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(old) + ("\n" if old else ""))
print("  دُمج: جديد %d + مخزّن %d = %d رابطًا" % (len(fresh), len(old), len(merged)), flush=True)
try:
    health = json.load(open(os.path.join(data, "source_health.json"), encoding="utf-8"))
    detail = [s for s in health.get("detail", []) if s.get("ok")]
    detail.sort(key=lambda s: s.get("new", 0), reverse=True)
    print("  مصادر ناجحة: %d/%d" % (health.get("sources", 0), health.get("sources", 0) + health.get("failed", 0)), flush=True)
    for s in detail[:3]:
        if s.get("new"):
            print("   + %s…  %d رابطًا جديدًا" % (s["url"][:64], s["new"]), flush=True)
except Exception:
    pass
"""
BACKUP_DIR = os.path.join(DATA_DIR, "webapp-backup")
BACKUP_FILE = os.path.join(BACKUP_DIR, "vpn-servers.txt")

DOWNLOADS = {
    "servers": SERVERS_FILE,
    "stable": "working_stable_unique.txt",
    "by_country": "working_by_country.txt",
    "clash": "clash.yaml",
    "clash_simple": "clash_simple.yaml",
    "base64": "working_stable_base64.txt",
}


def resolve_result(name):
    """أحدث نسخة من ملف نتيجة: على سطح المكتب أو في مجلد البيانات أو مجلد الجاهز."""
    candidates = [
        os.path.join(RESULTS_DIR, name),
        os.path.join(DATA_DIR, name),
        os.path.join(READY_DIR, name),
    ]
    found = [p for p in candidates if os.path.isfile(p)]
    if not found:
        return candidates[0]
    return max(found, key=os.path.getmtime)


def current_servers_file():
    """الملف الذي تعرضه الواجهة: vpn-servers.txt وإلا أحدث نتيجة مستقرة."""
    if os.path.isfile(SERVERS_FILE) and os.path.getsize(SERVERS_FILE) > 0:
        return SERVERS_FILE
    alt = resolve_result("working_stable_unique.txt")
    return alt if os.path.isfile(alt) else SERVERS_FILE


# عقد مع سكربت المهارة run.py: يجب أن يطبع مراحل بصيغة "== n/6"
# وإلا انكسر شريط التقدم صامتًا. لا تغيّر هذا التنسيق في run.py
# دون تحديث STAGE_RE هنا.
STAGE_RE = re.compile(r"==\s*(\d)\s*/\s*6")
EMOJI_FLAG_RE = re.compile(
    "[\U0001F1E6-\U0001F1FF]{2}"
)


# --------------------------------------------------------------------------
#  أدوات مساعدة
# --------------------------------------------------------------------------
def read_lines(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return [ln.strip() for ln in fh if ln.strip()]
    except OSError:
        return []


def count_lines(path):
    total = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.strip():
                    total += 1
    except OSError:
        return 0
    return total


def mtime_str(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return ""


def human_size(path):
    try:
        n = os.path.getsize(path)
    except OSError:
        return ""
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return "%d %s" % (n, unit)
        n /= 1024.0
    return "%.1f GB" % n


def flag_for(code):
    code = (code or "").upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return chr(0x1F1E6 + ord(code[0]) - 65) + chr(0x1F1E6 + ord(code[1]) - 65)


def b64decode_text(blob):
    """فك base64 مع دعم urlsafe والحشو الناقص."""
    blob = (blob or "").strip().replace("-", "+").replace("_", "/")
    return base64.b64decode(blob + "=" * (-len(blob) % 4)).decode("utf-8", "ignore")


def tag_of(raw):
    if "#" in raw:
        return unquote(raw.split("#", 1)[1]).strip()
    return ""


def parse_link(raw):
    raw = raw.strip()
    if not raw or "://" not in raw:
        return None
    scheme = raw.split("://", 1)[0].lower()
    host, port, name = "", "", tag_of(raw)
    try:
        if scheme == "vmess":
            blob = raw.split("://", 1)[1].split("#", 1)[0]
            data = json.loads(b64decode_text(blob))
            host = str(data.get("add") or "")
            port = str(data.get("port") or "")
            name = str(data.get("ps") or name)
        elif scheme == "ss" and "@" not in raw.split("://", 1)[1].split("#", 1)[0]:
            # صيغة ss القديمة: ss://base64(method:password@host:port)#name
            blob = raw.split("://", 1)[1].split("#", 1)[0].split("?", 1)[0]
            decoded = b64decode_text(blob)
            _userinfo, sep, hostport = decoded.rpartition("@")
            if sep:
                parsed = urlparse("ss://" + hostport)
                host = parsed.hostname or ""
                port = str(parsed.port or "")
            elif ":" in decoded:
                host, _, port = decoded.rpartition(":")
        else:
            parsed = urlparse(raw.split("#", 1)[0])
            host = parsed.hostname or ""
            port = str(parsed.port or "")
    except Exception:
        pass
    flag = ""
    match = EMOJI_FLAG_RE.search(name)
    if match:
        flag = match.group(0)
        name = (name[: match.start()] + name[match.end():]).strip(" -_|·")
    if not name:
        name = host or raw[:40]
    return {
        "raw": raw,
        "name": name,
        "proto": scheme,
        "host": host,
        "port": port,
        "flag": flag,
    }


def load_servers():
    raw = read_lines(current_servers_file())
    out = []
    for line in raw:
        item = parse_link(line)
        if item:
            out.append(item)
    return out


def country_map():
    try:
        with open(os.path.join(RESULTS_DIR, "countries.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


# --------------------------------------------------------------------------
#  إزالة التكرار قبل الفحص
# --------------------------------------------------------------------------

# إزالة التكرار قبل الفحص: نصي / ذكي (host,port,sni) / حسب الخادم (host,port)
DEDUPE_CODE = r"""
import os, sys, json, base64
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.join(os.environ["WEBAPP_SKILL"], "scripts"))
import fetch, retest

mode = os.environ.get("WEBAPP_DEDUPE", "smart")
carrier = os.environ.get("WEBAPP_CARRIER", "auto")
limit = int(os.environ.get("WEBAPP_LIMIT", "0") or 0)
src = os.environ["WEBAPP_RAW"]

with open(src, encoding="utf-8", errors="ignore") as fh:
    raw = [ln.strip() for ln in fh if "://" in ln]

# تعقيم + إسقاط الصيغ التي لا تستطيع النوى بناء اتصال منها (توفير وقت الفحص)
lines = []
seen_raw = set()
for ln in raw:
    link = fetch.clean_link(ln)
    if link and link not in seen_raw:
        seen_raw.add(link)
        lines.append(link)
cleaned = retest.usable_links(lines)
if len(cleaned) != len(lines):
    print("  تعقيم الروابط: %d → %d" % (len(lines), len(cleaned)), flush=True)
lines = cleaned


def parts(link):
    try:
        if link.startswith("vmess://"):
            b = link[8:]
            j = json.loads(base64.b64decode(b + "=" * (-len(b) % 4)).decode("utf-8", "ignore"))
            return str(j.get("add") or ""), str(j.get("port") or ""), str(j.get("sni") or j.get("host") or "")
        p = urlparse(link)
        q = {k.lower(): v[0] for k, v in parse_qs(p.query, keep_blank_values=True).items()}
        return (p.hostname or ""), str(p.port or ""), (q.get("sni") or q.get("servername") or q.get("peer") or q.get("host") or "")
    except Exception:
        return "", "", ""


def key_of(link):
    host, port, sni = parts(link)
    if not host:
        return ("raw", link)
    if mode == "server":
        return (host, port)
    if mode == "smart":
        return (host, port, sni)
    return ("raw", link)


allowed = retest.CARRIER_PROFILES.get(carrier, {}).get("allowed_sni", [])


def score(sni):
    if not sni:
        return 0
    if any(sni == a or sni.endswith("." + a) for a in allowed) or retest.is_ru_sni(sni):
        return 2
    return 1


best, order = {}, []
for link in lines:
    k = key_of(link)
    _, _, sni = parts(link)
    sc = score(sni)
    if k not in best:
        best[k] = [sc, link]
        order.append(k)
    elif sc > best[k][0]:
        best[k] = [sc, link]

deduped = [best[k][1] for k in order]
# عند وجود حد: ابدأ بالروابط التي تحمل SNI روسيًا (الأقرب للنجاح عبر TSPU)
ranked = sorted(deduped, key=lambda l: score(parts(l)[2]), reverse=True)
full = deduped
tested = ranked[:limit] if (limit and len(ranked) > limit) else ranked

print("  إزالة التكرار (%s): %d → %d  (أُزيل %d)" %
      (mode, len(lines), len(full), len(lines) - len(full)), flush=True)
if limit and len(full) > limit:
    ru_first = sum(1 for l in tested if score(parts(l)[2]) == 2)
    print("  للفحص: %d رابطًا (الحد %d، منها %d بـ SNI روسي)" %
          (len(tested), limit, ru_first), flush=True)

for path, data in ((os.environ["WEBAPP_ALL"], full),
                   (os.environ["WEBAPP_MERGED"], tested),
                   (os.path.join(os.environ["WEBAPP_DATA"], "links.txt"), full)):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(data) + ("\n" if data else ""))
"""


# --------------------------------------------------------------------------
#  النشر إلى GitHub
# --------------------------------------------------------------------------
SYNC = {"running": False, "ok": None, "message": "", "time": "", "url": ""}
SYNC_LOCK = threading.Lock()


def github_config():
    try:
        with open(GITHUB_CFG, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def repo_url(cfg=None):
    cfg = cfg or github_config()
    if not cfg.get("owner") or not cfg.get("repo"):
        return ""
    return "https://github.com/%s/%s/blob/%s/%s" % (
        cfg.get("owner"), cfg.get("repo"), cfg.get("branch", "main"), cfg.get("path", "vpn-servers.txt"))


def load_settings():
    defaults = {"auto_sync": True}
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            defaults.update(data)
    except Exception:
        pass
    return defaults


def save_settings(data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def sync_status():
    with SYNC_LOCK:
        return dict(SYNC)


def _sync_payload():
    data = sync_status()
    if not data.get("running") and not data.get("time"):
        last = load_settings().get("last_sync") or {}
        if isinstance(last, dict) and last.get("time"):
            data.update({"time": last.get("time", ""), "ok": last.get("ok"),
                         "message": last.get("message", "")})
    return data


def start_sync(force=False):
    with SYNC_LOCK:
        if SYNC["running"]:
            return False, "النشر قيد التنفيذ حاليًا"
        SYNC.update(running=True, ok=None, message="جارٍ النشر إلى GitHub…")
    threading.Thread(target=_sync_worker, args=(force,), daemon=True).start()
    return True, ""


def _sync_worker(force):
    ok, msg = False, ""
    cfg = github_config()
    try:
        if not cfg.get("token"):
            msg = "GitHub غير مضبوط على هذا الجهاز (لا يوجد توكن في ~/.config/vpn-list/github.json)"
        elif not os.path.isfile(SYNC_PY):
            msg = "سكربت المزامنة غير موجود"
        elif not os.path.isfile(SERVERS_FILE):
            msg = "ملف vpn-servers.txt غير موجود"
        else:
            args = [sys.executable, "-u", SYNC_PY, "--file", SERVERS_FILE]
            if cfg.get("public"):
                args.append("--public")
            if force:
                args.append("--force")
            proc = subprocess.run(args, cwd=SKILL_DIR, capture_output=True, text=True, timeout=180)
            out = ((proc.stdout or "") + (proc.stderr or "")).strip()
            ok = proc.returncode == 0
            lines = [ln for ln in out.splitlines() if ln.strip()]
            msg = lines[-1] if lines else ("تم النشر" if ok else "فشل النشر")
    except subprocess.TimeoutExpired:
        msg = "انتهت مهلة النشر (180 ثانية)"
    except Exception as exc:
        msg = "خطأ: %s" % exc

    with SYNC_LOCK:
        SYNC.update(running=False, ok=ok, message=msg,
                    time=datetime.now().strftime("%H:%M"), url=repo_url(cfg))
    RUNNER.log("GitHub: %s" % msg)
    try:
        data = load_settings()
        data["last_sync"] = {"time": SYNC["time"], "ok": ok, "message": msg}
        save_settings(data)
    except Exception:
        pass


# --------------------------------------------------------------------------
#  حالة التشغيل
# --------------------------------------------------------------------------
class Runner:
    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.mode = ""
        self.started = 0.0
        self.ended = 0.0
        self.exit_code = None
        self.stage = ""
        self.lines = deque(maxlen=4000)
        self.reader = None
        self._stop_requested = False
        self.active = False
        self.limited = False

    # ---------------------------------------------------------------
    def is_running(self):
        with self.lock:
            return self.active

    def log(self, text):
        stamp = datetime.now().strftime("%H:%M:%S")
        line = "[%s] %s" % (stamp, text)
        self.lines.append(line)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(APP_LOG, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    def _rotate_log(self):
        """أبقِ السجل صغيرًا: أعد تسميته عند تجاوز 5 MB."""
        try:
            if os.path.getsize(APP_LOG) > 5 * 1024 * 1024:
                os.replace(APP_LOG, APP_LOG + ".1")
        except OSError:
            pass

    def snapshot(self):
        running = self.is_running()
        with self.lock:
            return {
                "running": running,
                "mode": self.mode,
                "elapsed": int(time.time() - self.started) if self.started else 0,
                "exit_code": self.exit_code,
                "stage": self.stage,
                "pid": self.proc.pid if running and self.proc else None,
            }

    # ---------------------------------------------------------------
    def start(self, mode, source="", limit=0, carrier="auto", throttle=None, dedupe="smart"):
        if not os.path.isfile(RUN_PY):
            return False, "مهارة vpn-list غير مثبتة في %s" % SKILL_DIR
        with self.lock:
            if self.active:
                return False, "هناك عملية تحديث قيد التشغيل بالفعل"

        try:
            plan = self._build_plan(mode, source, limit, carrier, throttle, dedupe)
        except RuntimeError as exc:
            return False, str(exc)

        if mode == "russia":
            data = load_settings()
            data.update({"carrier": carrier or "auto", "throttle": bool(throttle), "dedupe": dedupe,
                         "rus_limit": max(0, int(limit or 0))})
            save_settings(data)

        self._backup_all()
        self._rotate_log()
        self.lines.clear()
        self.exit_code = None
        self.stage = ""
        self.started = time.time()
        self.ended = 0.0
        self.mode = mode
        self._stop_requested = False
        self.limited = bool(limit) and mode in ("russia", "quick", "resume")
        with self.lock:
            self.active = True

        self.log("بدأ التشغيل (%s) — %d مرحلة" % (self._mode_label(mode), len(plan)))
        threading.Thread(target=self._run_plan, args=(plan,), daemon=True).start()
        return True, ""

    def _run_command(self, mode, source="", limit=0, carrier="auto", throttle=None):
        args = [sys.executable, "-u", RUN_PY, "--single", "--no-confirm"]
        if mode == "quick":
            args += ["--limit", str(limit or 150)]
        elif mode == "resume":
            if not os.path.isfile(MERGED_LINKS):
                raise RuntimeError("ملف الروابط المحفوظ غير موجود — شغّل تحديثًا كاملًا أولًا")
            args += ["--links-file", MERGED_LINKS]
        elif mode == "russia":
            args += ["--links-file", MERGED_LINKS, "--carrier", carrier or "auto"]
            if throttle:
                args += ["--throttle"]
        if source:
            args += ["--source", source]
        return (args, {"VPN_THRONE_SYNC": "0", "VPN_DESKTOP": DESKTOP,
                       "VPN_DATA": DATA_DIR, "VPN_SINGLE_OUT": SERVERS_FILE})

    def _fetch_command(self):
        args = [sys.executable, "-u", "-c", FETCH_CODE]
        env = {
            "WEBAPP_SKILL": SKILL_DIR,
            "WEBAPP_DATA": DATA_DIR,
            "WEBAPP_RAW": RAW_LINKS,
            "WEBAPP_RU_EXTRA": ",".join(RU_EXTRA_SOURCES),
            "WEBAPP_DEEP": "1" if (os.environ.get("VPN_DEEP", "").lower() in ("1", "true", "yes", "on")
                                    or bool(load_settings().get("deep"))) else "0",
            "VPN_THRONE_SYNC": "0",
            "VPN_DESKTOP": DESKTOP,
            "VPN_DATA": DATA_DIR,
        }
        return (args, env)

    def _dedupe_command(self, src, limit, carrier, dedupe):
        args = [sys.executable, "-u", "-c", DEDUPE_CODE]
        env = {
            "WEBAPP_SKILL": SKILL_DIR,
            "WEBAPP_DATA": DATA_DIR,
            "WEBAPP_ALL": ALL_LINKS,
            "WEBAPP_MERGED": MERGED_LINKS,
            "WEBAPP_RAW": src,
            "WEBAPP_DEDUPE": dedupe or "smart",
            "WEBAPP_CARRIER": carrier or "auto",
            "WEBAPP_LIMIT": str(limit or 0),
            "VPN_THRONE_SYNC": "0",
            "VPN_DESKTOP": DESKTOP,
            "VPN_DATA": DATA_DIR,
        }
        return (args, env)

    def _build_plan(self, mode, source, limit, carrier, throttle, dedupe="smart"):
        if mode == "russia":
            return [self._fetch_command(),
                    self._dedupe_command(RAW_LINKS, limit, carrier, dedupe),
                    self._run_command("russia", carrier=carrier, throttle=throttle)]
        if mode == "resume":
            return [self._dedupe_command(os.path.join(DATA_DIR, "links.txt"), limit or 150, carrier, dedupe),
                    self._run_command("resume")]
        return [self._run_command(mode, source=source, limit=limit)]

    def _mode_label(self, mode):
        return {
            "full": "تحديث كامل",
            "quick": "فحص سريع",
            "resume": "إعادة فحص المحفوظ",
            "source": "مصدر مخصص",
            "russia": "تحديث روسي",
        }.get(mode, mode)

    def _run_plan(self, plan):
        rc = 0
        try:
            for args, extra_env in plan:
                env = dict(os.environ)
                env.update(extra_env)
                env.setdefault("PYTHONUNBUFFERED", "1")
                try:
                    proc = subprocess.Popen(
                        args, cwd=SKILL_DIR, stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=1, env=env, start_new_session=True)
                except OSError as exc:
                    self.lines.append("[خطأ] تعذّر تشغيل العملية: %s" % exc)
                    rc = 1
                    break
                with self.lock:
                    self.proc = proc
                self._stream(proc)
                rc = proc.wait()
                if rc != 0:
                    break
        except Exception as exc:  # لا تبقِ الواجهة عالقة في حالة "قيد التشغيل"
            self.lines.append("[خطأ غير متوقع] %s" % exc)
            rc = 1
        finally:
            try:
                self._finish(rc)
            finally:
                with self.lock:
                    self.proc = None
                    self.active = False

    def _stream(self, proc):
        log_fh = None
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            log_fh = open(APP_LOG, "a", encoding="utf-8")
        except OSError:
            pass
        try:
            for line in proc.stdout:
                line = line.rstrip("\n")
                if not line:
                    self.lines.append("")
                    continue
                match = STAGE_RE.search(line)
                if match:
                    self.stage = "%s/6" % match.group(1)
                self.lines.append(line)
                if log_fh:
                    try:
                        log_fh.write(line + "\n")
                    except OSError:
                        pass
        except Exception as exc:
            self.lines.append("[قارئ السجل] %s" % exc)
        finally:
            if log_fh:
                try:
                    log_fh.close()
                except OSError:
                    pass

    def _finish(self, code):
        cancelled = self._stop_requested
        if cancelled and code == 0:
            code = 130  # أُوقف بطلب المستخدم — لا تعتبره نجاحًا
        self.exit_code = code
        self.ended = time.time()
        self._restore_links()
        restored = False
        if code != 0 or count_lines(SERVERS_FILE) == 0:
            restored = self._restore_backup()
        if restored:
            reason = ("لم تُنتج القائمة أي سيرفر" if code == 0
                      else "فشل التشغيل برمز %s" % code)
            self.log("أُعيدت القائمة السابقة تلقائيًا (%s)" % reason)
        elif code == 0:
            self.log("انتهى التشغيل بنجاح — %d سيرفر" % count_lines(SERVERS_FILE))
            if self.limited:
                self.log("نتيجة جزئية (حد الفحص) — لم يُنشر تلقائيًا إلى GitHub")
            elif load_settings().get("auto_sync", True) and github_config().get("token"):
                start_sync(force=False)
        else:
            self.log("انتهى التشغيل برمز %s" % code)
        self.stage = "done" if code == 0 else "failed"
        with self.lock:
            self.proc = None
            self.active = False

    def _backup_all(self):
        """نسخة أمان كاملة قبل أي تشغيل (القائمة + النتائج + الحزمة)."""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            shutil.rmtree(BACKUP_DIR, ignore_errors=True)
            os.makedirs(BACKUP_DIR, exist_ok=True)
            if os.path.isfile(SERVERS_FILE):
                shutil.copy2(SERVERS_FILE, BACKUP_FILE)
            results_dir = os.path.join(BACKUP_DIR, "results")
            os.makedirs(results_dir, exist_ok=True)
            for name in ("working_stable_unique.txt", "working_unique.txt", "working_stable.txt",
                         "working_all.txt", "working_by_country.txt", "clash.yaml",
                         "clash_simple.yaml", "countries.json", "carrier_report.json",
                         "geo_cache.json"):
                src = os.path.join(DATA_DIR, name)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(results_dir, name))
            links_now = os.path.join(DATA_DIR, "links.txt")
            if os.path.isfile(links_now):
                shutil.copy2(links_now, os.path.join(BACKUP_DIR, "links.txt"))
            for src, name in ((RESULTS_DIR, "vpn-list"), (READY_DIR, "vpn-ready")):
                if os.path.isdir(src):
                    shutil.copytree(src, os.path.join(BACKUP_DIR, name))
            tarball = READY_DIR + ".tar.gz"
            if os.path.isfile(tarball):
                shutil.copy2(tarball, os.path.join(BACKUP_DIR, "vpn-ready.tar.gz"))
        except OSError:
            pass

    def _restore_links(self):
        """أعد ملف الروابط الكامل بعد التشغيل (الفحص يستخدم مجموعة جزئية)."""
        links_now = os.path.join(DATA_DIR, "links.txt")
        try:
            if self.mode == "russia" and os.path.isfile(ALL_LINKS):
                shutil.copy2(ALL_LINKS, links_now)
                return
            bak = os.path.join(BACKUP_DIR, "links.txt")
            if os.path.isfile(bak) and os.path.isfile(links_now):
                if count_lines(links_now) < count_lines(bak):
                    shutil.copy2(bak, links_now)
            elif os.path.isfile(bak) and not os.path.isfile(links_now):
                shutil.copy2(bak, links_now)
        except OSError:
            pass

    def _restore_backup(self):
        restored = False
        try:
            if os.path.isfile(BACKUP_FILE) and os.path.getsize(BACKUP_FILE) > 0:
                shutil.copy2(BACKUP_FILE, SERVERS_FILE)
                restored = True
            results_backup = os.path.join(BACKUP_DIR, "results")
            if os.path.isdir(results_backup):
                for name in os.listdir(results_backup):
                    srcf = os.path.join(results_backup, name)
                    if os.path.isfile(srcf):
                        shutil.copy2(srcf, os.path.join(DATA_DIR, name))
                restored = True
            for name, dst in (("vpn-list", RESULTS_DIR), ("vpn-ready", READY_DIR)):
                src = os.path.join(BACKUP_DIR, name)
                if os.path.isdir(src):
                    shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(src, dst)
                    restored = True
            tarball_src = os.path.join(BACKUP_DIR, "vpn-ready.tar.gz")
            if os.path.isfile(tarball_src):
                shutil.copy2(tarball_src, READY_DIR + ".tar.gz")
        except OSError:
            pass
        return restored

    def cancel(self):
        with self.lock:
            proc = self.proc
        if proc is None or proc.poll() is not None:
            return False, "لا توجد عملية قيد التشغيل"
        self._stop_requested = True
        self.log("طلب إيقاف — إرسال SIGTERM")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except OSError:
            try:
                proc.terminate()
            except OSError:
                pass

        # انتظر حتى 5 ثوانٍ باستخدام waitpid(WNOHANG) — أدق من poll()،
        # ولا يتعارض مع Popen.wait() في خيط التشغيل.
        import errno
        reaped = False
        for _ in range(20):
            try:
                pid, _status = os.waitpid(proc.pid, os.WNOHANG)
            except ChildProcessError:
                reaped = True
                break
            except OSError as exc:
                if exc.errno != errno.ECHILD:
                    self.log("تعذّر انتظار العملية: %s" % exc)
                reaped = True
                break
            if pid == proc.pid:
                reaped = True
                break
            time.sleep(0.25)

        if reaped:
            proc.returncode = -signal.SIGTERM  # الإيقاف ليس نجاحًا
            self.log("توقّفت العملية بأمر الإيقاف")
            return True, ""

        # لم يستجب خلال 5 ثوانٍ — اقتل المجموعة كلها ثم انتظر قليلًا
        self.log("العملية لم تستجب خلال 5 ثوانٍ — إرسال SIGKILL")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
        try:
            os.waitpid(proc.pid, 0)
        except OSError:
            pass
        proc.returncode = -signal.SIGKILL
        return True, ""


RUNNER = Runner()


# --------------------------------------------------------------------------
#  الواجهة (HTML + CSS + JS) — مضمّنة بالكامل، بلا أي اتصال خارجي
# --------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>مفلتر السيرفرات — لوحة التحكم</title>
<link rel="icon" type="image/png" href="data:image/png;base64,__ICON__">
<link rel="apple-touch-icon" href="data:image/png;base64,__ICON__">
<style>
  :root{
    --bg:#070c14; --bg2:#0b1220; --card:#101a2b; --card2:#0d1626;
    --line:#1d2b40; --line2:#24344d;
    --txt:#e8eef7; --mut:#8fa3bd; --dim:#5f7590;
    --teal:#2ec4b6; --teal2:#1f9e93; --blue:#5b8cff; --amber:#f5a623; --red:#ef5b5b; --green:#3ddc97;
    --radius:14px;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    background:
      radial-gradient(1100px 600px at 85% -10%, rgba(46,196,182,.14), transparent 60%),
      radial-gradient(900px 500px at -5% 105%, rgba(91,140,255,.10), transparent 55%),
      var(--bg);
    color:var(--txt);
    font-family:"Noto Kufi Arabic","Noto Naskh Arabic","Segoe UI",system-ui,sans-serif;
    min-height:100vh; direction:rtl;
  }
  a{color:var(--teal);text-decoration:none}
  .wrap{max-width:1280px;margin:0 auto;padding:22px 22px 40px}

  /* ---------- topbar ---------- */
  .top{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:22px}
  .logo{width:46px;height:46px;border-radius:13px;background:linear-gradient(145deg,#123049,#0b1a2c);
        display:flex;align-items:center;justify-content:center;border:1px solid var(--line2)}
  .logo svg{width:26px;height:26px}
  .brand h1{font-size:19px;margin:0;font-weight:800;letter-spacing:.2px}
  .brand p{margin:2px 0 0;font-size:11.5px;color:var(--mut)}
  .spacer{flex:1}
  .pill{display:inline-flex;align-items:center;gap:7px;padding:7px 13px;border-radius:99px;
        font-size:11.5px;font-weight:700;border:1px solid var(--line2);background:var(--card)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--dim);box-shadow:0 0 0 3px rgba(255,255,255,.03)}
  .dot.on{background:var(--green);box-shadow:0 0 0 3px rgba(61,220,151,.12);animation:pulse 1.8s infinite}
  .dot.run{background:var(--amber);box-shadow:0 0 0 3px rgba(245,166,35,.14);animation:pulse 1.2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
  .port{font-family:"DejaVu Sans Mono",monospace;font-size:11px;color:var(--mut);direction:ltr}

  /* ---------- cards ---------- */
  .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:16px}
  .stat{background:linear-gradient(160deg,var(--card),var(--card2));border:1px solid var(--line);
        border-radius:var(--radius);padding:15px 16px;position:relative;overflow:hidden}
  .stat::after{content:"";position:absolute;inset:auto -30% -60% auto;width:120px;height:120px;
        background:radial-gradient(circle,rgba(46,196,182,.10),transparent 70%)}
  .stat .k{font-size:11px;color:var(--mut);margin-bottom:7px}
  .stat .v{font-size:27px;font-weight:800;line-height:1.1}
  .stat .s{font-size:10.5px;color:var(--dim);margin-top:5px}
  .stat.teal .v{color:var(--teal)} .stat.blue .v{color:var(--blue)}
  .stat.amber .v{color:var(--amber)} .stat.white .v{font-size:15px;color:var(--txt);padding-top:8px}

  /* ---------- actions ---------- */
  .panel{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:16px}
  .actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
  .btn{appearance:none;border:1px solid var(--line2);background:#16243a;color:var(--txt);
       padding:11px 17px;border-radius:11px;font-family:inherit;font-size:12.5px;font-weight:700;
       cursor:pointer;display:inline-flex;align-items:center;gap:8px;transition:.16s;white-space:nowrap}
  .btn:hover:not(:disabled){background:#1c2d47;border-color:#2f4463;transform:translateY(-1px)}
  .btn:disabled{opacity:.42;cursor:not-allowed;transform:none}
  .btn.gh-off{opacity:.55;cursor:not-allowed}
  .btn.gh-off:hover{background:#16243a;border-color:var(--line2);transform:none}
  .btn.primary{background:linear-gradient(145deg,var(--teal2),#14786f);border-color:#2ec4b6;color:#04120f}
  .btn.primary:hover:not(:disabled){background:linear-gradient(145deg,#25b3a6,#178a80)}
  .btn.blue{background:linear-gradient(145deg,#3f6fd8,#2f57ae);border-color:#5b8cff;color:#f2f6ff}
  .btn.danger{background:#3a1620;border-color:#7a2b3a;color:#ffb3bf}
  .btn.danger:hover:not(:disabled){background:#4a1b27}
  .btn.ghost{background:transparent}
  .btn svg{width:15px;height:15px}
  .sel,.num{background:#0a1322;border:1px solid var(--line2);border-radius:10px;color:var(--txt);
            font-family:inherit;font-size:12px;padding:10px 10px;cursor:pointer}
  .sel:focus,.num:focus{outline:none;border-color:var(--teal)}
  .num{width:78px;text-align:center}
  .minichk{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--mut);cursor:pointer}
  .minichk input{accent-color:var(--teal);width:14px;height:14px;cursor:pointer}
  .src{display:flex;gap:8px;flex:1;min-width:240px}
  .src input{flex:1;background:#0a1322;border:1px solid var(--line2);border-radius:10px;
             padding:10px 13px;color:var(--txt);font-family:inherit;font-size:12px;direction:ltr;text-align:left}
  .src input:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px rgba(46,196,182,.10)}

  .syncbar{display:flex;align-items:center;gap:18px;margin-top:11px;font-size:11px;
           color:var(--mut);flex-wrap:wrap}
  .syncbar .auto{display:flex;align-items:center;gap:7px;cursor:pointer;user-select:none}
  .syncbar input[type=checkbox]{accent-color:var(--teal);width:14px;height:14px;cursor:pointer}
  #syncInfo b{color:var(--txt);font-weight:700}
  #syncInfo a{color:var(--teal)}

  /* ---------- grid ---------- */
  .grid{display:grid;grid-template-columns:1.25fr 1fr;gap:16px;align-items:start}
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
  .card h2{font-size:13.5px;margin:0;padding:14px 16px;border-bottom:1px solid var(--line);
           display:flex;align-items:center;gap:9px}
  .card h2 .count{margin-inline-start:auto;font-size:10.5px;color:var(--mut);font-weight:500}
  .card h2 svg{width:16px;height:16px;color:var(--teal)}

  /* servers */
  .filters{display:flex;gap:8px;padding:11px 14px;border-bottom:1px solid var(--line);flex-wrap:wrap}
  .filters input{flex:1;min-width:150px;background:#0a1322;border:1px solid var(--line2);border-radius:9px;
                 padding:8px 12px;color:var(--txt);font-family:inherit;font-size:12px}
  .filters input:focus{outline:none;border-color:var(--teal)}
  .chip{padding:6px 11px;border-radius:99px;border:1px solid var(--line2);background:transparent;
        color:var(--mut);font-size:10.5px;cursor:pointer;font-family:inherit;font-weight:700}
  .chip.active{background:rgba(46,196,182,.13);border-color:rgba(46,196,182,.45);color:var(--teal)}
  .table{max-height:520px;overflow:auto}
  table{width:100%;border-collapse:collapse;font-size:11.5px}
  thead th{position:sticky;top:0;background:#0c1524;color:var(--mut);font-size:10.5px;font-weight:700;
           text-align:right;padding:9px 13px;border-bottom:1px solid var(--line);z-index:2;white-space:nowrap}
  tbody td{padding:9px 13px;border-bottom:1px solid rgba(29,43,64,.6);vertical-align:middle}
  tbody tr:hover{background:rgba(46,196,182,.045)}
  .name{display:flex;align-items:center;gap:7px;font-weight:600}
  .flag{font-size:14px}
  .proto{display:inline-block;padding:2px 8px;border-radius:6px;font-family:"DejaVu Sans Mono",monospace;
         font-size:9.5px;letter-spacing:.3px;border:1px solid;direction:ltr}
  .p-ss{color:#f5a623;border-color:#5a4318;background:rgba(245,166,35,.08)}
  .p-vless{color:#5b8cff;border-color:#2c4270;background:rgba(91,140,255,.09)}
  .p-vmess{color:#3ddc97;border-color:#215c43;background:rgba(61,220,151,.08)}
  .p-trojan{color:#c084fc;border-color:#4a3266;background:rgba(192,132,252,.08)}
  .p-other{color:#8fa3bd;border-color:#2b3b52;background:rgba(143,163,189,.06)}
  .addr{font-family:"DejaVu Sans Mono",monospace;font-size:10px;color:var(--mut);direction:ltr;text-align:left}
  .copy{background:transparent;border:1px solid var(--line2);color:var(--mut);border-radius:7px;
        padding:4px 8px;font-size:10px;cursor:pointer;font-family:inherit}
  .copy:hover{color:var(--teal);border-color:var(--teal)}
  .empty{padding:44px 20px;text-align:center;color:var(--mut);font-size:12.5px}
  .empty b{display:block;color:var(--txt);margin-bottom:6px;font-size:13.5px}

  /* console */
  .console{background:#060b13;border-top:1px solid var(--line);height:520px;overflow:auto;
           padding:12px 14px;font-family:"DejaVu Sans Mono",monospace;font-size:10.5px;
           line-height:1.75;direction:ltr;text-align:left}
  .console .ln{white-space:pre-wrap;word-break:break-word;color:#9db1c9}
  .console .ln.err{color:#ff9aa8}
  .console .ln.ok{color:#5ee6a8}
  .console .ln.stage{color:#2ec4b6;font-weight:700}
  .console .ln.msg{color:#e8eef7}
  .progress{height:3px;background:#101a2b;overflow:hidden}
  .progress i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--teal),var(--blue));
              transition:width .5s}

  /* downloads */
  .files{display:flex;gap:9px;flex-wrap:wrap;margin-top:16px}
  .file{display:flex;align-items:center;gap:9px;padding:10px 13px;border:1px solid var(--line);
        border-radius:10px;background:var(--card);font-size:11.5px;color:var(--txt);transition:.15s}
  .file:hover{border-color:var(--teal);background:#121f33}
  .file.off{opacity:.38;pointer-events:none;filter:grayscale(.4)}
  .file small{color:var(--mut);font-size:9.5px;direction:ltr}
  .file svg{width:15px;height:15px;color:var(--teal)}

  /* toast */
  #toast{position:fixed;bottom:22px;right:50%;transform:translateX(50%) translateY(120px);
         background:#12233a;border:1px solid var(--line2);color:var(--txt);padding:11px 20px;
         border-radius:11px;font-size:12px;box-shadow:0 12px 40px rgba(0,0,0,.55);
         opacity:0;transition:.25s;z-index:99;pointer-events:none}
  #toast.show{transform:translateX(50%) translateY(0);opacity:1}

  .footer{margin-top:22px;text-align:center;font-size:10.5px;color:var(--dim)}
  .footer code{color:var(--mut);direction:ltr;font-family:"DejaVu Sans Mono",monospace}

  @media (max-width:960px){
    .stats{grid-template-columns:repeat(2,1fr)}
    .grid{grid-template-columns:1fr}
  }
</style>
</head>
<body>
<div class="wrap">

  <div class="top">
    <div class="logo">
      <svg viewBox="0 0 24 24" fill="none"><path d="M12 3l7 2.4v5.4c0 4.6-3 7.8-7 9.2-4-1.4-7-4.6-7-9.2V5.4z" stroke="#2ec4b6" stroke-width="1.7"/><path d="M9.2 12l2 2 3.6-3.8" stroke="#5b8cff" stroke-width="1.7"/></svg>
    </div>
    <div class="brand">
      <h1>VPN Working List</h1>
      <p>لوحة تحكم محلية — فحص وتجميع السيرفرات العاملة</p>
    </div>
    <div class="spacer"></div>
    <span class="pill" id="statusPill"><span class="dot" id="statusDot"></span><span id="statusText">غير معروف</span></span>
    <span class="port" id="portText"></span>
  </div>

  <div class="stats">
    <div class="stat teal"><div class="k">السيرفرات في القائمة</div><div class="v" id="stTotal">—</div><div class="s" id="stTotalSub">vpn-servers.txt</div></div>
    <div class="stat blue"><div class="k">مستقرة (3/3)</div><div class="v" id="stStable">—</div><div class="s">نجحت في كل الجولات</div></div>
    <div class="stat amber"><div class="k">كل العاملة</div><div class="v" id="stAll">—</div><div class="s" id="stAllSub">مقبولة وما فوق</div></div>
    <div class="stat white"><div class="k">آخر تحديث</div><div class="v" id="stUpdated" dir="ltr" style="text-align:right">—</div><div class="s" id="stUpdatedSub">—</div></div>
  </div>

  <div class="panel">
    <div class="actions">
      <button class="btn primary" id="btnFull">
        <svg viewBox="0 0 24 24" fill="none"><path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>
        تحديث كامل
      </button>
      <button class="btn blue" id="btnQuick">
        <svg viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14h6l-1 8 9-12h-6z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>
        فحص سريع
      </button>
      <button class="btn" id="btnRussia" title="بحث جديد في المصادر الروسية + دمج المخزّن">
        <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.5"/><path d="M3.5 12h17M12 3.5c2.4 2.4 3.6 5.3 3.6 8.5s-1.2 6.1-3.6 8.5c-2.4-2.4-3.6-5.3-3.6-8.5S9.6 5.9 12 3.5z" stroke="currentColor" stroke-width="1.3"/></svg>
        تحديث روسي
      </button>
      <select id="carrierSel" class="sel" title="ملف المشغّل الروسي">
        <option value="auto">مشغّل: تلقائي</option>
        <option value="mts">MTS</option>
        <option value="megafon">Мегафон</option>
        <option value="beeline">Билайн</option>
        <option value="tele2">Tele2</option>
      </select>
      <label class="minichk" title="كشف الخنق الصامت (TSPU)"><input type="checkbox" id="throttleChk" checked> كشف الخنق</label>
      <label class="minichk" title="مصادر إضافية ضخمة (روابط أكثر، لكن البحث أبطأ)"><input type="checkbox" id="deepChk"> مصادر عميقة</label>
      <select id="dedupeSel" class="sel" title="إزالة التكرار قبل الفحص">
        <option value="smart">تكرار: ذكي</option>
        <option value="server">تكرار: حسب الخادم</option>
        <option value="text">تكرار: نصي فقط</option>
      </select>
      <label class="minichk" title="أقصى عدد روابط للفحص (0 = الكل)">حد
        <input id="rusLimit" class="num" type="number" min="0" step="50" value="0">
      </label>
      <button class="btn" id="btnResume">
        <svg viewBox="0 0 24 24" fill="none"><path d="M5 5v14l9-7z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M18 5v14" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
        إعادة فحص المحفوظ
      </button>
      <button class="btn" id="btnSync">
        <svg viewBox="0 0 24 24" fill="none"><path d="M12 3a9 9 0 0 0-2.8 17.5c.4.1.6-.2.6-.4v-1.6c-2.3.5-2.8-1-2.8-1-.4-1-.9-1.2-.9-1.2-.8-.5.1-.5.1-.5.8.1 1.2.8 1.2.8.7 1.2 1.9.9 2.4.7.1-.5.3-.9.6-1.1-1.9-.2-3.8-.9-3.8-4 0-.9.3-1.6.8-2.2-.1-.2-.4-1 .1-2.1 0 0 .7-.2 2.2.8a7.5 7.5 0 0 1 4 0c1.5-1 2.2-.8 2.2-.8.5 1.1.2 1.9.1 2.1.5.6.8 1.3.8 2.2 0 3.1-1.9 3.8-3.8 4 .3.3.6.8.6 1.5v2.3c0 .2.2.5.6.4A9 9 0 0 0 12 3z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>
        نشر إلى GitHub
      </button>
      <button class="btn danger" id="btnCancel" disabled>
        <svg viewBox="0 0 24 24" fill="none"><rect x="6" y="6" width="12" height="12" rx="2" stroke="currentColor" stroke-width="1.8"/></svg>
        إيقاف
      </button>
      <div class="src">
        <input id="srcInput" placeholder="رابط اشتراك مخصص (اختياري)" spellcheck="false">
        <button class="btn ghost" id="btnSource">تشغيل بالمصدر</button>
      </div>
    </div>
    <div class="syncbar">
      <label class="auto"><input type="checkbox" id="autoSync" checked> نشر تلقائي بعد كل تحديث ناجح</label>
      <span id="syncInfo">آخر نشر: —</span>
    </div>
    <div class="progress"><i id="progBar"></i></div>
  </div>

  <div class="grid" style="margin-top:16px">
    <div class="card">
      <h2>
        <svg viewBox="0 0 24 24" fill="none"><path d="M4 7h16M4 12h16M4 17h10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
        السيرفرات العاملة
        <span class="count" id="listCount"></span>
      </h2>
      <div class="filters">
        <input id="search" placeholder="ابحث بالاسم أو الدولة أو العنوان…">
        <button class="chip active" data-proto="all">الكل</button>
        <button class="chip" data-proto="ss">ss</button>
        <button class="chip" data-proto="vless">vless</button>
        <button class="chip" data-proto="vmess">vmess</button>
        <button class="chip" data-proto="trojan">trojan</button>
        <button class="chip" id="btnCopyAll" title="نسخ كل السيرفرات">نسخ الكل</button>
      </div>
      <div class="table" id="tableBox">
        <table>
          <thead><tr><th>الاسم</th><th>النوع</th><th>العنوان</th><th></th></tr></thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2>
        <svg viewBox="0 0 24 24" fill="none"><path d="M4 6h16v12H4z" stroke="currentColor" stroke-width="1.6"/><path d="M7 10l3 2-3 2M12 15h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        سجل التشغيل
        <span class="count" id="logCount"></span>
      </h2>
      <div class="console" id="console"></div>
    </div>
  </div>

  <div class="files">
    <a class="file" href="/download/servers" download><svg viewBox="0 0 24 24" fill="none"><path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg> vpn-servers.txt <small>القائمة النهائية</small></a>
    <a class="file" href="/download/stable" download><svg viewBox="0 0 24 24" fill="none"><path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg> working_stable_unique <small>المستقرة</small></a>
    <a class="file" href="/download/by_country" download><svg viewBox="0 0 24 24" fill="none"><path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg> working_by_country <small>حسب الدولة</small></a>
    <a class="file" href="/download/clash" download><svg viewBox="0 0 24 24" fill="none"><path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg> clash.yaml <small>Clash</small></a>
    <a class="file" href="/download/clash_simple" download><svg viewBox="0 0 24 24" fill="none"><path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg> clash_simple.yaml <small>Clash مبسّط</small></a>
    <a class="file" href="/download/base64" download><svg viewBox="0 0 24 24" fill="none"><path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg> base64 <small>للاشتراك</small></a>
  </div>

  <div class="footer">
    تطبيق محلي بالكامل — لا يتصل بأي خادم خارجي. يعمل على <code>127.0.0.1</code> فقط.
    <br>الإصدار __VERSION__ · لتشغيله: <code>python3 ~/.local/share/mofilter/vpn-web-app.py</code>
  </div>
</div>

<div id="toast"></div>

<script>
(function(){
  "use strict";
  var state = {servers: [], visible: [], proto: "all", q: "", running: false, lastLog: null};

  function $(id){ return document.getElementById(id); }
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }

  function toast(msg){
    var t = $("toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(t._h); t._h = setTimeout(function(){ t.classList.remove("show"); }, 2200);
  }

  function api(path, opts){
    return fetch(path, opts || {}).then(function(r){
      if(!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function statusUI(s){
    var dot = $("statusDot"), txt = $("statusText");
    dot.className = "dot";
    if(s.running){ dot.className = "dot run"; txt.textContent = "قيد التشغيل" + (s.stage && s.stage !== "done" ? " · " + s.stage : ""); }
    else if(s.exit_code === 0){ dot.className = "dot on"; txt.textContent = "جاهز"; }
    else if(s.exit_code !== null && s.exit_code !== undefined){ dot.className = "dot"; txt.textContent = "متوقف"; }
    else { dot.className = "dot"; txt.textContent = "جاهز"; }

    $("btnFull").disabled = s.running;
    $("btnQuick").disabled = s.running;
    $("btnResume").disabled = s.running;
    $("btnRussia").disabled = s.running;
    $("btnSource").disabled = s.running;
    $("btnCancel").disabled = !s.running;
    state.running = s.running;
    var sb = $("btnSync"); if(sb) sb.disabled = s.running || (window.__sync && window.__sync.running);

    var pct = 0;
    if(s.running && s.stage && /^\d\/6$/.test(s.stage)){ pct = parseInt(s.stage) / 6 * 100; }
    if(!s.running && s.exit_code === 0){ pct = 100; }
    $("progBar").style.width = pct + "%";
  }

  function renderServers(){
    var rows = $("rows"), box = $("tableBox");
    var q = state.q.toLowerCase();
    var list = state.servers.filter(function(s){
      if(state.proto !== "all" && s.proto !== state.proto) return false;
      if(!q) return true;
      return (s.name + " " + s.host + " " + s.port + " " + s.proto).toLowerCase().indexOf(q) >= 0;
    });
    state.visible = list;
    $("listCount").textContent = list.length + " / " + state.servers.length;

    if(!list.length){
      box.innerHTML = '<div class="empty"><b>لا توجد سيرفرات بعد</b>شغّل «تحديث كامل» أو «فحص سريع» لبناء القائمة.</div>';
      return;
    }
    var html = list.map(function(s, i){
      var cls = ["ss","vless","vmess","trojan"].indexOf(s.proto) >= 0 ? "p-" + s.proto : "p-other";
      var flag = s.flag || "";
      var addr = (s.host || "") + (s.port ? ":" + s.port : "");
      return '<tr>' +
        '<td><div class="name"><span class="flag">' + esc(flag) + '</span>' + esc(s.name) + '</div></td>' +
        '<td><span class="proto ' + cls + '">' + esc(s.proto) + '</span></td>' +
        '<td class="addr">' + esc(addr) + '</td>' +
        '<td><button class="copy" data-i="' + i + '">نسخ</button></td>' +
        '</tr>';
    }).join("");
    rows.innerHTML = html;
  }

  function loadServers(){
    return api("/api/servers").then(function(d){
      state.servers = d.servers || [];
      renderServers();
    }).catch(function(){});
  }

  function loadState(){
    return api("/api/state").then(function(d){
      statusUI(d.run || {running:false});
      $("stTotal").textContent = d.stats.total;
      $("stStable").textContent = (d.stats.stable === null ? "—" : d.stats.stable);
      $("stAll").textContent = (d.stats.working === null ? "—" : d.stats.working);
      $("stUpdated").textContent = d.stats.updated || "—";
      $("stUpdatedSub").textContent = d.stats.updated_size ? d.stats.updated_size : "لا يوجد ملف";
      $("portText").textContent = "127.0.0.1:" + d.port;
      window.__gh = !!d.github;
      if(d.sync){ window.__sync = d.sync; renderSync(d.sync, d.repo_url); }
      if(d.settings){
        var cb = $("autoSync"); if(document.activeElement !== cb) cb.checked = !!d.settings.auto_sync;
        if(d.settings.carrier) $("carrierSel").value = d.settings.carrier;
        if(typeof d.settings.throttle === "boolean") $("throttleChk").checked = d.settings.throttle;
        if(typeof d.settings.deep === "boolean") $("deepChk").checked = d.settings.deep;
        if(d.settings.dedupe) $("dedupeSel").value = d.settings.dedupe;
        if(typeof d.settings.rus_limit === "number" && document.activeElement !== $("rusLimit")) $("rusLimit").value = d.settings.rus_limit;
      }
      if(d.files){
        Array.prototype.forEach.call(document.querySelectorAll("a.file"), function(a){
          var key = (a.getAttribute("href") || "").split("/").pop();
          var ok = d.files[key] !== false;
          a.classList.toggle("off", !ok);
          a.title = ok ? "" : "غير متوفر بعد — شغّل تحديثًا كاملًا";
        });
      }
      if(d.stats.total !== state.servers.length){ loadServers(); }
    }).catch(function(){});
  }

  function renderSync(s, url){
    var el = $("syncInfo"); if(!el) return;
    var html;
    if(s.running){
      html = '<span style="color:var(--amber)">جارٍ النشر إلى GitHub…</span>';
    } else if(s.ok === true){
      html = '✔ آخر نشر: <b>' + esc(s.time || "") + '</b>';
      if(url) html += ' · <a href="' + esc(url) + '" target="_blank" rel="noopener">فتح على GitHub</a>';
    } else if(s.ok === false){
      html = '<span style="color:var(--red)">✘ فشل النشر: ' + esc(s.message || "") + '</span>';
    } else {
      html = 'آخر نشر: —';
    }
    el.innerHTML = html;
    var sb = $("btnSync");
    if(sb){
      var ghOff = window.__gh === false;
      // لا نستخدم disabled هنا: الزر المعطّل لا يُطلق حدث النقر، فلا يظهر السبب.
      sb.disabled = state.running || s.running;
      sb.classList.toggle("gh-off", ghOff);
      sb.setAttribute("aria-disabled", ghOff ? "true" : "false");
      sb.title = ghOff ? "GitHub غير مضبوط — انسخ github.json إلى ~/.config/vpn-list/" : "";
    }
    // أرفق الإشعار مرة واحدة فقط، واعمل حتى لو تغيّرت حالة GitHub لاحقًا
    if(sb && !sb._ghNotice){
      sb._ghNotice = true;
      sb.addEventListener("click", function(ev){
        if(window.__gh === false){
          ev.preventDefault();
          ev.stopImmediatePropagation();
          toast("GitHub غير مضبوط: انسخ github.json إلى ~/.config/vpn-list/ ثم أعد التشغيل");
        }
      }, true);
    }
  }

  function renderLog(text){
    if(text === state.lastLog) return;
    state.lastLog = text;
    var box = $("console");
    if(!text){
      box.innerHTML = '<div class="empty" style="padding:60px 16px"><b>لا يوجد سجل بعد</b>سيظهر هنا تقدّم الفحص لحظة بلحظة عند التشغيل.</div>';
      return;
    }
    var atBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 40;
    var lines = (text || "").split("\n");
    box.innerHTML = lines.map(function(l){
      var cls = "ln";
      if(/^\[.*\]/.test(l)) cls += " msg";
      if(/==\s*\d\/6/.test(l)) cls += " stage";
      if(/✘|error|تعذّر|فشل|Failed|Traceback/i.test(l)) cls += " err";
      if(/✔|نجاح|تمّ|حُفظ/.test(l)) cls += " ok";
      return '<div class="' + cls + '">' + esc(l) + '</div>';
    }).join("");
    if(atBottom) box.scrollTop = box.scrollHeight;
  }

  function loadLog(){
    return api("/api/log").then(function(d){ renderLog(d.log || ""); }).catch(function(){});
  }

  function startRun(mode){
    var src = $("srcInput").value.trim();
    // تحذير: الحد=0 يعني فحص كل الروابط — قد يستغرق ساعات
    if(mode === "russia"){
      var limNow = parseInt($("rusLimit").value, 10);
      if(isNaN(limNow) || limNow === 0){
        if(!confirm("الحد = 0 يعني فحص كل الروابط (قد يستغرق ساعات).\nهل تريد المتابعة؟")){
          return;
        }
      }
    }
    if(mode === "source" && !src){ toast("أدخل رابط اشتراك أولًا"); return; }
    var body = {mode: mode};
    if(src) body.source = src;
    if(mode === "quick" || mode === "resume") body.limit = 150;
    if(mode === "russia"){
      var lim = parseInt($("rusLimit").value, 10);
      body.limit = isNaN(lim) ? 0 : Math.max(0, lim);
      body.carrier = $("carrierSel").value;
      body.throttle = $("throttleChk").checked;
    }
    if(mode === "russia" || mode === "resume"){
      body.dedupe = $("dedupeSel").value;
      body.carrier = $("carrierSel").value;
      if(mode === "resume"){
        var rl = parseInt($("rusLimit").value, 10);
        body.limit = (isNaN(rl) || rl <= 0) ? 150 : rl;
      }
    }
    api("/api/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    }).then(function(d){
      if(d.ok){ toast("بدأ التشغيل…"); state.lastLog = ""; }
      else { toast(d.error || "تعذّر البدء"); }
      loadState(); loadLog();
    }).catch(function(e){ toast("خطأ: " + e.message); });
  }

  document.addEventListener("click", function(ev){
    var t = ev.target;
    if(t && t.classList && t.classList.contains("copy")){
      var rows = Array.prototype.slice.call(document.querySelectorAll("#rows tr"));
      var idx = rows.indexOf(t.closest("tr"));
      var item = (state.visible || [])[idx];
      if(!item) return;
      navigator.clipboard.writeText(item.raw).then(function(){ toast("تم النسخ"); })
        .catch(function(){ toast("تعذّر النسخ"); });
    }
  });

  $("search").addEventListener("input", function(e){ state.q = e.target.value; renderServers(); });
  Array.prototype.forEach.call(document.querySelectorAll(".chip[data-proto]"), function(c){
    c.addEventListener("click", function(){
      Array.prototype.forEach.call(document.querySelectorAll(".chip[data-proto]"), function(x){ x.classList.remove("active"); });
      c.classList.add("active");
      state.proto = c.getAttribute("data-proto");
      renderServers();
    });
  });
  $("btnCopyAll").addEventListener("click", function(){
    var text = (state.visible || []).map(function(s){ return s.raw; }).join("\n");
    if(!text){ toast("لا توجد سيرفرات"); return; }
    navigator.clipboard.writeText(text).then(function(){ toast("تم نسخ " + (state.visible||[]).length + " سيرفر"); })
      .catch(function(){ toast("تعذّر النسخ"); });
  });
  $("btnFull").addEventListener("click", function(){ startRun("full"); });
  $("btnQuick").addEventListener("click", function(){ startRun("quick"); });
  $("btnResume").addEventListener("click", function(){ startRun("resume"); });
  $("btnRussia").addEventListener("click", function(){ startRun("russia"); });
  $("rusLimit").addEventListener("change", function(e){
    api("/api/settings", {method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({rus_limit: parseInt(e.target.value, 10) || 0})});
  });
  $("btnSource").addEventListener("click", function(){ startRun("source"); });
  $("btnSync").addEventListener("click", function(){
    if(window.__gh === false){
      toast("GitHub غير مضبوط: انسخ github.json إلى ~/.config/vpn-list/ ثم أعد التشغيل");
      return;
    }
    api("/api/sync", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({force:true})})
      .then(function(d){ toast(d.ok ? "بدأ النشر إلى GitHub…" : (d.error || "تعذّر النشر")); })
      .catch(function(e){ toast("خطأ: " + e.message); });
  });
  $("autoSync").addEventListener("change", function(e){
    api("/api/settings", {method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({auto_sync: e.target.checked})})
      .then(function(){ toast(e.target.checked ? "النشر التلقائي مفعّل" : "النشر التلقائي متوقف"); });
  });
  $("deepChk").addEventListener("change", function(e){
    api("/api/settings", {method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({deep: e.target.checked})})
      .then(function(){ toast(e.target.checked ? "المصادر العميقة مفعّلة — البحث سيكون أبطأ" : "المصادر العميقة متوقفة"); });
  });
  $("btnCancel").addEventListener("click", function(){
    api("/api/cancel", {method:"POST"}).then(function(d){ toast(d.ok ? "تم طلب الإيقاف" : (d.error||"فشل")); });
  });

  loadState(); loadServers(); loadLog();
  setInterval(loadState, 2000);
  setInterval(loadLog, 1200);
  setInterval(function(){ if(state.running) loadServers(); }, 6000);
})();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------
#  خادم HTTP
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "VPNWebApp/" + APP_VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # امنع ضجيج السجل في الطرفية
        pass

    # ---------------------------------------------------------------
    def _local_host(self):
        """ارفض أي Host غريب (حماية من DNS rebinding)."""
        host = (self.headers.get("Host") or "").strip().lower()
        if not host:
            return True
        if host.startswith("["):
            end = host.find("]")
            name = host[1:end] if end > 0 else host
        elif host.count(":") == 1:
            name = host.rsplit(":", 1)[0]
        else:
            name = host
        return name in ("127.0.0.1", "localhost", "::1")

    def _local_origin(self):
        """ارفض POST قادمًا من صفحة خارجية (حماية CSRF)."""
        site = (self.headers.get("Sec-Fetch-Site") or "").strip().lower()
        if site and site not in ("same-origin", "none"):
            return False
        origin = (self.headers.get("Origin") or "").strip()
        if not origin:
            return True
        parsed = urlparse(origin)
        return (parsed.scheme == "http"
                and parsed.hostname in ("127.0.0.1", "localhost", "::1")
                and parsed.port == self.server.server_port)

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        headers = {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        }
        if ctype.startswith("text/html"):
            headers.update({
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": (
                    "default-src 'self'; img-src 'self' data:; "
                    "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
                ),
            })
        if extra:
            headers.update(extra)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _error(self, message, code=400):
        self._json({"ok": False, "error": message}, code)

    # ---------------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._local_host():
            self._error("طلب غير محلي مرفوض", 403)
            return
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            html = HTML.replace("__VERSION__", APP_VERSION).replace("__ICON__", ICON_B64)
            self._send(200, html, "text/html; charset=utf-8")
            return

        if path == "/api/state":
            self._json(self.state_payload())
            return

        if path == "/api/servers":
            self._json({"servers": load_servers()})
            return

        if path == "/api/log":
            text = "\n".join(list(RUNNER.lines)[-600:])
            if not text:
                text = self._tail(APP_LOG, 120)
            self._json({"log": text})
            return

        if path.startswith("/download/"):
            key = path[len("/download/"):]
            spec = DOWNLOADS.get(key)
            target = spec if spec and os.path.isabs(spec) else (resolve_result(spec) if spec else None)
            if not target or not os.path.isfile(target):
                self._error("الملف غير موجود", 404)
                return
            try:
                with open(target, "rb") as fh:
                    data = fh.read()
            except OSError as exc:
                self._error(str(exc), 500)
                return
            name = os.path.basename(target)
            self._send(200, data, "application/octet-stream",
                       {"Content-Disposition": 'attachment; filename="%s"' % name})
            return

        self._error("غير موجود", 404)

    def do_POST(self):
        if not self._local_host() or not self._local_origin():
            self._error("طلب غير محلي مرفوض", 403)
            return
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > 1_000_000:
            self._error("الطلب كبير جدًا", 413)
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            payload = {}

        if parsed.path == "/api/run":
            mode = str(payload.get("mode") or "full")
            if mode not in ("full", "quick", "resume", "source", "russia"):
                mode = "full"
            source = str(payload.get("source") or "").strip()[:4096]
            try:
                limit = max(0, min(100000, int(payload.get("limit") or 0)))
            except Exception:
                limit = 0
            carrier = str(payload.get("carrier") or "auto")
            if carrier not in ("auto", "mts", "megafon", "beeline", "tele2"):
                carrier = "auto"
            throttle = payload.get("throttle")
            throttle = None if throttle is None else bool(throttle)
            dedupe = str(payload.get("dedupe") or "smart")
            if dedupe not in ("text", "smart", "server"):
                dedupe = "smart"
            ok, err = RUNNER.start(mode, source, limit, carrier, throttle, dedupe)
            if ok:
                self._json({"ok": True})
            else:
                self._json({"ok": False, "error": err})
            return

        if parsed.path == "/api/cancel":
            ok, err = RUNNER.cancel()
            self._json({"ok": ok, "error": err})
            return

        if parsed.path == "/api/sync":
            force = bool(payload.get("force"))
            ok, err = start_sync(force=force)
            self._json({"ok": ok, "error": err})
            return

        if parsed.path == "/api/settings":
            data = load_settings()
            if "auto_sync" in payload:
                data["auto_sync"] = bool(payload.get("auto_sync"))
            if "rus_limit" in payload:
                try:
                    data["rus_limit"] = max(0, min(100000, int(payload.get("rus_limit") or 0)))
                except (TypeError, ValueError):
                    data["rus_limit"] = 0
            if "carrier" in payload and str(payload.get("carrier")) in ("auto", "mts", "megafon", "beeline", "tele2"):
                data["carrier"] = str(payload.get("carrier"))
            if "throttle" in payload:
                data["throttle"] = bool(payload.get("throttle"))
            if "dedupe" in payload and str(payload.get("dedupe")) in ("text", "smart", "server"):
                data["dedupe"] = str(payload.get("dedupe"))
            if "deep" in payload:
                data["deep"] = bool(payload.get("deep"))
            save_settings(data)
            self._json({"ok": True, "settings": data})
            return

        self._error("غير موجود", 404)

    # ---------------------------------------------------------------
    def _tail(self, path, n=120):
        """آخر n سطرًا من ملف كبير دون قراءته كاملًا."""
        try:
            with open(path, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                block = min(size, 256 * 1024)
                fh.seek(size - block)
                data = fh.read().decode("utf-8", "ignore")
            return "\n".join(data.splitlines()[-n:])
        except OSError:
            return ""

    def state_payload(self):
        current = current_servers_file()
        total = count_lines(current)
        stable = count_lines(resolve_result("working_stable_unique.txt"))
        working = count_lines(resolve_result("working_unique.txt"))
        if total and not stable:
            stable = None
        if total and not working:
            working = None
        return {
            "ok": True,
            "app": {"name": "VPN Working List", "version": APP_VERSION},
            "port": self.server.server_port,
            "run": RUNNER.snapshot(),
            "stats": {
                "total": total,
                "stable": stable,
                "working": working,
                "updated": mtime_str(current),
                "updated_size": human_size(current),
            },
            "paths": {
                "servers": current,
                "results": RESULTS_DIR,
                "log": APP_LOG,
                "skill": SKILL_DIR,
            },
            "skill_ok": os.path.isfile(RUN_PY),
            "sync": _sync_payload(),
            "repo_url": repo_url(),
            "github": bool(github_config().get("token")),
            "settings": load_settings(),
            "files": {
                "servers": os.path.isfile(SERVERS_FILE),
                "stable": os.path.isfile(resolve_result("working_stable_unique.txt")),
                "by_country": os.path.isfile(resolve_result("working_by_country.txt")),
                "clash": os.path.isfile(resolve_result("clash.yaml")),
                "clash_simple": os.path.isfile(resolve_result("clash_simple.yaml")),
                "base64": os.path.isfile(resolve_result("working_stable_base64.txt")),
            },
        }


# --------------------------------------------------------------------------
#  التشغيل
# --------------------------------------------------------------------------
def free_port(start):
    if start <= 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]
    port = start
    while port < start + 200:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    raise SystemExit("لا يوجد منفذ حر قرب %d" % start)


def main():
    ap = argparse.ArgumentParser(description="VPN Working List — تطبيق ويب محلي")
    ap.add_argument("--port", type=int, default=8080, help="المنفذ (افتراضي 8080)")
    ap.add_argument("--no-open", action="store_true", help="لا تفتح المتصفح تلقائيًا")
    ap.add_argument("--version", action="version", version="vpn-web-app " + APP_VERSION)
    args = ap.parse_args()

    if not os.path.isfile(RUN_PY):
        print("تنبيه: مهارة vpn-list غير مثبتة في %s" % SKILL_DIR)
        print("ستعمل الواجهة للعرض فقط، ولن يعمل زر التحديث.")

    port = free_port(args.port)
    os.makedirs(DATA_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    url = "http://127.0.0.1:%d/" % port

    print("VPN Working List — تطبيق الويب")
    print("  الرابط : %s" % url)
    print("  المنفذ : %d" % port)
    print("  المهارة: %s" % ("موجودة" if os.path.isfile(RUN_PY) else "غير مثبتة"))
    print("  إيقاف : Ctrl+C")
    sys.stdout.flush()

    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    def _do_stop():
        RUNNER.cancel()
        try:
            server.shutdown()
        except Exception:
            pass

    def _shutdown(_sig, _frm):
        print("\nجارٍ الإيقاف…", flush=True)
        # لا تستدعِ shutdown() من خيط serve_forever نفسه — وإلا حدث جمود.
        threading.Thread(target=_do_stop, daemon=True).start()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        server.serve_forever(poll_interval=0.4)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        try:
            server.server_close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
