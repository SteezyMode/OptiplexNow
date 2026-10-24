"""Remote owner approval tests; all host networking, Wolf and SSH are faked."""
import http.client
from http.server import HTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "server")]
from owner_access import PolicyError
from tailnet_wolf_review import (single_active_wolf_ui,
                                 approve_reviewed_owner_request)
from tailnet_enrollment import (make_handler, REVIEW_ROUTE, APPROVE_ROUTE)


class FakeWolf:
    def __init__(self):
        self.clients = {"success": True, "clients": [
            {"client_id": "1200", "app_state_folder": "1200"}]}
        self.apps = {"success": True, "apps": [
            {"id": "ui-app", "title": "Wolf UI"},
            {"id": "steam-app", "title": "Steam"}]}
        self.sessions = {"success": True, "sessions": [
            {"client_id": "1200", "app_id": "ui-app",
             "aes_key": "NEVER-IN-RESPONSE", "aes_iv": "secret"}]}
        self.lobbies = {"success": True, "lobbies": []}
        self.calls = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path))
        assert method == "GET" and body is None
        return {
            "/api/v1/clients": self.clients,
            "/api/v1/apps": self.apps,
            "/api/v1/sessions": self.sessions,
            "/api/v1/lobbies": self.lobbies}[path]


class WolfReviewTests(unittest.TestCase):
    def setUp(self):
        self.wolf = FakeWolf()

    def test_only_one_live_pair_and_wolf_ui_are_eligible(self):
        self.assertEqual(single_active_wolf_ui(self.wolf), "1200")
        self.assertEqual(len(self.wolf.calls), 4)
        self.assertTrue(all(method == "GET" for method, _ in self.wolf.calls))

    def test_ambiguous_direct_steam_or_unpaired_fail_closed(self):
        cases = [
            ("multiple sessions", lambda: self.wolf.sessions["sessions"].append(
                {"client_id": "1201", "app_id": "ui-app"})),
            ("none", lambda: self.wolf.sessions["sessions"].clear()),
            ("direct Steam", lambda: self.wolf.sessions["sessions"][0].update(
                {"app_id": "steam-app"})),
            ("not paired", lambda: self.wolf.sessions["sessions"][0].update(
                {"client_id": "1201"})),
            ("Wolf UI duplicate", lambda: self.wolf.apps["apps"].append(
                {"title": "Wolf UI", "id": "other-ui"})),
            ("active lobby", lambda: self.wolf.lobbies["lobbies"].append(
                {"id": "existing"})),
            ("bad inventory", lambda: self.wolf.sessions.update(
                {"success": False})),
        ]
        for title, mutate in cases:
            with self.subTest(case=title):
                self.wolf = FakeWolf()
                mutate()
                with self.assertRaises(PolicyError):
                    single_active_wolf_ui(self.wolf)

    def test_review_does_not_grant_without_explicit_owner_confirmation(self):
        with patch("owner_enrollment.approve_request") as approver:
            with self.assertRaises(PolicyError):
                approve_reviewed_owner_request(
                    "/state", "a"*32, "123456", "1200",
                    wolf_api=self.wolf, approval=False)
            approver.assert_not_called()
            with self.assertRaises(PolicyError):
                approve_reviewed_owner_request(
                    "/state", "a"*32, "123456", "1201",
                    wolf_api=self.wolf, approval=True)
            approver.assert_not_called()
            approver.return_value = {"success": True, "status": "approved"}
            result = approve_reviewed_owner_request(
                "/state", "a"*32, "123456", "1200",
                wolf_api=self.wolf, approval=True)
            self.assertEqual(result["status"], "approved")
            self.assertEqual(approver.call_args.args[:4],
                             ("/state", "a"*32, "123456", "1200"))
            self.assertIs(approver.call_args.kwargs["confirmed"], True)


