#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مفلتر السيرفرات — مشغّل سطح المكتب.

يبدأ خادم التطبيق المحلي، ثم يفتحه في نافذة تطبيق مستقلة (Chrome/Chromium app
mode) بلا شريط عنوان ولا قوائم متصفح، ويُغلق الخادم تلقائيًا عند إغلاق النافذة.

    mofilter-desktop              فتح النافذة
    mofilter-desktop --no-window  تشغيل الخادم فقط (تشخيص/اختبار)
    mofilter-desktop --port 9000  منفذ محدد
    mofilter-desktop --version    رقم الإصدار
"""
import argparse
import fcntl
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

VERSION = "1.0.0"
NAME = "مفلتر السيرفرات"

HOME = os.path.expanduser("~")
APP_HOME = os.path.join(HOME, ".local", "share", "mofilter")
DATA_HOME = os.path.join(HOME, ".local", "share", "vpn-list")
PORT_FILE = os.path.join(APP_HOME, "desktop-port")
LOCK_FILE = os.path.join(APP_HOME, "desktop.lock")
LOG_FILE = os.path.join(APP_HOME, "desktop.log")
PROFILE = os.path.join(APP_HOME, "chrome-profile")
WM_CLASS = "MofilterVPN"

DEVNULL = subprocess.DEVNULL


def log(msg):
    try:
        os.makedirs(APP_HOME, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def notify(message):
    """Visible error even when launched from the menu (Terminal=false)."""
    for cmd in (["kdialog", "--error", message], ["zenity", "--error", "--text", message]):
        exe = shutil.which(cmd[0])
        if exe:
            try:
                subprocess.run([exe] + cmd[1:], timeout=30)
                return
            except Exception:
                pass
    sys.stderr.write(message + "\n")


def app_script():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.environ.get("MOFILTER_APP"),
                 os.path.join(APP_HOME, "vpn-web-app.py"),
                 os.path.join(here, "vpn-web-app.py"),
                 os.path.join(os.path.dirname(here), "vpn-web-app.py")):
        if cand and os.path.isfile(cand):
            return cand
    return None


def free_port(preferred):
    for port in range(preferred, preferred + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ready(port, timeout=0.8):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/api/state" % port, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def saved_port():
    try:
        with open(PORT_FILE, encoding="utf-8") as fh:
            return int(fh.read().strip())
    except Exception:
        return 0


def _die_with_parent():
    """Linux: let the server die if the launcher crashes (no orphan process)."""
    try:
        import ctypes
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
    except Exception:
        pass


def start_server(port):
    script = app_script()
    if not script:
        notify("لم يُعثر على vpn-web-app.py — أعد تشغيل حزمة «مفلتر السيرفرات».")
        return None
    os.makedirs(APP_HOME, exist_ok=True)
    out = open(LOG_FILE, "a", encoding="utf-8")
    out.write("\n===== %s =====\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    out.flush()
    proc = subprocess.Popen(
        [sys.executable, "-u", script, "--no-open", "--port", str(port)],
        cwd=APP_HOME, stdout=out, stderr=subprocess.STDOUT,
        start_new_session=True, preexec_fn=_die_with_parent,
    )
    log("server pid %d on port %d" % (proc.pid, port))
    return proc


def wait_until_up(proc, port, timeout=45.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        if ready(port):
            return True
        time.sleep(0.25)
    return False


def chromium_path():
    for exe in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                "brave-browser", "microsoft-edge", "microsoft-edge-stable", "vivaldi"):
        path = shutil.which(exe)
        if path:
            return path
    return None


def prepare_profile():
    """Silence Chrome's translate bubble and crash restore for the app window."""
    default = os.path.join(PROFILE, "Default")
    os.makedirs(default, exist_ok=True)
    pref = os.path.join(default, "Preferences")
    if not os.path.exists(pref):
        data = {
            "translate": {"enabled": False},
            "translate_blocked_languages": ["ar", "en"],
            "profile": {"exit_type": "Normal", "exited_cleanly": True},
        }
        try:
            with open(pref, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        except OSError:
            pass


def open_window(url):
    chrome = chromium_path()
    if chrome:
        os.makedirs(PROFILE, exist_ok=True)
        prepare_profile()
        args = [
            chrome,
            "--app=" + url,
            "--user-data-dir=" + PROFILE,
            "--class=" + WM_CLASS,
            "--start-maximized",
            "--lang=ar",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-mode",
            "--disable-translate",
            "--hide-crash-restore-bubble",
            "--disable-features=Translate,TranslateUI,MediaRouter",
            "--disable-sync",
            "--no-service-autorun",
        ]
        try:
            proc = subprocess.Popen(args, stdout=DEVNULL, stderr=DEVNULL,
                                    start_new_session=True)
            log("window pid %d (%s)" % (proc.pid, chrome))
            return proc, PROFILE
        except OSError as exc:
            log("chrome failed: %s" % exc)
    # Fallback: Firefox (normal window) or the default browser.
    firefox = shutil.which("firefox")
    if firefox:
        try:
            proc = subprocess.Popen([firefox, "--new-window", url],
                                    stdout=DEVNULL, stderr=DEVNULL,
                                    start_new_session=True)
            log("window pid %d (firefox)" % proc.pid)
            return proc, None
        except OSError:
            pass
    try:
        subprocess.Popen(["xdg-open", url], stdout=DEVNULL, stderr=DEVNULL,
                         start_new_session=True)
        log("xdg-open used")
    except OSError as exc:
        log("cannot open browser: %s" % exc)
    return None, None


def window_alive(proc, profile):
    if profile:
        # The wrapper process may detach; the profile is unique, so pgrep is
        # the reliable signal that the app window is still open.
        try:
            rc = subprocess.run(["pgrep", "-f", "user-data-dir=" + profile],
                                stdout=DEVNULL, stderr=DEVNULL, timeout=5).returncode
            return rc == 0
        except Exception:
            pass
    return proc is not None and proc.poll() is None


def stop(proc, profile):
    if profile:
        try:
            subprocess.run(["pkill", "-TERM", "-f", "user-data-dir=" + profile],
                           stdout=DEVNULL, stderr=DEVNULL, timeout=5)
        except Exception:
            pass
    if proc is None:
        return
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def tail_log(lines=12):
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-lines:])
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser(description="%s — تطبيق سطح المكتب" % NAME)
    ap.add_argument("--port", type=int, default=0, help="منفذ الخادم (يُختار تلقائيًا)")
    ap.add_argument("--no-window", action="store_true", help="شغّل الخادم فقط بلا نافذة")
    ap.add_argument("--version", action="version", version="mofilter-desktop " + VERSION)
    args = ap.parse_args()

    os.makedirs(APP_HOME, exist_ok=True)

    # Single instance: a second click just opens another window on the same
    # server instead of starting a rival copy.
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        first = True
    except OSError:
        first = False

    if not first:
        port = saved_port()
        if port and ready(port):
            if args.no_window:
                print("http://127.0.0.1:%d/" % port)
            else:
                open_window("http://127.0.0.1:%d/" % port)
            return 0
        time.sleep(1.5)
        port = saved_port()
        if port and ready(port):
            if not args.no_window:
                open_window("http://127.0.0.1:%d/" % port)
            return 0
        notify("التطبيق يعمل بالفعل لكنه لا يستجيب — أغلق نافذته ثم أعد المحاولة.")
        return 1

    port = args.port or free_port(8080)
    proc = start_server(port)
    if not proc:
        return 1
    if not wait_until_up(proc, port):
        stop(proc, None)
        notify("تعذّر تشغيل الخادم المحلي.\n\n" + tail_log())
        return 1

    url = "http://127.0.0.1:%d/" % port
    try:
        with open(PORT_FILE, "w", encoding="utf-8") as fh:
            fh.write(str(port))
    except OSError:
        pass

    if args.no_window:
        print("READY %s" % url, flush=True)
        stop_now = {"v": False}

        def _term(_signo, _frame):
            stop_now["v"] = True

        signal.signal(signal.SIGTERM, _term)
        signal.signal(signal.SIGINT, _term)
        try:
            while proc.poll() is None and not stop_now["v"]:
                time.sleep(0.5)
        finally:
            stop(proc, None)
        return 0

    window, profile = open_window(url)
    if window is None and profile is None:
        notify("لم يُعثر على متصفح لعرض الواجهة.\nثبّت Chrome أو Firefox ثم أعد المحاولة.")
        stop(proc, None)
        return 1

    stopping = {"now": False}

    def _sig(_signo, _frame):
        stopping["now"] = True

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    try:
        while not stopping["now"]:
            time.sleep(2)
            if proc.poll() is not None:
                notify("توقّف خادم التطبيق.\n\n" + tail_log())
                break
            if window is not None and not window_alive(window, profile):
                break
    finally:
        stop(proc, profile)
        try:
            os.unlink(PORT_FILE)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
