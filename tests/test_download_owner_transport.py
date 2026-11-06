"""Regression contract for the fixed Downloads owner SSH argv.

Runs entirely offline. The host/device/access validation stays in each
Downloads client and is covered by their existing tests.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from download_owner_transport import restricted_ssh_argv


class RestrictedDownloadsTransport(unittest.TestCase):
    def test_v1221_argv_is_exact_and_does_not_invoke_a_shell(self):
        key = Path("/tmp/client-only-key")
        expected = [
            "ssh", "-F", "/dev/null", "-T", "-i", str(key),
            "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=6",
            "optiplex@100.121.156.34",
        ]
        self.assertEqual(restricted_ssh_argv("100.121.156.34", "optiplex", key),
                         expected)
        self.assertNotIn("StrictHostKeyChecking=no", expected)
        self.assertNotIn("UserKnownHostsFile=/dev/null", expected)
        self.assertNotIn("ProxyCommand", expected)
        self.assertEqual(expected.count("-T"), 1)

    def test_all_download_clients_use_the_single_builder(self):
        calls = {
            "download-queue-client.py": 1,
            "download-search-client.py": 2,
            "download-operations-client.py": 1,
        }
        for name, count in calls.items():
            with self.subTest(name=name):
                data = (ROOT / "src" / name).read_text(encoding="utf-8")
                self.assertEqual(
                    data.count("restricted_ssh_argv(host,user,KEY)"), count)
                self.assertNotIn('"ssh","-F","/dev/null","-T","-i",str(KEY)', data)
        package = (ROOT / "package.py").read_text(encoding="utf-8")
        self.assertEqual(package.count(
            "shutil.copy2(root/'src/download_owner_transport.py'"), 1)


if __name__ == "__main__":
    unittest.main()
