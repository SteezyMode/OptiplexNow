"""Validate URL and first-run login safety without touching the real tailnet."""
import importlib.util
import json
import subprocess
import sys
from unittest import mock
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("browser_login",ROOT/"src"/"tailscale_browser_login.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TailscaleBrowserLoginTests(unittest.TestCase):
    def test_url_is_strictly_official_login_host(self):
        self.assertTrue(mod.valid_login_url("https://login.tailscale.com/a/0123456789"))
        for url in [
            "http://login.tailscale.com/a/123", "https://evil.example/a/123",
            "https://login.tailscale.com.evil.example/a/123",
            "https://login.tailscale.com@evil.example/a/123",
            "https://login.tailscale.com:444/a/123",
            "file:///etc/passwd", "https://login.tailscale.com/admin",
            "https://login.tailscale.com/a/123#frag", "",
            None, "https://login.tailscale.com/a/" + "x"*3000]:
            with self.subTest(url=url):
                self.assertFalse(mod.valid_login_url(url))

    def test_realistic_multiline_json_stream_split_into_chunks(self):
        url = "https://login.tailscale.com/a/0123456789abcdef"
        raw = (json.dumps({"AuthURL": url, "QR": "data:image/png;base64,AAAA",
                           "BackendState": "NeedsLogin"}, indent=2)
               + "\n" + json.dumps({"BackendState": "Running"}, indent=2)
               + "\n")
        stream = mod.JSONMessageStream()
        found = []
        for byte in raw.encode("utf-8"):
            found.extend(stream.feed(bytes([byte])))
        self.assertEqual(found[0]["AuthURL"], url)
        self.assertEqual(found[1]["BackendState"], "Running")
        self.assertEqual(len(found), 2)
        self.assertEqual(stream.pending, "")

    def test_multiple_objects_in_one_chunk_and_error_is_bounded(self):
        stream = mod.JSONMessageStream()
        rows = stream.feed(b'{"AuthURL":"https://login.tailscale.com/a/abc"}\n{"BackendState":"Running"}')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["BackendState"], "Running")
        with self.assertRaises(ValueError):
            mod.JSONMessageStream().feed(b'x' * (mod.MAX_BUFFER + 1))
        with self.assertRaises(ValueError):
            mod.JSONMessageStream().feed(b'<html>authorization failed</html>')

    def test_fake_cli_exercises_browser_then_completion(self):
        url = "https://login.tailscale.com/a/abcdef1234567890"
        first = json.dumps({"AuthURL": url, "QR": "data:image/png;base64,ABCD",
                            "BackendState": "NeedsLogin"}, indent=2)
        last = json.dumps({"BackendState": "Running"}, indent=2)
        output = first + "\n" + last + "\n"
        script = "import sys;sys.stdout.write(" + repr(output) + ");sys.stdout.flush()"
        seen = []
        def fake_popen(args, **kwargs):
            self.assertEqual(args[-2:], ["up", "--json"])
            return subprocess.Popen([sys.executable, "-u", "-c", script], **kwargs)
        with mock.patch.object(mod.shutil, "which", return_value="/usr/local/bin/tailscale"):
            rc = mod.start_login(popen=fake_popen,
                                 browser=lambda link: seen.append(link) or True,
                                 timeout=5)
        self.assertEqual(rc, 0)
        self.assertEqual(seen, [url])

    def test_does_not_store_secrets_or_build_authkey_commands(self):
        source=(ROOT/"src"/"tailscale_browser_login.py").read_text()
        self.assertIn('"up", "--json"',source)
        self.assertIn('"pkexec"',source)
        self.assertIn("stderr=subprocess.DEVNULL",source)
        self.assertNotIn("shell=True",source)
        self.assertNotIn("--auth-key",source)
        self.assertNotIn('print(url)',source)

if __name__=="__main__":
    unittest.main()
