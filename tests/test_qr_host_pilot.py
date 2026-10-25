"""Offline immutable-install tests; no real host, Tailscale or Docker writes."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "qr_host_pilot", ROOT / "tools/qr_host_pilot.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
REV = "a" * 40


class PilotInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.source = self.home / ("OptiplexNow-" + REV)
        self.source.mkdir()
        self.dest = self.home / "qr-host"
        for name in pilot.MODULES:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# fixed simulated module " + name + "\n")

    def test_copy_is_atomic_private_and_does_not_start_listener(self):
        existing = self.home / "authorized_keys"
        existing.write_text("KEEP OWNER KEYS\n")
        with patch("subprocess.run") as run:
            installed = pilot.install_tree(self.source, self.dest, REV)
            run.assert_not_called()
        self.assertEqual(existing.read_text(), "KEEP OWNER KEYS\n")
        self.assertEqual(installed.stat().st_mode & 0o777, 0o700)
        self.assertEqual((installed / "run-qr-pilot").stat().st_mode & 0o777, 0o700)
        self.assertFalse((installed / "run-qr-pilot").is_symlink())
        self.assertEqual((installed / "manifest.json").stat().st_mode & 0o777, 0o600)
        manifest = json.loads((installed / "manifest.json").read_text())
        self.assertEqual(manifest["revision"], REV)
        self.assertEqual(set(manifest["files"]), set(pilot.MODULES))
        for module in pilot.MODULES:
            path = installed / module
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.read_bytes(), (self.source / module).read_bytes())
        runner = (installed / "run-qr-pilot").read_text()
        self.assertIn(" --enable-remote-approval", runner)
        self.assertNotIn(" --serve", runner)
        self.assertIn("--approver-node-id-file", runner)
        self.assertIn("--wolf-config", runner)
        with self.assertRaisesRegex(pilot.InstallError, "already installed"):
            pilot.install_tree(self.source, self.dest, REV)
        pilot.remove_tree(self.dest, REV)
        self.assertFalse(installed.exists())
        self.assertEqual(existing.read_text(), "KEEP OWNER KEYS\n")

    def test_missing_module_and_symlink_fail_before_install(self):
        target = self.source / pilot.MODULES[0]
        target.unlink()
        with self.assertRaisesRegex(pilot.InstallError, "Missing"):
            pilot.install_tree(self.source, self.dest, REV)
        target.symlink_to("/dev/null")
        with self.assertRaisesRegex(pilot.InstallError, "Missing"):
            pilot.install_tree(self.source, self.dest, REV)
        self.assertFalse((self.dest / REV).exists())

    def test_revision_and_unsafe_install_base_fail_closed(self):
        with self.assertRaisesRegex(pilot.InstallError, "revision"):
            pilot.install_tree(self.source, self.dest, "main")
        self.dest.symlink_to(self.home / "elsewhere")
        with self.assertRaisesRegex(pilot.InstallError, "Unsafe"):
            pilot.install_tree(self.source, self.dest, REV)

    def test_manifest_mismatch_blocks_removal(self):
        installed = pilot.install_tree(self.source, self.dest, REV)
        manifest = installed / "manifest.json"
        data = json.loads(manifest.read_text())
        data["revision"] = "b" * 40
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(pilot.InstallError, "does not match"):
            pilot.remove_tree(self.dest, REV)
        self.assertTrue(installed.exists())


if __name__ == "__main__":
    unittest.main()
