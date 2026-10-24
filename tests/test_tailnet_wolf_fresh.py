"""Fresh Wolf pending request guard: orphaned requests are never selected.

Offline tests; no real Wolf, Docker, Tailnet or privileged SSH access.
"""
import http.client
from http.server import HTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "server")]
from owner_access import PolicyError
from tailnet_wolf_fresh import FreshPairWindow
from tailnet_enrollment import (
    make_handler, PAIR_PREPARE_ROUTE, PAIR_PENDING_ROUTE, PAIR_APPROVE_ROUTE)

spec = importlib.util.spec_from_file_location(
    "owner_wolf_client_fresh", ROOT / "src/wolf-pair-client.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

SOURCE = "100.73.42.22"
HOST = "100.121.156.34"
PEER = ("3905340949246616", "node-A")
OLD = {"client_ip": SOURCE, "pair_secret": "orphan-secret"}
NEW = {"client_ip": SOURCE, "pair_secret": "new-client-secret"}


class Wolf:
    def __init__(self, entries=None):
        self.entries = list(entries or [])
        self.approved = []

    def __call__(self, method, path, body=None):
        if (method, path) == ("GET", "/api/v1/pair/pending"):
            return {"success": True, "requests": list(self.entries)}
        if (method, path) == ("POST", "/api/v1/pair/client"):
            self.approved.append(dict(body))
            return {"success": True}
        raise AssertionError("Unallowlisted Wolf operation")


class FreshPairTests(unittest.TestCase):
    def setUp(self):
        self.clock = 100
        self.guard = FreshPairWindow(clock=lambda: self.clock)
        self.wolf = Wolf([OLD])

    def test_orphaned_pending_ignored_and_new_client_selected(self):
        self.assertEqual(self.guard.prepare(PEER, SOURCE, call_api=self.wolf),
                         {"success": True, "status": "prepared"})
        self.assertEqual(self.guard.pending(
            PEER, SOURCE, call_api=self.wolf)["clients"], [])
        self.wolf.entries.extend([NEW])
        result = self.guard.pending(PEER, SOURCE, call_api=self.wolf)
        self.assertEqual(result, {"success": True, "clients": [
            {"index": 2, "client_ip": SOURCE}]})
        self.assertNotIn("orphan-secret", str(result))
        self.assertNotIn("new-client-secret", str(result))
        self.assertEqual(self.guard.pair(PEER, SOURCE, {
            "index": 2, "client_ip": SOURCE, "pin": "0419"},
            call_api=self.wolf), {"success": True})
        self.assertEqual(self.wolf.approved, [{
            "pair_secret": "new-client-secret", "pin": "0419"}])
        with self.assertRaises(PolicyError):
            self.guard.pending(PEER, SOURCE, call_api=self.wolf)

    def test_unprepared_and_old_pending_cannot_be_approved(self):
        with self.assertRaises(PolicyError):
            self.guard.pending(PEER, SOURCE, call_api=self.wolf)
        self.guard.prepare(PEER, SOURCE, call_api=self.wolf)
        with self.assertRaises(PolicyError):
            self.guard.pair(PEER, SOURCE, {
                "index": 1, "client_ip": SOURCE, "pin": "1234"},
                call_api=self.wolf)
        self.assertEqual(self.wolf.approved, [])

    def test_wrong_node_source_or_expiration_rejected(self):
        self.guard.prepare(PEER, SOURCE, call_api=self.wolf)
        self.wolf.entries.append(NEW)
        for who, ip in [
            ((PEER[0], "different-node"), SOURCE),
            (("999", PEER[1]), SOURCE),
            (PEER, "100.73.42.23"),
        ]:
            with self.subTest(identity=who, address=ip), self.assertRaises(PolicyError):
                self.guard.pending(who, ip, call_api=self.wolf)
        self.clock += 301
        with self.assertRaises(PolicyError):
            self.guard.pair(PEER, SOURCE, {
                "index": 2, "client_ip": SOURCE, "pin": "1234"},
                call_api=self.wolf)
        self.assertEqual(self.wolf.approved, [])

    def test_multiple_new_requests_or_index_changed_refuses(self):
        self.guard.prepare(PEER, SOURCE, call_api=self.wolf)
        self.wolf.entries += [NEW, {"client_ip": SOURCE, "pair_secret": "another-new"}]
        with self.assertRaises(PolicyError):
            self.guard.pending(PEER, SOURCE, call_api=self.wolf)
        self.wolf.entries.pop()
        with self.assertRaises(PolicyError):
            self.guard.pair(PEER, SOURCE, {
                "index": 1, "client_ip": SOURCE, "pin": "1234"},
                call_api=self.wolf)
        self.assertEqual(self.wolf.approved, [])


class FreshPairServerTests(unittest.TestCase):
    def setUp(self):
        self.wolf = Wolf([{"client_ip": "127.0.0.1",
                           "pair_secret": "orphan-secret"}])
        self.authorized = True
        self.server = HTTPServer(("127.0.0.1", 0), make_handler(
            "3905340949246616", "/isolated/test",
            verify=lambda *_: PEER if self.authorized else None,
            pair_api=self.wolf, owner_pair_enabled=True,
            require_fresh_pairing=True))
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.mock_ip = patch("tailnet_wolf_fresh.tailnet_ipv4", side_effect=lambda x: x)
        self.mock_ip.start()

    def tearDown(self):
        self.mock_ip.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def req(self, method, path, payload=None):
        con = http.client.HTTPConnection("127.0.0.1",
                                         self.server.server_port, timeout=4)
        body = json.dumps(payload).encode() if payload is not None else None
        try:
            con.request(method, path, body=body,
                        headers={"Content-Type": "application/json"})
            resp = con.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            con.close()

    def test_prepare_before_new_moonlight_required_and_stale_ignored(self):
        self.assertEqual(self.req("GET", PAIR_PENDING_ROUTE)[0], 409)
        self.assertEqual(self.req("POST", PAIR_PREPARE_ROUTE, {}),
                         (200, {"success": True, "status": "prepared"}))
        self.assertEqual(self.req("GET", PAIR_PENDING_ROUTE),
                         (200, {"success": True, "clients": []}))
        self.wolf.entries.append({"client_ip": "127.0.0.1",
                                  "pair_secret": "fresh"})
        self.assertEqual(self.req("GET", PAIR_PENDING_ROUTE),
                         (200, {"success": True, "clients": [
                             {"index": 2, "client_ip": "127.0.0.1"}]}))
        self.assertEqual(self.req("POST", PAIR_APPROVE_ROUTE, {
            "index": 1, "client_ip": "127.0.0.1", "pin": "0419"})[0], 400)
        self.assertEqual(self.wolf.approved, [])
        self.assertEqual(self.req("POST", PAIR_APPROVE_ROUTE, {
            "index": 2, "client_ip": "127.0.0.1", "pin": "0419"}),
                         (200, {"success": True}))
        self.assertEqual(self.wolf.approved[-1]["pair_secret"], "fresh")
        self.assertEqual(self.req("GET", PAIR_PENDING_ROUTE)[0], 409)

    def test_non_owner_cannot_prepare_or_pair(self):
        self.authorized = False
        self.assertEqual(self.req("POST", PAIR_PREPARE_ROUTE, {})[0], 403)
        self.assertEqual(self.req("GET", PAIR_PENDING_ROUTE)[0], 403)
        self.assertEqual(self.req("POST", PAIR_APPROVE_ROUTE, {
            "index": 1, "client_ip": "127.0.0.1", "pin": "1234"})[0], 403)
        self.assertEqual(self.wolf.approved, [])


class FreshPairClientTests(unittest.TestCase):
    def test_prepare_and_correct_source_not_confused_with_host(self):
        routes = []
        class Conn:
            def __init__(self, host, port, timeout):
                self.path = None
                self.host = host
                self.port = port
            def request(self, method, path, body=None, headers=None):
                routes.append((method, path, json.loads(body) if body else None))
                self.path = path
            def getresponse(self):
                path = self.path
                class Reply:
                    status = 200
                    def read(self, n):
                        return json.dumps({"success": True, "status": "prepared"}
                                          if path == PAIR_PREPARE_ROUTE else
                                          {"success": True}).encode()
                return Reply()
            def close(self):
                pass
        self.assertEqual(client.invoke_tailnet(
            HOST, "prepare", connection=Conn)["status"], "prepared")
        self.assertEqual(routes[-1], ("POST", PAIR_PREPARE_ROUTE, {}))
        self.assertEqual(client.invoke_tailnet(
            HOST, "pair", {
                "index": 2, "client_ip": SOURCE, "pin": "0419"},
            connection=Conn), {"success": True})
        self.assertEqual(routes[-1][1], PAIR_APPROVE_ROUTE)
        with self.assertRaises(ValueError):
            client.invoke_tailnet(
                HOST, "pair", {
                    "index": 1, "client_ip": "192.168.1.1", "pin": "1234"},
                connection=Conn)


if __name__ == "__main__":
    unittest.main()
