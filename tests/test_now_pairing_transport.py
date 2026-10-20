"""Offline identity parsing and real HTTP/Unix pairing authorization contract.

All networking here is local loopback. Tailscale commands are fixture-only;
no broker, client, or host service is launched on production equipment.
"""
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(HERE))

import now_pairing_requests as pairing
import now_pairing_identity as identity
import now_pairing_owner as owner
import now_pairing_broker as broker


class StubResult:
    returncode = 0

    def __init__(self, data):
        self.stdout = json.dumps(data)


SOURCE = "100.88.21.4"
ALT = "100.88.21.5"


def whois(node_id="nTestClient", user_id=1042, ip=SOURCE, **extra):
    node = {"StableID": node_id, "User": user_id,
            "Addresses": [ip + "/32"]}
    node.update(extra)
    return {"Node": node, "UserProfile": {"ID": user_id,
                                         "LoginName": "private@example.invalid"}}


class TailscaleIdentityTests(unittest.TestCase):
    def test_exact_node_user_and_ip_from_real_whois_shape(self):
        result = identity.verified_peer_from_whois(SOURCE, whois())
        self.assertEqual(result, pairing.PeerIdentity("nTestClient", "1042"))

    def test_reject_route_match_wrong_user_tagged_and_malformed(self):
        invalid = [
            whois(ip=ALT), whois(Addresses=[SOURCE + "/24"]),
            whois(Addresses=[], AllowedIPs=[SOURCE + "/32"]),
            whois(User=4444), whois(Tags=["tag:server"]),
            {"Node": whois()["Node"]},
            {"UserProfile": whois()["UserProfile"]},
            whois(node_id="node<script>"), whois(user_id=0, User=0),
        ]
        for item in invalid:
            with self.subTest(item=item):
                self.assertIsNone(identity.verified_peer_from_whois(SOURCE, item))
        for ip in ("127.0.0.1", "192.168.1.2", "8.8.8.8",
                   "100.100.100.100", "fd7a:115c:a1e0::5"):
            self.assertIsNone(identity.verified_peer_from_whois(ip, whois()))

    def test_whois_never_consults_client_provided_identity(self):
        calls = []
        def run(argv, **kw):
            calls.append(argv)
            return StubResult(whois())
        verified = identity.verify_tailscale_peer(SOURCE, runner=run)
        self.assertEqual(verified.user_id, "1042")
        self.assertEqual(calls, [["tailscale", "whois", "--json", SOURCE]])
        self.assertIsNone(identity.verify_tailscale_peer("192.168.0.3", runner=run))
        self.assertEqual(len(calls), 1)
        def fail(argv, **kw):
            return StubResult({"UserProfile": {"ID": 123}})
        self.assertIsNone(identity.verify_tailscale_peer(SOURCE, runner=fail))

    def test_own_bind_address_never_lan_or_wildcard(self):
        def run(argv, **kw):
            self.assertEqual(argv, ["tailscale", "status", "--json"])
            return StubResult({"BackendState": "Running",
                               "Self": {"TailscaleIPs": ["100.92.3.7",
                                          "fd7a:115c:a1e0::abcd"]}})
        self.assertEqual(identity.own_tailnet_ipv4(runner=run), "100.92.3.7")
        def no_tailscale(argv, **kw):
            return StubResult({"BackendState": "NeedsLogin",
                               "Self": {"TailscaleIPs": ["100.92.3.7"]}})
        with self.assertRaises(ValueError):
            identity.own_tailnet_ipv4(runner=no_tailscale)


