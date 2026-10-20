"""Unit tests for the MoonlightWeb admin tunnel helper (no server required)."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "open-web-gaming-admin.py"
spec = importlib.util.spec_from_file_location("open_web_gaming_admin", SCRIPT)
admin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admin)


class AdminTunnelTests(unittest.TestCase):
    def test_invalid_hosts_and_users_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for host, user in [("-oProxyCommand=evil", "optiplex"),
                               ("server", "-root"),
                               ("server;command", "optiplex")]:
                with self.assertRaises(ValueError):
                    admin.tunnel_settings(host, user, Path(tmp))

    def test_reuses_existing_verified_ssh_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(admin, "checked_run", return_value=SimpleNamespace(returncode=0)) as run, \
                 patch.object(admin.socket, "create_connection") as connect, \
                 patch.object(admin.subprocess, "Popen") as opener, \
                 patch.object(admin.shutil, "which", return_value="/usr/bin/xdg-open"):
                connect.return_value.__enter__.return_value = None
                opener.return_value.wait.return_value = 0
                self.assertEqual(admin.open_admin("100.121.156.34", "optiplex", Path(tmp)), 0)
                self.assertEqual(run.call_count, 1)
                self.assertIn("-O", run.call_args.args[0])
                url = opener.call_args.args[0][1]
                self.assertTrue(url.startswith("https://127.0.0.1:"))
                self.assertTrue(url.endswith("/admin"))

    def test_starts_loopback_only_forwarding(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(admin, "checked_run", side_effect=[
                SimpleNamespace(returncode=255),
                SimpleNamespace(returncode=0),
            ]) as run, \
                 patch.object(admin.socket, "create_connection"), \
                 patch.object(admin.subprocess, "Popen") as opener, \
                 patch.object(admin.shutil, "which", return_value="/usr/bin/xdg-open"):
                opener.return_value.wait.return_value = 0
                self.assertEqual(admin.open_admin("100.121.156.34", "optiplex", Path(tmp)), 0)
                cmd = run.call_args_list[1].args[0]
                self.assertEqual(cmd[0], "ssh")
                self.assertIn("-L", cmd)
                forward = cmd[cmd.index("-L") + 1]
                self.assertRegex(forward, r"^127\.0\.0\.1:\d+:127\.0\.0\.1:8443$")

    def test_no_browser_when_ssh_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(admin, "checked_run", side_effect=[
                SimpleNamespace(returncode=255),
                SimpleNamespace(returncode=255, stderr="Connection refused"),
            ]), patch.object(admin.subprocess, "Popen") as opener:
                self.assertEqual(admin.open_admin("100.121.156.34", "optiplex", Path(tmp)), 1)
                opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
