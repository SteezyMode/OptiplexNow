"""Disposable owner host migration and package contract (never edits a real home)."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "src/owner-host-upgrade.py"
spec = importlib.util.spec_from_file_location("owner_host_upgrade", SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

KEY = b"ssh-ed25519 " + b"A" * 66
ID = b"11701600982361132536"


class HostPackageUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.ssh = self.home / ".ssh"
        self.ssh.mkdir(mode=0o700)
        self.ssh.chmod(0o700)
        self.package = self.root / "package/owner-bridge/server/owner_games_ssh.py"
        self.package.parent.mkdir(parents=True)
        self.package.write_text("# fixture")
        self.package.chmod(0o644)
        self.legacy = (self.home / ".local/lib/optiplex-now-games/server/owner_games_ssh.py")
        self.auth = self.ssh / "authorized_keys"

    def keyline(self, path):
        return (b'restrict,command="/usr/bin/python3 ' +
                str(path).encode("ascii") + b' --client-id ' + ID +
                b'" ' + KEY + b"\n")

    def write_auth(self, body):
        self.auth.write_bytes(body)
        self.auth.chmod(0o600)

    def inspect(self):
        return module.inspect(home=self.home, package_broker=self.package,
                              package_owner=os.geteuid())

    def activate(self):
        return module.activate(home=self.home, package_broker=self.package,
                               package_owner=os.geteuid())

    def test_unconfigured_never_enrolls_or_creates_key(self):
        self.assertEqual(self.inspect()[0]["status"], "not_configured")
        with self.assertRaises(module.HostUpgradeError):
            self.activate()
        self.assertFalse(self.auth.exists())

    def test_migrate_only_approved_entries_and_retain_other_keys_and_mode(self):
        unchanged = b"# trusted ordinary admin key\nssh-ed25519 "+b"B"*66+b" owner\n"
        original = unchanged + self.keyline(self.legacy) + self.keyline(self.legacy)
        self.write_auth(original)
        self.assertEqual(self.inspect()[0]["status"], "ready")
        result = self.activate()
        self.assertEqual(result["count"], 2)
        updated = self.auth.read_bytes()
        self.assertEqual(updated, unchanged + self.keyline(self.package)*2)
        self.assertEqual(self.auth.stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(result["backup"]).read_bytes(), original)
        self.assertEqual(self.inspect()[0]["status"], "up_to_date")
        with self.assertRaises(module.HostUpgradeError):
            self.activate()

    def test_unknown_or_modified_forced_command_refuses_without_mutation(self):
        old = self.keyline(self.legacy)
        for payload in (old.replace(b"restrict,", b""),
                        old.replace(b" --client-id ", b" -c "),
                        self.keyline(self.root / "someone/owner_games_ssh.py"),
                        old + self.keyline(self.root / "someone/owner_games_ssh.py")):
            self.write_auth(payload)
            with self.assertRaises(module.HostUpgradeError):
                self.activate()
            self.assertEqual(self.auth.read_bytes(), payload)

    def test_symlink_and_unsafe_ssh_permissions_refused(self):
        self.write_auth(self.keyline(self.legacy))
        self.ssh.chmod(0o777)
        with self.assertRaises(module.HostUpgradeError):
            self.activate()
        self.ssh.chmod(0o700)
        self.auth.unlink()
        self.auth.symlink_to(self.root / "missing")
        with self.assertRaises(module.HostUpgradeError):
            self.activate()

    def test_package_handler_must_be_trusted(self):
        self.write_auth(self.keyline(self.legacy))
        self.package.chmod(0o666)
        with self.assertRaises(module.HostUpgradeError):
            self.activate()
        self.assertEqual(self.auth.read_bytes(), self.keyline(self.legacy))

    def test_package_code_import_graph_is_complete(self):
        # Packaging smoke independently imports the installed package paths.
        package_source = (SRC.parents[1] / "package.py").read_text()
        for name in ("owner_games_ssh.py", "owner_games_request.py",
                     "owner_launch.py", "owner_lobby.py",
                     "owner_host_pilot.py", "download_manage.py",
                     "download_search.py", "download_queue.py",
                     "download_inventory.py", "download_destinations.py",
                     "media_endpoint.py", "owner_games_enroll.py"):
            self.assertIn("'" + name + "'", package_source)
        self.assertIn("owner-host-upgrade.py", package_source)
        self.assertIn("Use installed NOW host code?", SRC.read_text())


if __name__ == "__main__":
    unittest.main()
