"""Private phone QR HTTP acceptance: real staging/proof/approval, fake Tailnet/Wolf.

This is an offline test. The fake socket peer is reassigned by the test
handler; no actual Tailscale, SSH server, browser, Docker or host is contacted.
"""
import base64
from http.server import HTTPServer
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "src"), str(ROOT / "tests")]

from owner_access import OwnerStore
from owner_enrollment import approve_request
from moonlight_cert_identity import message, wolf_certificate_client_id
from owner_qr_approval import PAGE_PREFIX
from tailnet_enrollment import (make_handler, ROUTE, PROOF_ROUTE, REVIEW_ROUTE,
                                APPROVE_ROUTE)
from test_moonlight_cert_identity import credentials
from test_owner_enrollment import public_key
from test_owner_lobby import fixtures


class PhoneQrHttpEndToEnd(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.store = OwnerStore(str(self.state))
        with self.store.locked() as fd:
            self.store.write(fd, fixtures()[0])
        self.auth = self.root / "authorized_keys"
        self.original = "ssh-ed25519 AAAAowner existing-admin\n"
        self.auth.write_text(self.original)
        self.auth.chmod(0o600)
        self.broker = ROOT / "server/owner_games_ssh.py"

        self.cert, self.key = credentials()
        self.client_id = wolf_certificate_client_id(self.cert.encode("utf-8"))
        self.wolfconf = self.root / "wolf.toml"
        self.wolfconf.write_text(
            "paired_clients=[{client_cert=" + json.dumps(self.cert) +
            ', app_state_folder="different-from-client-id"}]\n')
        self.wolfconf.chmod(0o600)

        def wolf(method, path):
            self.assertEqual((method, path), ("GET", "/api/v1/clients"))
            return {"success": True, "clients": [
                {"client_id": self.client_id,
                 "app_state_folder": "different-from-client-id"}]}
        self.wolf = wolf
        self.peer = {"ip": "100.72.15.27", "node": "new-client"}
        self.pinned_phone = "trusted-iphone"

        def verify(source, owner_id):
            if source != self.peer["ip"] or owner_id != "1042":
                return None
            return owner_id, self.peer["node"]

        def approve(state, request_id, code, client_id, *,
                    wolf_api, approval, wolf_config):
            return approve_request(
                state, request_id, code, client_id,
                confirmed=approval, wolf_api=wolf_api,
                wolf_config=wolf_config, auth_path=self.auth,
                broker_path=self.broker)

        base_handler = make_handler(
            "1042", str(self.state), verify=verify,
            wolf_factory=lambda: self.wolf, approve=approve,
            wolf_config=str(self.wolfconf), remote_approve_enabled=True,
            approver_node_id=self.pinned_phone)

        peer = self.peer
        class SimulatedTailnetPeer(base_handler):
            def setup(self):
                super().setup()
                # Inject a synthetic test-only peer, not an HTTP header.
                self.client_address = (peer["ip"], self.client_address[1])

        self.server = HTTPServer(("127.0.0.1", 0), SimulatedTailnetPeer)
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01},
                                       daemon=True)
        self.worker.start()
        self.addCleanup(self.close_server)
        self.public_key = public_key(b"q")

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def call(self, method, route, data=None):
        conn = http.client.HTTPConnection("127.0.0.1",
                                          self.server.server_port, timeout=3)
        try:
            body = json.dumps(data) if data is not None else None
            headers = {"Content-Type": "application/json"} if body else {}
            conn.request(method, route, body, headers)
            reply = conn.getresponse()
            raw = reply.read()
            if "application/json" in reply.getheader("Content-Type", ""):
                return reply.status, json.loads(raw)
            return reply.status, raw.decode("utf-8")
        finally:
            conn.close()

    def staged(self):
        status, result = self.call("POST", ROUTE,
                                   {"version": 1, "public_key": self.public_key})
        self.assertEqual(status, 202, result)
        self.assertEqual(result["status"], "pending")
        self.assertIs(result.get("phone_approval_available"), True)
        return result

    def signed_proof(self, request):
        key = serialization.load_pem_private_key(self.key.encode("ascii"),
                                                 password=None)
        signature = key.sign(message(request["request_id"], request["code"],
                                     request["fingerprint"]),
                             padding.PKCS1v15(), hashes.SHA256())
        return {"request_id": request["request_id"],
                "certificate_pem": self.cert,
                "signature_b64": base64.b64encode(signature).decode("ascii")}

    def verify_no_grant(self):
        self.assertEqual(self.auth.read_text(), self.original)
        with self.store.locked() as fd:
            self.assertEqual(len(self.store.read(fd)["devices"]), 1)

    def test_client_proves_identity_phone_reviews_and_grants_once(self):
        request = self.staged()
        rid = request["request_id"]
        self.assertEqual(self.call("POST", PROOF_ROUTE,
                                   self.signed_proof(request)),
                         (200, {"success": True, "status": "proof_recorded"}))
        self.verify_no_grant()

        # Even the device holding the enrolled Moonlight certificate cannot
        # impersonate the separately pinned owner phone.
        self.assertEqual(self.call("GET", PAGE_PREFIX + rid)[0], 403)
        self.assertEqual(self.call("GET", REVIEW_ROUTE + "/" + rid)[0], 403)
        self.assertEqual(self.call("POST", APPROVE_ROUTE,
                {"request_id": rid, "code": request["code"],
                 "wolf_client_id": self.client_id, "confirmed": True})[0], 403)
        self.verify_no_grant()

        # The trusted phone authorizes exactly the previously staged client.
        self.peer.update(ip="100.72.15.28", node=self.pinned_phone)
        status, page = self.call("GET", PAGE_PREFIX + rid)
        self.assertEqual(status, 200)
        self.assertIn(request["fingerprint"], page)
        self.assertNotIn(request["code"], page)
        self.assertEqual(self.call("GET", REVIEW_ROUTE + "/" + rid),
                         (200, {"success": True,
                                "wolf_client_id": self.client_id}))
        response = self.call("POST", APPROVE_ROUTE,
            {"request_id": rid, "code": request["code"],
             "wolf_client_id": self.client_id, "confirmed": True})
        self.assertEqual(response,
                         (200, {"success": True, "status": "approved"}))
        self.assertIn("--client-id " + self.client_id, self.auth.read_text())
        self.assertIn(self.original, self.auth.read_text())
        # A captured phone approval cannot be replayed.
        self.assertEqual(self.call("POST", APPROVE_ROUTE,
            {"request_id": rid, "code": request["code"],
             "wolf_client_id": self.client_id, "confirmed": True})[0], 400)

    def test_proof_wrong_source_wrong_signature_and_denied_unattested_qr(self):
        request = self.staged()
        rid = request["request_id"]
        self.peer["ip"] = "100.72.15.29"
        self.assertEqual(self.call("POST", PROOF_ROUTE,
                         self.signed_proof(request))[0], 400)
        self.peer["ip"] = "100.72.15.27"
        forged = self.signed_proof(request)
        forged["signature_b64"] = base64.b64encode(b"z"*256).decode("ascii")
        self.assertEqual(self.call("POST", PROOF_ROUTE, forged)[0], 400)
        self.peer.update(ip="100.72.15.28", node=self.pinned_phone)
        self.assertEqual(self.call("GET", REVIEW_ROUTE + "/" + rid)[0], 409)
        self.assertEqual(self.call("POST", APPROVE_ROUTE,
            {"request_id": rid, "code": request["code"],
             "wolf_client_id": self.client_id, "confirmed": True})[0], 400)
        self.verify_no_grant()

    def test_wrong_phone_and_no_approval_node_fail_closed(self):
        request = self.staged()
        self.call("POST", PROOF_ROUTE, self.signed_proof(request))
        self.peer.update(ip="100.72.15.28", node="different-phone")
        self.assertEqual(self.call("GET", PAGE_PREFIX + request["request_id"])[0],
                         403)
        self.assertEqual(self.call("GET", REVIEW_ROUTE + "/" +
                                   request["request_id"])[0], 403)
        self.assertEqual(self.call("POST", APPROVE_ROUTE,
            {"request_id": request["request_id"], "code": request["code"],
             "wolf_client_id": self.client_id, "confirmed": True})[0], 403)
        self.verify_no_grant()


if __name__ == "__main__":
    unittest.main()
