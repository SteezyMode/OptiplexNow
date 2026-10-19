"""Exercise actual encrypted client backup/restore without touching user files."""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "build" / "optiplex-now-backup"
PASSWORD = "fixture-password-at-least-12-characters\n"


class EncryptedBackupTests(unittest.TestCase):
    def setUp(self):
        if not HELPER.is_file():
            self.skipTest("Build first: make package (CI always builds before tests).")
        self.tmp = tempfile.TemporaryDirectory(prefix="now-backup-test-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.home.mkdir(mode=0o700)
        self.archive = root / "client.onb"
        self.cfg = self.home / ".config/optiplex-desk/config.ini"
        self.ssh = self.home / ".ssh/id_ed25519"
        self.cfg.parent.mkdir(parents=True, mode=0o700)
        self.ssh.parent.mkdir(parents=True, mode=0o700)
        self.cfg.write_bytes(b"host=fixture.example\nuser=testuser\n")
        self.ssh.write_bytes(b"TEST_FIXTURE_PRIVATE_SSH_KEY_ONLY\n")
        self.cfg.chmod(0o600)
        self.ssh.chmod(0o600)
        self.env = dict(os.environ, HOME=str(self.home))

    def call(self, action, path=None, password=PASSWORD):
        return subprocess.run(
            [str(HELPER), action, str(path or self.archive)],
            input=password, text=True, env=self.env, capture_output=True, timeout=15,
        )

    def test_encrypted_roundtrip_and_permissions(self):
        self.assertEqual(self.call("export").returncode, 0)
        data = self.archive.read_bytes()
        self.assertIn(b"OPNENC1\n", data[:8])
        self.assertNotIn(b"TEST_FIXTURE_PRIVATE_SSH_KEY_ONLY", data)
        self.assertNotIn(b"fixture.example", data)
        self.assertEqual(stat.S_IMODE(self.archive.stat().st_mode), 0o600)

        self.cfg.write_bytes(b"host=changed.example\n")
        self.ssh.unlink()
        self.assertNotEqual(self.call("restore", password="incorrect-password-12345\n").returncode, 0)
        self.assertEqual(self.cfg.read_bytes(), b"host=changed.example\n")
        self.assertFalse(self.ssh.exists())
        self.assertEqual(self.call("restore").returncode, 0)
        self.assertEqual(self.cfg.read_bytes(), b"host=fixture.example\nuser=testuser\n")
        self.assertEqual(self.ssh.read_bytes(), b"TEST_FIXTURE_PRIVATE_SSH_KEY_ONLY\n")
        self.assertEqual(stat.S_IMODE(self.ssh.stat().st_mode), 0o600)

    def test_tampered_ciphertext_rejected_without_writes(self):
        self.assertEqual(self.call("export").returncode, 0)
        tampered = bytearray(self.archive.read_bytes())
        tampered[-1] ^= 0xFF
        self.archive.write_bytes(tampered)
        self.cfg.write_bytes(b"host=preserve.me\n")
        self.assertNotEqual(self.call("restore").returncode, 0)
        self.assertEqual(self.cfg.read_bytes(), b"host=preserve.me\n")

    def test_symlink_target_rejected_before_any_restore(self):
        self.assertEqual(self.call("export").returncode, 0)
        self.cfg.write_bytes(b"host=keep.current\n")
        outside = Path(self.tmp.name) / "outside-file"
        outside.write_bytes(b"do-not-touch\n")
        self.ssh.unlink()
        self.ssh.symlink_to(outside)
        self.assertNotEqual(self.call("restore").returncode, 0)
        self.assertEqual(outside.read_bytes(), b"do-not-touch\n")
        self.assertEqual(self.cfg.read_bytes(), b"host=keep.current\n")


if __name__ == "__main__":
    unittest.main()
