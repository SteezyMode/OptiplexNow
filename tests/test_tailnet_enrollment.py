"""Offline Tailscale owner staging tests; never touch real tailnet/host/SSH."""
import http.client
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "src")]
from tailnet_owner_identity import (tailnet_ipv4, peer_from_whois,
                                   pinned_owner_id, verify_owner_peer)
from tailnet_enrollment import ROUTE, make_handler
from http.server import HTTPServer

spec = importlib.util.spec_from_file_location(
    "now_owner_enroll_tailnet", ROOT / "src/owner-enroll-client.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

OWNER = "1042"
SOURCE = "100.85.2.8"


def identity_fixture():
    return {"Node": {"StableID": "n123456", "Addresses": [SOURCE + "/32"],
                     "User": int(OWNER), "Tags": []},
            "UserProfile": {"ID": int(OWNER)}}


class WhoIsIdentityTests(unittest.TestCase):
    def test_exact_source_account_and_node_are_required(self):
        self.assertEqual(peer_from_whois(SOURCE, identity_fixture()),
                         (OWNER, "n123456"))
        altered = identity_fixture()
        altered["Node"]["Addresses"] = [SOURCE + "/24"]
        self.assertIsNone(peer_from_whois(SOURCE, altered))
        altered = identity_fixture()
        altered["Node"]["Tags"] = ["tag:host"]
        self.assertIsNone(peer_from_whois(SOURCE, altered))
        altered = identity_fixture()
        altered["Node"]["User"] = 2048
        self.assertIsNone(peer_from_whois(SOURCE, altered))
        altered = identity_fixture()
        altered["UserProfile"]["ID"] = "foo@example.com"
        self.assertIsNone(peer_from_whois(SOURCE, altered))
        self.assertIsNone(peer_from_whois("192.168.1.5", identity_fixture()))
        self.assertIsNone(peer_from_whois("100.100.100.100", identity_fixture()))

    def test_whois_uses_authoritative_local_tailscale_and_pinned_owner(self):
        class Response:
            returncode = 0
            stdout = json.dumps(identity_fixture())
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            return Response()
        self.assertEqual(verify_owner_peer(SOURCE, OWNER, runner=run),
                         (OWNER, "n123456"))
        self.assertIsNone(verify_owner_peer(SOURCE, "2048", runner=run))
        self.assertEqual(calls[0], ["tailscale", "whois", "--json", SOURCE])
        self.assertIsNone(verify_owner_peer("10.0.0.1", OWNER, runner=run))

    def test_owner_id_file_must_be_local_private_and_exact(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "owner-id"
            path.write_text("1042\n")
            path.chmod(0o600)
            self.assertEqual(pinned_owner_id(str(path)), OWNER)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                pinned_owner_id(str(path))
            path.chmod(0o600)
            symlink = Path(folder) / "link"
            symlink.symlink_to(path)
            with self.assertRaises(ValueError):
                pinned_owner_id(str(symlink))
            path.write_text("0\n")
            with self.assertRaises(ValueError):
                pinned_owner_id(str(path))


class ServerStagingTests(unittest.TestCase):
    def setUp(self):
        self.is_owner = True
        self.staged = []
        def verify(source, pinned):
            return (OWNER, "n123456") if self.is_owner and pinned == OWNER else None
        def stage(state_dir, key, *, source_ip):
            self.staged.append((state_dir, key))
            return {"success": True, "status": "pending",
                    "request_id": "a" * 32, "code": "123456",
                    "fingerprint": "b" * 20}
        self.server = HTTPServer(
            ("127.0.0.1", 0),
            make_handler(OWNER, "/private/owner-state", verify=verify, stage=stage))
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def post(self, payload=None, *, path=ROUTE, headers=None):
        if payload is None:
            payload = {"version": 1, "public_key": "ssh-ed25519 AAAA"}
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=2)
        try:
            values = {"Content-Type": "application/json"}
            if headers:
                values.update(headers)
            connection.request("POST", path, body=json.dumps(payload), headers=values)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_same_owner_can_only_stage_public_key(self):
        status, result = self.post()
        self.assertEqual(status, 202)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["code"], "123456")
        self.assertEqual(self.staged,
                         [("/private/owner-state", "ssh-ed25519 AAAA")])
        self.assertNotIn("approved", result)
        self.assertNotIn("client_id", result)

    def test_unknown_guest_rejected_before_staging(self):
        self.is_owner = False
        self.assertEqual(self.post()[0], 403)
        self.assertEqual(self.staged, [])
        self.is_owner = True
        self.assertEqual(self.post(path="/v1/owner/approve")[0], 404)
        self.assertEqual(self.staged, [])
        self.assertEqual(self.post(headers={"Origin": "https://bad.example"})[0], 403)
        self.assertEqual(self.staged, [])

    def test_payload_cannot_choose_owner_or_wolf_client(self):
        for payload in ({"version": 1, "public_key": "k", "client_id": "1001"},
                        {"version": 1, "public_key": "k", "owner_id": OWNER},
                        {"version": True, "public_key": "k"},
                        {"public_key": "k"}, []):
            with self.subTest(payload=payload):
                self.assertEqual(self.post(payload)[0], 400)
        self.assertEqual(self.staged, [])


