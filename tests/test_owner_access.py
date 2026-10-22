"""Offline owner policy contract. No Docker, privileged writes or real Steam data."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import owner_access as policy

spec = importlib.util.spec_from_file_location(
    "now_owner_access_local", ROOT / "src" / "owner-access-local.py")
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


def profiles(*names):
    return {"success": True, "profiles": [
        {"id": "moonlight-profile-id", "apps": [{"title": "Steam"}]},
        *({"id": name, "pin": [1, 2, 3, 4],
           "apps": [{"title": "Steam", "runner": {"env": ["PASSWORD=SECRET"]}}]}
          for name in names)
    ]}


def clients(*pairs):
    return {"success": True, "clients": [
        {"client_id": client, "app_state_folder": folder,
         "settings": {"run_uid": 1000}} for client, folder in pairs
    ]}


class OwnerAccessTests(unittest.TestCase):
    def setUp(self):
        self.data = policy.new_owner("user", profiles("user"))
        self.wolf = clients(("1001", "1001"), ("1002", "1002"))

    def test_owner_profile_is_explicit_and_named(self):
        self.assertEqual(self.data["workspaces"][0]["profile_id"], "user")
        self.assertEqual(len(self.data["principals"]), 1)
        self.assertEqual(self.data["principals"][0]["role"], "owner")
        self.assertEqual(self.data["devices"], [])
        with self.assertRaises(policy.PolicyError):
            policy.new_owner("moonlight-profile-id", profiles("user"))
        with self.assertRaises(policy.PolicyError):
            policy.new_owner("nonexistent", profiles("user"))
        with self.assertRaises(policy.PolicyError):
            policy.new_owner("user", profiles("user", "user"))
        self.assertNotIn("SECRET", json.dumps(self.data))

    def test_two_owner_devices_one_persistent_workspace(self):
        policy.approve_device(self.data, "1001", self.wolf)
        policy.approve_device(self.data, "1002", self.wolf)
        first = policy.resolve_games(self.data, "1001", self.wolf)
        second = policy.resolve_games(self.data, "1002", self.wolf)
        self.assertEqual(first, second)
        self.assertEqual(first["wolf_profile_id"], "user")
        self.assertEqual(first["principal_id"], self.data["principals"][0]["id"])
        self.assertNotIn("client_id", first)

    def test_unapproved_revoked_and_unknown_clients_denied(self):
        with self.assertRaisesRegex(policy.PolicyError, "no owner"):
            policy.resolve_games(self.data, "1001", self.wolf)
        with self.assertRaisesRegex(policy.PolicyError, "not in"):
            policy.approve_device(self.data, "9999", self.wolf)
        policy.approve_device(self.data, "1001", self.wolf)
        with self.assertRaisesRegex(policy.PolicyError, "already"):
            policy.approve_device(self.data, "1001", self.wolf)
        policy.revoke_device(self.data, "1001")
        with self.assertRaisesRegex(policy.PolicyError, "no owner"):
            policy.resolve_games(self.data, "1001", self.wolf)
        with self.assertRaisesRegex(policy.PolicyError, "No active"):
            policy.revoke_device(self.data, "1001")
        policy.approve_device(self.data, "1001", self.wolf)
        self.assertEqual(policy.resolve_games(self.data, "1001", self.wolf)["wolf_profile_id"], "user")

    def test_only_devices_still_paired_may_resolve(self):
        policy.approve_device(self.data, "1001", self.wolf)
        with self.assertRaisesRegex(policy.PolicyError, "not paired"):
            policy.resolve_games(self.data, "1001", clients(("1002", "1002")))

    def test_duplicate_records_and_conflicting_folders(self):
        inventory = clients(("1001", "1001"), ("1001", "1001"))
        self.assertEqual(policy.paired_client_ids(inventory), frozenset({"1001"}))
        policy.approve_device(self.data, "1001", inventory)
        conflict = clients(("1001", "1001"), ("1001", "something-else"))
        with self.assertRaisesRegex(policy.PolicyError, "Conflicting"):
            policy.resolve_games(self.data, "1001", conflict)
        with self.assertRaisesRegex(policy.PolicyError, "Conflicting"):
            policy.approve_device(policy.new_owner("user", profiles("user")), "1001", conflict)

    def test_invalid_identity_or_roles_do_not_grant(self):
        for invalid_id in ("-1", "user", "0; rm /", "", None, 1001):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(policy.PolicyError):
                    policy.approve_device(self.data, invalid_id, self.wolf)
        for bad in [
            lambda x: x["principals"].append({"id": "evil", "role": "member"}),
            lambda x: x["workspaces"][0].update({"profile_id": "../owner"}),
            lambda x: x["workspaces"][0].update({"profile_id": "moonlight-profile-id"}),
            lambda x: x["devices"].append({"client_id": "1001", "principal_id": "bad",
                                            "services": ["admin"], "revoked": False}),
            lambda x: x.update({"version": 2}),
        ]:
            damaged = copy.deepcopy(self.data)
            bad(damaged)
            with self.assertRaises(policy.PolicyError):
                policy.validate(damaged)

    def test_atomic_private_state_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            store = policy.OwnerStore(str(Path(temp) / "private"))
            with store.locked() as fd:
                self.assertIsNone(store.read(fd))
                store.write(fd, self.data)
                policy.approve_device(self.data, "1001", self.wolf)
                store.write(fd, self.data)
                loaded = store.read(fd)
            self.assertEqual(policy.resolve_games(loaded, "1001", self.wolf)["wolf_profile_id"], "user")
            folder = Path(temp) / "private"
            self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((folder / "owner-access.json").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((folder / ".lock").stat().st_mode), 0o600)

    def test_rejects_symlinked_store_and_loose_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "safe"
            target.mkdir(mode=0o700)
            link = Path(temp) / "link"
            link.symlink_to(target)
            with self.assertRaises(policy.PolicyError):
                with policy.OwnerStore(str(link)).locked():
                    pass
            target.chmod(0o755)
            with self.assertRaises(policy.PolicyError):
                with policy.OwnerStore(str(target)).locked():
                    pass

    def test_rejects_tampered_policy_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            store = policy.OwnerStore(str(Path(temp) / "private"))
            with store.locked() as fd:
                store.write(fd, self.data)
            path = Path(temp) / "private" / "owner-access.json"
            path.chmod(0o644)
            with store.locked() as fd:
                with self.assertRaisesRegex(policy.PolicyError, "permissions"):
                    store.read(fd)

    def test_local_cli_refuses_unprivileged_or_unconfirmed_adoption(self):
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as temp:
            store = policy.OwnerStore(str(Path(temp) / "private"))
            arg = Namespace(action="initialize", profile="user", confirm_existing_owner=True)
            with mock.patch.object(local.os, "geteuid", return_value=1000):
                with self.assertRaisesRegex(policy.PolicyError, "administrator"):
                    local.run(arg, store=store, wolf_api=lambda *_: profiles("user"))
            arg.confirm_existing_owner = False
            with mock.patch.object(local.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(policy.PolicyError, "Explicit"):
                    local.run(arg, store=store, wolf_api=lambda *_: profiles("user"))
            # Root-only gate is tested independently; the owner store itself is
            # tested as an unprivileged temporary fixture above.

    def test_local_cli_allowlist_does_not_expose_writes_or_stream(self):
        from argparse import Namespace
        with mock.patch.object(local.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(policy.PolicyError, "Unsupported"):
                local.run(Namespace(action="start-stream"),
                          store=mock.Mock(), wolf_api=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
