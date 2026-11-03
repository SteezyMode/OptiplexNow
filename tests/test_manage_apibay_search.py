"""Offline regression tests for the reversible single-provider migration."""
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "server/search_plugins/bruiser_apibay.py"
MODULE_PATH = ROOT / "tools/manage_apibay_search.py"
spec = importlib.util.spec_from_file_location("bruiser_search_transition_test", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeAPI:
    def __init__(self, enabled=("torrentscsv", "limetorrents"), fail_search=False):
        self.data = {
            name: {"name": name, "enabled": name in enabled, "version": "1.0"}
            for name in ("torrentscsv", "limetorrents")
        }
        self.fail_search = fail_search
        self.records = []

    def plugins(self):
        return {k: dict(v) for k, v in self.data.items()}

    def request(self, route, fields=None):
        self.records.append((route, fields))
        assert route == "search/installPlugin"
        assert fields == {"sources": mod.SOURCE_URL}
        self.data["bruiser_apibay"] = {
            "name": "bruiser_apibay", "fullName": "Bruiser - API Bay",
            "url": "https://apibay.org", "enabled": True,
            "version": "1.1",
        }
        return b""

    def find_plugin(self, name):
        return self.plugins().get(name)

    def set_enabled(self, names, enabled):
        names = list(names)
        self.records.append(("set_enabled", (sorted(names), enabled)))
        for name in names:
            self.data[name]["enabled"] = enabled

    def verified_search(self):
        self.records.append(("verified_search", None))
        if self.fail_search:
            raise mod.TransitionError("API Bay verification failed")
        return 32


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.patches = [
            patch.object(mod, "CONFIG_ROOT", base),
            patch.object(mod, "BACKUP_FILE", base / "backup.json"),
            patch.object(mod, "PLUGIN_FILE", base / "bruiser_apibay.py"),
            patch.object(mod, "fetch_source", return_value=b"verified module"),
            patch.object(mod, "nova_preflight", return_value=24),
            patch.object(mod, "local_code_matches", return_value=True),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_source_pinned_to_exact_git_blob(self):
        self.assertEqual(mod.git_blob_sha(PLUGIN.read_bytes()),
                         mod.SOURCE_GIT_BLOB)

    def test_apply_switches_only_plugin_flags_with_rollback_record(self):
        api = FakeAPI()
        mod.activate(api)
        self.assertEqual(
            {name for name, meta in api.plugins().items() if meta["enabled"]},
            {"bruiser_apibay"})
        previous = mod.snapshot_read()
        self.assertEqual(previous, {"torrentscsv": True, "limetorrents": True})
        mode = mod.BACKUP_FILE.stat().st_mode
        self.assertEqual(stat.S_IMODE(mode), 0o600)
        self.assertIn(("verified_search", None), api.records)
        self.assertTrue(all(x[0] in ("search/installPlugin", "set_enabled",
                                     "verified_search") for x in api.records))
        mod.restore(api, previous)
        self.assertEqual(
            {name for name, meta in api.plugins().items() if meta["enabled"]},
            {"torrentscsv", "limetorrents"})

    def test_failing_nova_check_never_installs_or_changes_state(self):
        api = FakeAPI()
        with patch.object(mod, "nova_preflight",
                          side_effect=mod.TransitionError("probe failed")):
            with self.assertRaises(mod.TransitionError):
                mod.activate(api)
        self.assertEqual(api.records, [])
        self.assertFalse(mod.BACKUP_FILE.exists())

    def test_failed_installed_search_restores_original_engines(self):
        api = FakeAPI(fail_search=True)
        with self.assertRaises(mod.TransitionError):
            mod.activate(api)
        self.assertEqual(
            {name for name, meta in api.plugins().items() if meta["enabled"]},
            {"torrentscsv", "limetorrents"})
        self.assertFalse(mod.BACKUP_FILE.exists())

    def test_unexpected_enabled_plugin_blocks_before_install(self):
        api = FakeAPI(enabled=("torrentscsv",))
        with self.assertRaisesRegex(mod.TransitionError, "Unexpected enabled"):
            mod.activate(api)
        self.assertEqual(api.records, [])

    def test_conflicting_installed_source_blocks(self):
        api = FakeAPI()
        api.data["bruiser_apibay"] = {
            "name": "bruiser_apibay", "enabled": True
        }
        with self.assertRaisesRegex(mod.TransitionError, "already installed"):
            mod.activate(api)
        self.assertEqual(api.records, [])

    def test_existing_backup_blocks_overwrite(self):
        mod.BACKUP_FILE.write_text("old backup", encoding="utf-8")
        api = FakeAPI()
        with self.assertRaisesRegex(mod.TransitionError, "Pre-existing rollback"):
            mod.activate(api)
        self.assertEqual(mod.BACKUP_FILE.read_text(), "old backup")
        self.assertEqual(api.records, [])

    def test_invalid_backup_does_not_change_plugins(self):
        mod.BACKUP_FILE.write_text('{"version":1,"previous":{"evil":true}}')
        with self.assertRaises(mod.TransitionError):
            mod.snapshot_read()

    def test_repeat_is_idempotent_after_success(self):
        api = FakeAPI()
        mod.activate(api)
        before = list(api.records)
        mod.activate(api)
        self.assertEqual(api.records, before)


if __name__ == "__main__":
    unittest.main()
