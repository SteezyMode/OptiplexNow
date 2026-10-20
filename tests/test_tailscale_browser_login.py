"""Validate URL and first-run login safety without touching the real tailnet."""
import importlib.util
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