class BrokerWireTests(unittest.TestCase):
    def setUp(self):
        # Dynamically loaded legacy regression tests must all share the same
        # production pairing module to preserve dataclass identities.
        module = sys.modules["now_pairing_requests"]
        self.queue = module.PairingRequests()
        self.alice = module.PeerIdentity("nTestClient", "1042")
        self.bob = module.PeerIdentity("nOtherClient", "2055")
        self.current_peer = self.alice
        self.directory = tempfile.TemporaryDirectory(prefix="now-broker-test-")
        self.owner = owner.OwnerControl(self.directory.name, self.queue)
        self.owner_thread = threading.Thread(
            target=self.owner.serve_forever,
            kwargs={"poll_interval": 0.01}, daemon=True)
        self.owner_thread.start()
        def authenticated(_source_ip):
            return self.current_peer
        self.http = broker.PairingHTTPServer(
            ("127.0.0.1", 0), broker.make_handler(self.queue, verify=authenticated))
        self.http_thread = threading.Thread(
            target=self.http.serve_forever,
            kwargs={"poll_interval": 0.01}, daemon=True)
        self.http_thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.http_thread.join(timeout=2)
        self.owner.shutdown()
        self.owner.server_close()
        self.owner_thread.join(timeout=2)
        self.directory.cleanup()

    def send(self, method, path=broker.REQUEST_ROUTE, payload=None, headers=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.http.server_port, timeout=3)
        try:
            data = None if payload is None else json.dumps(payload).encode()
            head = {} if headers is None else dict(headers)
            if payload is not None:
                head.setdefault("Content-Type", "application/json")
            conn.request(method, path, body=data, headers=head)
            response = conn.getresponse()
            return response.status, json.loads(response.read()), {
                "cors": response.getheader("Access-Control-Allow-Origin"),
                "cache": response.getheader("Cache-Control"),
            }
        finally:
            conn.close()

    def test_full_client_request_owner_approve_then_client_status(self):
        status, payload, heads = self.send("POST", payload={"backend": "sunshine"})
        self.assertEqual(status, 202)
        self.assertEqual(payload["owner_status"], "pending")
        self.assertFalse(payload["moonlight_paired"])
        self.assertIsNone(heads["cors"])
        self.assertEqual(heads["cache"], "no-store")
        request_id = payload["request_id"]
        pending = owner.owner_command(self.directory.name, "list")["pending"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["device_id"], "nTestClient")
        self.assertEqual(pending[0]["account_id"], "1042")
        self.assertTrue(owner.owner_command(
            self.directory.name, "approve", request_id)["ok"])
        status, payload, _ = self.send("GET", broker.REQUEST_ROUTE + "/" + request_id)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"owner_status": "approved",
                                   "moonlight_paired": False})
        grant = self.queue.take_grant_for_adapter(self.alice, request_id, "sunshine")
        self.assertIsNotNone(grant)
        self.assertIsNone(self.queue.take_grant_for_adapter(
            self.alice, request_id, "sunshine"))

    def test_other_identity_cannot_view_or_cancel_request(self):
        _, body, _ = self.send("POST", payload={"backend": "wolf"})
        path = broker.REQUEST_ROUTE + "/" + body["request_id"]
        self.current_peer = self.bob
        self.assertEqual(self.send("GET", path)[0], 404)
        self.assertEqual(self.send("DELETE", path)[0], 404)
        self.current_peer = self.alice
        self.assertEqual(self.send("GET", path)[1]["owner_status"], "pending")
        self.assertEqual(self.send("DELETE", path)[1], {
            "cancelled": True, "moonlight_paired": False})
        self.assertEqual(self.send("GET", path)[0], 404)

    def test_rejected_requests_cannot_be_cancelled_and_retried(self):
        _, body, _ = self.send("POST", payload={"backend": "wolf"})
        key = body["request_id"]
        self.assertTrue(owner.owner_command(self.directory.name, "deny", key)["ok"])
        path = broker.REQUEST_ROUTE + "/" + key
        self.assertEqual(self.send("GET", path)[1]["owner_status"], "denied")
        self.assertEqual(self.send("DELETE", path)[0], 404)
        again = self.send("POST", payload={"backend": "wolf"})
        self.assertEqual(again[0], 202)
        self.assertEqual(again[1]["request_id"], key)
        self.assertEqual(again[1]["owner_status"], "denied")
        self.assertFalse(owner.owner_command(self.directory.name, "approve", key)["ok"])

    def test_no_client_owner_approval_or_backend_control_routes(self):
        _, body, _ = self.send("POST", payload={"backend": "sunshine"})
        key = body["request_id"]
        for method, path in [
            ("POST", "/v1/pairing/approve"), ("POST", "/v1/owner/approve"),
            ("POST", "/v1/admin/restart"), ("GET", "/v1/owner/pending"),
            ("PUT", broker.REQUEST_ROUTE), ("GET", "/v1/discover"),
        ]:
            with self.subTest(method=method, path=path):
                self.assertNotEqual(self.send(method, path)[0], 200)
        self.assertEqual(self.queue.status_for_peer(self.alice, key), "pending")

    def test_forged_user_device_headers_and_body_never_change_identity(self):
        for body in [
            {"backend": "wolf", "user_id": "admin"},
            {"backend": "wolf", "node_id": "other"},
            {"backend": "wolf", "owner": True},
        ]:
            self.assertEqual(self.send("POST", payload=body)[0], 400)
        status, payload, _ = self.send("POST", payload={"backend": "wolf"},
                headers={"X-Tailscale-User": "admin", "X-Tailscale-Node": "admin"})
        self.assertEqual(status, 202)
        self.assertEqual(self.queue.owner_pending()[0].peer, self.alice)
        self.assertEqual(payload["owner_status"], "pending")

    def test_unverified_peer_is_denied_every_time(self):
        self.current_peer = None
        self.assertEqual(self.send("POST", payload={"backend": "wolf"})[0], 403)
        self.assertEqual(self.send("GET", broker.REQUEST_ROUTE + "/" + "a"*32)[0], 403)
        self.assertEqual(self.send("DELETE", broker.REQUEST_ROUTE + "/" + "a"*32)[0], 403)
        self.assertEqual(self.queue.owner_pending(), [])

    def test_body_size_content_type_and_browser_origin_rejected(self):
        self.assertEqual(self.send("POST", payload={"backend": "wolf"},
                                   headers={"Origin": "https://attacker.invalid"})[0], 403)
        self.assertEqual(self.send("POST", payload={"backend": "wolf"},
                                   headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.send("POST", payload={"backend": "wolf", "padding": "x"*200})[0], 413)
        self.assertEqual(self.queue.owner_pending(), [])

    def test_repeated_submissions_are_idempotent(self):
        a = self.send("POST", payload={"backend": "wolf"})
        b = self.send("POST", payload={"backend": "wolf"})
        self.assertEqual(a[1]["request_id"], b[1]["request_id"])
        self.assertEqual(len(owner.owner_command(self.directory.name, "list")["pending"]), 1)
        self.assertEqual(self.send("POST", payload={"backend": "sunshine"})[0], 409)

    def test_owner_command_is_not_served_over_http(self):
        self.assertEqual(self.send("POST", "/v1/pairing/requests",
                                   payload={"action": "approve", "request_id": "a"*32})[0], 400)
        self.assertFalse(os.path.exists(os.path.join(self.directory.name, "web-admin.sock")))


if __name__ == "__main__":
    unittest.main()
