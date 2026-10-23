"""No-network tests for the approved owner device queue display helper."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("now_queue_client", ROOT / "src" / "download-queue-client.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class QueueClientTests(unittest.TestCase):
    def run_payload(self, payload, status=0):
        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp) / "id_ed25519"
            key.write_text("test only")
            def runner(cmd, **kwargs):
                self.assertEqual(cmd[0], "ssh")
                self.assertIn("IdentitiesOnly=yes", cmd)
                self.assertIn("StrictHostKeyChecking=yes", cmd)
                self.assertEqual(cmd[-1], "optiplex@100.121.156.34")
                self.assertEqual(kwargs["input"], b'{"version":1,"action":"downloads_queue"}\n')
                return subprocess.CompletedProcess(cmd, status, payload, b"")
            with patch.object(mod, "KEY", key):
                return mod.fetch("100.121.156.34", "optiplex", runner=runner)

    def test_sanitized_queue_display(self):
        payload = json.dumps({"success":True,"service":"qbittorrent",
            "queue":[{"name":"test\nmovie","state":"downloading","progress_percent":21.25,
                      "save_path":"/not-for-client","hash":"secret"}]}).encode()
        out = self.run_payload(payload)
        self.assertIn("test movie", out)
        self.assertIn("21.2%", out)
        self.assertNotIn("/not-for-client", out)
        self.assertNotIn("secret", out)

    def test_empty_queue(self):
        self.assertEqual(self.run_payload(
            b'{"success":true,"service":"qbittorrent","queue":[]}'),
            "No downloads in queue.")

    def test_unapproved_response_fails_closed(self):
        for payload in (b"{}", b'{"success":false}',
                        b'{"success":true,"service":"other","queue":[]}',
                        b'{"success":true,"service":"qbittorrent","queue":[{"name":"A","state":"ok","progress_percent":101}]}',
                        b"x" * 65537):
            with self.subTest(payload=payload[:40]), self.assertRaises(ValueError):
                self.run_payload(payload)

    def test_invalid_host_and_user(self):
        self.assertFalse(mod.valid_host("-oProxyCommand=anything"))
        self.assertFalse(mod.valid_user("-evil"))
        self.assertFalse(mod.valid_user("name with spaces"))


if __name__=="__main__":
    unittest.main()
