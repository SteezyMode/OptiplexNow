"""Offline negative cases for same-node, fresh Wolf pairing owner review.

No real Tailnet, Wolf daemon, SSH server, authorizations or Docker processes.
"""
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
from tailnet_pair_witness import PairingWitness
from tailnet_enrollment import (make_handler, ROUTE, APPROVE_ROUTE,
                               PAIR_APPROVE_ROUTE, PAIRED_CANDIDATE_ROUTE)

SOURCE = "100.73.42.22"
IDENTITY = ("3905340949246616", "node-1")
REQ = "a"*32
CLIENT = "5114970000005922575"
OLD = "12009214108445860267"


class Wolf:
    def __init__(self):
        self.identities = [OLD]
        self.calls = []
        # An existing disconnected Steam lobby must not block this flow.
        self.steam_lobby = {"id": "preserved", "name": "Steam"}

    def __call__(self, method, path, body=None):
        self.calls.append((method, path))
        if (method, path) != ("GET", "/api/v1/clients"):
            raise AssertionError("This witness must read Wolf clients only")
        return {"success": True, "clients": [
            {"client_id": client, "app_state_folder": client}
            for client in self.identities]}


class WitnessTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.clock = lambda: self.now
        self.w = PairingWitness(clock=self.clock)
        self.wolf = Wolf()

    def stage_pair(self):
        self.w.staged(IDENTITY, SOURCE, REQ)
        baseline = frozenset(self.wolf.identities)
        self.w.paired(IDENTITY, SOURCE, baseline)
        self.wolf.identities.append(CLIENT)

    def test_unique_added_id_with_existing_lobby(self):
        self.stage_pair()
        self.assertEqual(self.w.candidate(
            IDENTITY, SOURCE, REQ, self.wolf), CLIENT)
        self.assertEqual(self.wolf.steam_lobby["name"], "Steam")
        self.assertEqual(self.wolf.calls, [("GET", "/api/v1/clients")])

    def test_no_stage_wrong_node_wrong_source_and_replay_rejected(self):
        self.w.paired(IDENTITY, SOURCE, frozenset((OLD,)))
        self.wolf.identities.append(CLIENT)
        with self.assertRaises(PolicyError):
            self.w.candidate(IDENTITY, SOURCE, REQ, self.wolf)
        self.w.staged(IDENTITY, SOURCE, REQ)
        for who, source in [
            (("3905340949246616", "different"), SOURCE),
            (IDENTITY, "100.73.42.23"),
            (("99999", "node-1"), SOURCE),
        ]:
            with self.subTest(peer=who, address=source), self.assertRaises(PolicyError):
                self.w.candidate(who, source, REQ, self.wolf)
        self.w.consumed(IDENTITY, SOURCE, REQ)
        with self.assertRaises(PolicyError):
            self.w.candidate(IDENTITY, SOURCE, REQ, self.wolf)

    def test_stale_or_ambiguous_wolf_inventory_fails_closed(self):
        self.stage_pair()
        self.wolf.identities.append("2222222222")
        with self.assertRaisesRegex(PolicyError, "not uniquely"):
            self.w.candidate(IDENTITY, SOURCE, REQ, self.wolf)
        self.wolf.identities.remove("2222222222")
        self.now += 601
        with self.assertRaises(PolicyError):
            self.w.candidate(IDENTITY, SOURCE, REQ, self.wolf)

    def test_already_paired_or_no_new_client_is_not_a_witness(self):
        self.w.staged(IDENTITY, SOURCE, REQ)
        self.w.paired(IDENTITY, SOURCE, frozenset((OLD, CLIENT)))
        self.wolf.identities.append(CLIENT)
        with self.assertRaises(PolicyError):
            self.w.candidate(IDENTITY, SOURCE, REQ, self.wolf)

    def test_no_anonymous_client_claim_can_create_witness(self):
        with self.assertRaises(PolicyError):
            self.w.staged(IDENTITY, "192.168.0.1", REQ)
        with self.assertRaises(PolicyError):
            self.w.paired(IDENTITY, "1.2.3.4", frozenset((OLD,)))


class HttpPairEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.wolf = Wolf()
        self.approved = []
        self.owner = IDENTITY
        self.pair_calls = []
        self.witness = PairingWitness()

        def stage(state, key):
            return {"success": True, "status": "pending",
                    "request_id": REQ, "code": "123456",
                    "fingerprint": "f"*20}

        def pair(method, path, body=None):
            self.pair_calls.append((method, path))
            if (method, path) == ("GET", "/api/v1/pair/pending"):
                return {"success": True, "requests": [{
                    "client_ip": "127.0.0.1",
                    "pair_secret": "private-wolf-secret"}]}
            if (method, path) == ("POST", "/api/v1/pair/client"):
                self.wolf.identities.append(CLIENT)
                return {"success": True}
            raise AssertionError("Unexpected Wolf operation")

        def commit(state, request_id, code, client_id, *, confirmed, wolf_api):
            self.approved.append((request_id, code, client_id, confirmed))
            return {"success": True, "status": "approved"}

        self.handler = make_handler(IDENTITY[0], "/safe/pilot",
            verify=lambda ip, owner: self.owner,
            wolf_factory=lambda: self.wolf,
            stage=stage, pair_api=pair, commit=commit,
            witness=self.witness,
            remote_approve_enabled=True, owner_pair_enabled=True)
        self.server = HTTPServer(("127.0.0.1", 0), self.handler)
        self.worker = threading.Thread(target=self.server.serve_forever,
            kwargs={"poll_interval": .01}, daemon=True)
        self.worker.start()
        self.patch_peer = patch("tailnet_pair_witness.tailnet_ipv4",
                                side_effect=lambda x: x)
        self.patch_pending = patch("tailnet_wolf_pair.tailnet_ipv4",
                                   side_effect=lambda x: x)
        self.patch_peer.start()
        self.patch_pending.start()

    def tearDown(self):
        self.patch_pending.stop()
        self.patch_peer.stop()
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def call(self, path, obj):
        con = http.client.HTTPConnection("127.0.0.1", self.server.server_port,
                                          timeout=3)
        try:
            con.request("POST", path, body=json.dumps(obj),
                        headers={"Content-Type": "application/json"})
            resp = con.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            con.close()

    def stage(self):
        return self.call(ROUTE, {"version": 1, "public_key": "mock-public-key"})

    def pair(self):
        return self.call(PAIR_APPROVE_ROUTE, {
            "index": 1, "client_ip": "127.0.0.1", "pin": "1234"})

    def candidate(self):
        return self.call(PAIRED_CANDIDATE_ROUTE, {"request_id": REQ})

    def confirm(self, client=CLIENT, code="123456"):
        return self.call(APPROVE_ROUTE, {
            "request_id": REQ, "code": code, "wolf_client_id": client,
            "confirmed": True, "source": "recent_pair"})

    def test_staged_same_node_pairing_can_be_explicitly_granted_while_steam_runs(self):
        self.assertEqual(self.stage()[0], 202)
        self.assertEqual(self.pair()[0], 200)
        self.assertEqual(self.candidate(), (200, {
            "success": True, "wolf_client_id": CLIENT}))
        self.assertEqual(self.approved, [])
        self.assertEqual(self.confirm(),
                         (200, {"success": True, "status": "approved"}))
        self.assertEqual(self.approved,
                         [(REQ, "123456", CLIENT, True)])
        self.assertEqual(self.wolf.steam_lobby["id"], "preserved")
        self.assertEqual(self.wolf.calls, [
            ("GET", "/api/v1/clients"),
            ("GET", "/api/v1/clients"),
            ("GET", "/api/v1/clients")])
        self.assertEqual(self.candidate()[0], 400)

    def test_cannot_approve_with_unwitnessed_key_or_other_client(self):
        self.assertEqual(self.candidate()[0], 400)
        self.assertEqual(self.confirm()[0], 400)
        self.assertEqual(self.stage()[0], 202)
        self.assertEqual(self.confirm()[0], 400)
        self.assertEqual(self.pair()[0], 200)
        self.assertEqual(self.confirm(client=OLD)[0], 400)
        self.assertEqual(self.approved, [])

    def test_wrong_node_denied_even_with_valid_staged_request(self):
        self.assertEqual(self.stage()[0], 202)
        self.assertEqual(self.pair()[0], 200)
        self.owner = (IDENTITY[0], "attacker-node")
        self.assertEqual(self.candidate()[0], 400)
        self.assertEqual(self.confirm()[0], 400)
        self.assertEqual(self.approved, [])

    def test_ambiguous_new_wolf_client_denied(self):
        self.assertEqual(self.stage()[0], 202)
        self.assertEqual(self.pair()[0], 200)
        self.wolf.identities.append("99999999999")
        self.assertEqual(self.candidate()[0], 400)
        self.assertEqual(self.confirm()[0], 400)
        self.assertEqual(self.approved, [])


if __name__ == "__main__":
    unittest.main()