class ApprovalHttpTests(unittest.TestCase):
    def setUp(self):
        self.authorized = True
        self.wolf = FakeWolf()
        self.approvals = []
        self.staged = []
        def verify(ip, owner):
            return ("1042", "node123") if self.authorized and owner == "1042" else None
        def stage(path, key):
            self.staged.append(key)
            return {"success": True, "status": "pending",
                    "request_id": "a"*32, "code": "123456",
                    "fingerprint": "b"*20}
        def approve(path, req, code, selected, *, wolf_api, approval):
            self.approvals.append((path, req, code, selected, approval))
            return {"success": True}
        self.handler = make_handler("1042", "/private/state", verify=verify,
                                    stage=stage, wolf_factory=lambda: self.wolf,
                                    approve=approve,
                                    remote_approve_enabled=True)
        self.server = HTTPServer(("127.0.0.1", 0), self.handler)
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def call(self, method, path, payload=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port,
                                          timeout=2)
        try:
            body = (json.dumps(payload) if payload is not None else None)
            hs = {"Content-Type": "application/json"}
            if headers:
                hs.update(headers)
            conn.request(method, path, body=body, headers=hs)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    def approval(self, **kwargs):
        return {"request_id": "a"*32, "code": "123456",
                "wolf_client_id": "1200", "confirmed": True, **kwargs}

    def test_owner_can_review_then_explicitly_approve_without_host_screen(self):
        status, body = self.call("GET", REVIEW_ROUTE)
        self.assertEqual(status, 200)
        self.assertEqual(body, {"success": True, "wolf_client_id": "1200"})
        self.assertNotIn("NEVER-IN-RESPONSE", str(body))
        self.assertEqual(self.approvals, [])
        status, body = self.call("POST", APPROVE_ROUTE, self.approval())
        self.assertEqual(status, 200)
        self.assertEqual(body, {"success": True, "status": "approved"})
        self.assertEqual(self.approvals,
                         [("/private/state", "a"*32, "123456", "1200", True)])

    def test_denies_guest_false_confirmation_browser_and_other_routes(self):
        self.authorized = False
        self.assertEqual(self.call("GET", REVIEW_ROUTE)[0], 403)
        self.assertEqual(self.call("POST", APPROVE_ROUTE, self.approval())[0], 403)
        self.authorized = True
        for bad in [
            {"request_id": "a"*32, "code": "123456",
             "wolf_client_id": "1200", "confirmed": False},
            {"request_id": "a"*32, "code": "123456",
             "wolf_client_id": "1200", "confirmed": "true"},
            {"request_id": "a"*32, "code": "123456",
             "wolf_client_id": "1200", "confirmed": True, "command": "ssh"},
        ]:
            self.assertEqual(self.call("POST", APPROVE_ROUTE, bad)[0], 400)
        self.assertEqual(self.call("POST", APPROVE_ROUTE, self.approval(),
                                   {"Origin": "https://example.invalid"})[0], 403)
        self.assertEqual(self.call("POST", "/v1/owner/exec", self.approval())[0], 404)
        self.assertEqual(self.approvals, [])

    def test_missing_unique_wolf_ui_prevents_confirmation(self):
        self.wolf.sessions["sessions"] = []
        status, body = self.call("GET", REVIEW_ROUTE)
        self.assertEqual(status, 409)
        self.assertNotIn("wolf_client_id", body)
        self.assertEqual(self.approvals, [])

    def test_disabled_listener_cannot_remotely_grant(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
        self.server = HTTPServer(("127.0.0.1", 0),
                                  make_handler("1042", "/private/state",
                                               verify=lambda *_: ("1042", "n123"),
                                               stage=lambda *_: {},
                                               wolf_factory=lambda: self.wolf))
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01},
                                       daemon=True)
        self.worker.start()
        self.assertEqual(self.call("GET", REVIEW_ROUTE)[0], 403)
        self.assertEqual(self.call("POST", APPROVE_ROUTE, self.approval())[0], 403)


if __name__ == "__main__":
    unittest.main()