class ClientRequestTests(unittest.TestCase):
    def test_client_uses_only_fixed_tailnet_endpoint_and_public_key(self):
        with tempfile.TemporaryDirectory() as folder:
            public = Path(folder) / "id_ed25519.pub"
            public.write_text("ssh-ed25519 AAAATEST test@macbook")
            class Keys:
                @staticmethod
                def ensure_key():
                    return Path(folder) / "id_ed25519", public
            seen = []
            class FakeConnection:
                def __init__(self, host, port, timeout):
                    seen.append(("connect", host, port, timeout))
                def request(self, method, path, body, headers):
                    seen.append((method, path, json.loads(body), headers))
                def getresponse(self):
                    class Reply:
                        status = 202
                        def read(self, limit):
                            return json.dumps({"success": True, "status": "pending",
                                "request_id": "a"*32, "code": "123456",
                                "fingerprint": "b"*20}).encode()
                    return Reply()
                def close(self):
                    seen.append(("close",))
            response = client.request_tailnet(
                SOURCE, key_module=Keys, connection=FakeConnection)
            self.assertEqual(response["code"], "123456")
            self.assertEqual(seen[0][:3], ("connect", SOURCE, 18793))
            self.assertEqual(seen[1][0:2], ("POST", ROUTE))
            self.assertEqual(set(seen[1][2]), {"version", "public_key"})
            self.assertNotIn("ssh", str(seen[0]))
            for ip in ("192.168.1.4", "100.100.100.100", "example.com", "1.1.1.1"):
                with self.subTest(ip=ip), self.assertRaises(ValueError):
                    client.request_tailnet(ip, key_module=Keys,
                                           connection=FakeConnection)

    def test_refused_listener_allows_existing_owner_pilot_only(self):
        with patch.object(client, "request_tailnet", side_effect=ConnectionRefusedError):
            with patch.object(client, "request", return_value={"status": "pending"}) as legacy:
                self.assertEqual(client.request_using_available_transport(SOURCE, "owner"),
                                 {"status": "pending"})
                legacy.assert_called_once()
        with patch.object(client, "request_tailnet", side_effect=ValueError("denied")):
            with patch.object(client, "request") as legacy:
                with self.assertRaises(ValueError):
                    client.request_using_available_transport(SOURCE, "owner")
                legacy.assert_not_called()

    def test_package_and_ui_do_not_auto_start_host_server(self):
        pkg = (ROOT / "package.py").read_text()
        ui = (ROOT / "src/owner-enroll-ui.py").read_text()
        self.assertIn("'tailnet_owner_identity.py','tailnet_enrollment.py'", pkg)
        self.assertIn("request_using_available_transport(", ui)
        self.assertNotIn("tailnet_enrollment.py --serve", pkg)


if __name__ == "__main__":
    unittest.main()
