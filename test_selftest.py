#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات وحدة بسيطة لمفلتر السيرفرات — بلا pytest، بايثون القياسي فقط.
التشغيل:  python3 test_selftest.py
"""
import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "vpn-web-app.py")

# نستورد التطبيق كوحدة رغم أن اسمه يحتوي شرطة
spec = importlib.util.spec_from_file_location("vpn_web_app", APP)
app = importlib.util.module_from_spec(spec)
sys.modules["vpn_web_app"] = app
spec.loader.exec_module(app)


def vmess(host="1.2.3.4", port=443, ps="Test", sni="yandex.ru"):
    payload = json.dumps({
        "v": "2", "ps": ps, "add": host, "port": str(port),
        "id": "uuid-here", "sni": sni, "net": "tcp", "tls": "tls",
    })
    return "vmess://" + base64.b64encode(payload.encode()).decode()


def ss_legacy(host="5.6.7.8", port=8388, ps="OldSS"):
    """ss://base64(method:password@host:port)#name — الصيغة القديمة."""
    blob = base64.b64encode(("aes-256-gcm:pass@%s:%s" % (host, port)).encode()).decode()
    return "ss://%s#%s" % (blob, ps)


class TestParseLink(unittest.TestCase):
    def test_vless_basic(self):
        raw = "vless://uuid@1.2.3.4:443?security=reality&sni=yandex.ru#MyServer"
        item = app.parse_link(raw)
        self.assertIsNotNone(item)
        self.assertEqual(item["proto"], "vless")
        self.assertEqual(item["host"], "1.2.3.4")
        self.assertEqual(item["port"], "443")
        self.assertEqual(item["name"], "MyServer")

    def test_ss_with_flag(self):
        raw = "ss://YWVzLTI1Ni1nY206cGFzcw==@5.6.7.8:8388#🇷🇺 Russia-1"
        item = app.parse_link(raw)
        self.assertIsNotNone(item)
        self.assertEqual(item["proto"], "ss")
        self.assertEqual(item["host"], "5.6.7.8")
        self.assertIn("Russia-1", item["name"])
        # العلم يجب أن يُستخرج ويُزال من الاسم
        self.assertEqual(item["flag"], "🇷🇺")

    def test_vmess(self):
        raw = vmess()
        item = app.parse_link(raw)
        self.assertIsNotNone(item)
        self.assertEqual(item["proto"], "vmess")
        self.assertEqual(item["host"], "1.2.3.4")
        self.assertEqual(item["port"], "443")

    def test_empty_and_garbage(self):
        self.assertIsNone(app.parse_link(""))
        self.assertIsNone(app.parse_link("   "))
        self.assertIsNone(app.parse_link("no-scheme-here"))

    def test_url_decoded_name(self):
        raw = "vless://u@1.1.1.1:443#%D8%B3%D9%8A%D8%B1%D9%81%D8%B1"
        item = app.parse_link(raw)
        self.assertEqual(item["name"], "سيرفر")

    def test_ss_legacy_base64(self):
        raw = ss_legacy()
        item = app.parse_link(raw)
        self.assertIsNotNone(item)
        self.assertEqual(item["proto"], "ss")
        self.assertEqual(item["host"], "5.6.7.8")
        self.assertEqual(item["port"], "8388")
        self.assertEqual(item["name"], "OldSS")

    def test_ss_legacy_with_flag(self):
        raw = ss_legacy(ps="🇷🇺 Russia-2")
        item = app.parse_link(raw)
        self.assertEqual(item["flag"], "🇷🇺")
        self.assertIn("Russia-2", item["name"])

    def test_trojan(self):
        raw = "trojan://secret@9.9.9.9:443?sni=yandex.ru#Trojan%20One"
        item = app.parse_link(raw)
        self.assertEqual(item["proto"], "trojan")
        self.assertEqual(item["host"], "9.9.9.9")
        self.assertEqual(item["port"], "443")
        self.assertEqual(item["name"], "Trojan One")

    def test_tag_of_decodes(self):
        self.assertEqual(app.tag_of("vless://x@1.1.1.1:443#A%20B"), "A B")
        self.assertEqual(app.tag_of("vless://x@1.1.1.1:443"), "")


class TestFlagFor(unittest.TestCase):
    def test_ru(self):
        self.assertEqual(app.flag_for("RU"), "🇷🇺")

    def test_us(self):
        self.assertEqual(app.flag_for("us"), "🇺🇸")

    def test_invalid(self):
        self.assertEqual(app.flag_for(""), "")
        self.assertEqual(app.flag_for("XYZ"), "")
        self.assertEqual(app.flag_for("R1"), "")


class TestReadCount(unittest.TestCase):
    def test_count_lines_missing(self):
        self.assertEqual(app.count_lines("/nonexistent/path/xyz"), 0)

    def test_count_lines_skips_blanks(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
            fh.write("a\n\n  \nb\r\nc\n")
            path = fh.name
        try:
            self.assertEqual(app.count_lines(path), 3)
        finally:
            os.unlink(path)


class TestServerFileFallback(unittest.TestCase):
    def test_falls_back_to_stable_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "vpn-servers.txt")
            stable = os.path.join(tmp, "working_stable_unique.txt")
            with open(stable, "w", encoding="utf-8") as fh:
                fh.write("vless://u@1.1.1.1:443\n")
            with mock.patch.object(app, "SERVERS_FILE", missing), \
                 mock.patch.object(app, "RESULTS_DIR", tmp), \
                 mock.patch.object(app, "DATA_DIR", os.path.join(tmp, "data")), \
                 mock.patch.object(app, "READY_DIR", os.path.join(tmp, "ready")):
                self.assertEqual(app.current_servers_file(), stable)
                self.assertEqual(len(app.load_servers()), 1)


class TestVersion(unittest.TestCase):
    def test_app_and_skill_versions_match(self):
        with open(os.path.join(HERE, "skill", ".version"), encoding="utf-8") as fh:
            skill_version = fh.read().strip()
        self.assertEqual(app.APP_VERSION, skill_version)


class TestCancel(unittest.TestCase):
    def test_cancel_reaps_and_marks_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(app, "APP_LOG", os.path.join(tmp, "app.log")), \
                 mock.patch.object(app, "DATA_DIR", tmp):
                proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
                with app.RUNNER.lock:
                    app.RUNNER.proc = proc
                app.RUNNER._stop_requested = False
                try:
                    ok, err = app.RUNNER.cancel()
                    self.assertTrue(ok, err)
                    self.assertEqual(proc.returncode, -15)
                finally:
                    if proc.poll() is None:
                        proc.kill()
                    with app.RUNNER.lock:
                        app.RUNNER.proc = None


if __name__ == "__main__":
    unittest.main(verbosity=2)
