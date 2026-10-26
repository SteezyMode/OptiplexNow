"""Offline owner-approved enrollment tests. Never touch live SSH, Wolf or Steam."""
import base64
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "server"), str(ROOT / "tests")]

from owner_access import OwnerStore, PolicyError
from owner_enrollment import stage_request, pending_requests, approve_request
from test_owner_lobby import fixtures


def public_key(symbol=b"k"):
    name = b"ssh-ed25519"
    body = (struct.pack("!I", len(name)) + name +
            struct.pack("!I", 32) + symbol * 32)
    return "ssh-ed25519 " + base64.b64encode(body).decode() + " test@device"


class OwnerEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / "owner-state"
        self.store = OwnerStore(str(self.state))
        with self.store.locked() as fd:
            self.store.write(fd, fixtures()[0])
        self.ssh = self.base / ".ssh"
        self.ssh.mkdir(mode=0o700)
        self.auth = self.ssh / "authorized_keys"
        self.original = "ssh-ed25519 " + base64.b64encode(b"unchanged-owner-access").decode() + " original\n"
        self.auth.write_text(self.original)
        self.auth.chmod(0o600)
        self.broker = ROOT / "server/owner_games_ssh.py"
        self.wolf = lambda method, path: {
            "success": True, "clients": [
                {"client_id": "1001", "app_state_folder": "1001"},
                {"client_id": "1002", "app_state_folder": "1002"}]}
        self.now = 1700000000

    def stage(self, key=None):
        return stage_request(self.state, key or public_key(), now=self.now)

    def approve(self, request, client="1002", *, confirmed=True, code=None, now=None):
        return approve_request(
            self.state, request["request_id"], code or request["code"], client,
            confirmed=confirmed, auth_path=self.auth, broker_path=self.broker,
            wolf_api=self.wolf, now=self.now if now is None else now,
            require_live_binding=False)

    def load(self):
        with self.store.locked() as fd:
            return self.store.read(fd)

    def test_stage_only_does_not_grant_access_or_replace_existing_keys(self):
        before = self.load()
        request = self.stage()
        self.assertEqual(request["status"], "pending")
        self.assertEqual(len(request["code"]), 6)
        self.assertEqual(self.auth.read_text(), self.original)
        self.assertEqual(self.load(), before)
        self.assertEqual(pending_requests(self.state, now=self.now)[0]["request_id"],
                         request["request_id"])
        self.assertEqual(request["request_id"], self.stage()["request_id"])
        request_file = self.state / "pending-enrollment" / request["request_id"]
        self.assertEqual(stat.S_IMODE(request_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(request_file.parent.stat().st_mode), 0o700)

    def test_live_source_binding_rejects_wrong_wolf_id_and_network_route(self):
        """Regression: wrong numeric picker must never grant another device."""
        source = "192.168.40.90"
        request = stage_request(self.state, public_key(b"x"),
                                source_ip=source, now=self.now)
        data = {
            "/api/v1/clients": {"success": True, "clients": [
                {"client_id": "1001", "app_state_folder": "1001"},
                {"client_id": "1002", "app_state_folder": "1002"}]},
            "/api/v1/apps": {"success": True, "apps": [
                {"id": "wolf-ui-app", "title": "Wolf UI"}]},
            "/api/v1/lobbies": {"success": True, "lobbies": []},
            "/api/v1/sessions": {"success": True, "sessions": [{
                "client_id": "1001", "client_ip": source,
                "app_id": "wolf-ui-app"}]},
        }
        def api(method, path):
            self.assertEqual(method, "GET")
            return data[path]
        def approve(client):
            return approve_request(
                self.state, request["request_id"], request["code"], client,
                confirmed=True, auth_path=self.auth, broker_path=self.broker,
                wolf_api=api, now=self.now)

        for client, ip, error in (
            ("1002", source, "differs from verified requester"),
            ("1001", "192.168.40.59", "origin differs"),
        ):
            with self.subTest(client=client, ip=ip):
                data["/api/v1/sessions"]["sessions"][0]["client_ip"] = ip
                with self.assertRaisesRegex(PolicyError, error):
                    approve(client)
                self.assertEqual(self.auth.read_text(), self.original)
                self.assertEqual([d["client_id"] for d in self.load()["devices"]], ["1001"])
        # On a correctly matched request, and ONLY then, the existing
        # atomic owner enrollment transaction may proceed.
        data["/api/v1/sessions"]["sessions"][0].update(
            client_id="1002", client_ip=source)
        self.assertEqual(approve("1002")["status"], "approved")
        self.assertIn("--client-id 1002", self.auth.read_text())

    def test_legacy_or_ambiguous_stream_cannot_create_new_grant(self):
        """Old requests without measured source cannot bypass binding."""
        request = self.stage(public_key(b"z"))
        with self.assertRaisesRegex(PolicyError, "Legacy request"):
            approve_request(
                self.state, request["request_id"], request["code"], "1002",
                confirmed=True, auth_path=self.auth, broker_path=self.broker,
                wolf_api=self.wolf, now=self.now)
        self.assertEqual(self.auth.read_text(), self.original)

    def test_verified_owner_approval_preserves_old_owner_and_ssh(self):
        request = self.stage()
        result = self.approve(request)
        self.assertEqual(result["status"], "approved")
        data = self.load()
        self.assertEqual([d["client_id"] for d in data["devices"]], ["1001", "1002"])
        self.assertTrue(all(not d["revoked"] for d in data["devices"]))
        text = self.auth.read_text()
        self.assertTrue(text.startswith(self.original))
        self.assertIn('restrict,command="/usr/bin/python3 ', text)
        self.assertIn("--client-id 1002", text)
        self.assertIn(public_key().split()[1], text)
        self.assertNotIn("test@device", text)
        self.assertEqual(stat.S_IMODE(self.auth.stat().st_mode), 0o600)
        self.assertEqual(pending_requests(self.state, now=self.now), [])
        backups = list((self.state / "enrollment-backups").iterdir())
        self.assertEqual(len(backups), 2)
        key_backup = next(p for p in backups if p.name.startswith("authorized_keys-"))
        policy_backup = next(p for p in backups if p.name.startswith("owner-access-"))
        self.assertEqual(key_backup.read_text(), self.original)
        self.assertEqual(stat.S_IMODE(policy_backup.stat().st_mode), 0o600)
        self.assertEqual(len(json.loads(policy_backup.read_text())["devices"]), 1)

    def test_existing_host_broker_is_discovered_without_installing_another(self):
        from owner_games_enroll import authorized_line
        existing = authorized_line(public_key(b"o"), "1001", self.broker)
        self.auth.write_text(self.original + existing + "\n")
        request = self.stage(public_key(b"n"))
        result = approve_request(
            self.state, request["request_id"], request["code"], "1002",
            confirmed=True, auth_path=self.auth, wolf_api=self.wolf,
            now=self.now, require_live_binding=False)
        self.assertEqual(result["status"], "approved")
        text = self.auth.read_text()
        self.assertEqual(text.count(str(self.broker)), 2)
        self.assertIn("--client-id 1001", text)
        self.assertIn("--client-id 1002", text)

    def test_without_existing_broker_or_explicit_reviewed_path_denies(self):
        request = self.stage()
        with self.assertRaisesRegex(PolicyError, "existing owner-restricted broker"):
            approve_request(self.state, request["request_id"], request["code"],
                            "1002", confirmed=True, auth_path=self.auth,
                            wolf_api=self.wolf, now=self.now,
                            require_live_binding=False)
        self.assertEqual(self.auth.read_text(), self.original)
        self.assertEqual([d["client_id"] for d in self.load()["devices"]], ["1001"])

    def test_atomic_rollback_if_policy_write_fails(self):
        from unittest.mock import patch
        request = self.stage()
        # The forced key is installed first, but must be removed atomically
        # if owner policy cannot be committed. The original access survives.
        with patch.object(OwnerStore, "write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.approve(request)
        self.assertEqual(self.auth.read_text(), self.original)
        self.assertEqual([d["client_id"] for d in self.load()["devices"]], ["1001"])
        self.assertEqual(len(pending_requests(self.state, now=self.now)), 1)

    def test_no_approval_without_verified_binding(self):
        request = self.stage()
        for opts in ({"confirmed": False}, {"code": "123xxx"},
                     {"code": "000000" if request["code"] != "000000" else "000001"}, {"client": "9999"},
                     {"now": self.now + 601}):
            with self.subTest(opts=opts), self.assertRaises((PolicyError, TypeError)):
                self.approve(request, **opts)
            self.assertEqual(self.auth.read_text(), self.original)
            self.assertEqual([d["client_id"] for d in self.load()["devices"]], ["1001"])

    def test_revoked_or_duplicate_key_is_denied(self):
        request = self.stage()
        from owner_access import revoke_device, approve_device
        with self.store.locked() as fd:
            data = self.store.read(fd)
            approve_device(data, "1002", self.wolf("GET", "/api/v1/clients"))
            revoke_device(data, "1002")
            self.store.write(fd, data)
        with self.assertRaisesRegex(PolicyError, "Revoked"):
            self.approve(request)
        self.auth.write_text(self.original + public_key() + "\n")
        with self.assertRaisesRegex(PolicyError, "already installed"):
            self.approve(request, client="1001")
        self.assertFalse(any("--client-id 1002" in line
                             for line in self.auth.read_text().splitlines()))

    def test_invalid_key_does_not_create_request(self):
        for text in ("ssh-rsa AAAA", "ssh-ed25519 AAAA", "abc\nInjected",
                     "ssh-ed25519 !not-base64!"):
            with self.subTest(text=text), self.assertRaises(PolicyError):
                self.stage(text)
        self.assertEqual(pending_requests(self.state, now=self.now), [])

    def test_rejects_unsafe_authorized_keys(self):
        request = self.stage()
        self.auth.chmod(0o666)
        with self.assertRaisesRegex(PolicyError, "Unsafe"):
            self.approve(request)
        self.assertEqual([d["client_id"] for d in self.load()["devices"]], ["1001"])


if __name__ == "__main__":
    unittest.main()
