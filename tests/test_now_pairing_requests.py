"""Offline approval-state tests. No Tailscale, Moonlight, Docker or live host."""
import importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "server" / "now_pairing_requests.py"
spec = importlib.util.spec_from_file_location("now_pairing_requests", SOURCE)
pairing = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = pairing
spec.loader.exec_module(pairing)


class FakeClock:
    def __init__(self):
        self.seconds = 100.0

    def __call__(self):
        return self.seconds

    def tick(self, amount):
        self.seconds += amount


class PairingApprovalTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.queue = pairing.PairingRequests(clock=self.clock, ttl_seconds=180)
        self.alice = pairing.PeerIdentity("node_alice", "user_alice")
        self.bob = pairing.PeerIdentity("node_bob", "user_bob")

    def test_request_never_grants_access_without_owner_decision(self):
        request_id = self.queue.request(self.alice, "wolf")
        self.assertGreaterEqual(len(request_id), 24)
        self.assertEqual(self.queue.status_for_peer(self.alice, request_id), "pending")
        self.assertEqual(self.queue.owner_pending()[0].peer, self.alice)
        self.assertIsNone(self.queue.take_grant_for_adapter(self.alice, request_id, "wolf"))

    def test_owner_approval_consumes_once_and_binds_backend(self):
        request_id = self.queue.request(self.alice, "sunshine")
        self.assertTrue(self.queue.owner_decide(request_id, approve=True))
        self.assertEqual(self.queue.status_for_peer(self.alice, request_id), "approved")
        self.assertIsNone(self.queue.take_grant_for_adapter(self.alice, request_id, "wolf"))
        grant = self.queue.take_grant_for_adapter(self.alice, request_id, "sunshine")
        self.assertIsInstance(grant, pairing.PairingGrant)
        self.assertEqual(grant.peer, self.alice)
        self.assertEqual(grant.backend, "sunshine")
        self.assertIsNone(self.queue.take_grant_for_adapter(self.alice, request_id, "sunshine"))
        self.assertEqual(self.queue.status_for_peer(self.alice, request_id), "unknown")

    def test_other_verified_device_cannot_observe_cancel_or_claim(self):
        request_id = self.queue.request(self.alice, "wolf")
        self.assertEqual(self.queue.status_for_peer(self.bob, request_id), "unknown")
        self.assertFalse(self.queue.cancel_for_peer(self.bob, request_id))
        self.assertTrue(self.queue.owner_decide(request_id, approve=True))
        self.assertIsNone(self.queue.take_grant_for_adapter(self.bob, request_id, "wolf"))
        self.assertIsNotNone(self.queue.take_grant_for_adapter(self.alice, request_id, "wolf"))

    def test_same_node_other_user_identity_is_not_authorized(self):
        request_id = self.queue.request(self.alice, "sunshine")
        swapped = pairing.PeerIdentity(self.alice.node_id, "user_attacker")
        self.assertEqual(self.queue.status_for_peer(swapped, request_id), "unknown")
        self.assertTrue(self.queue.owner_decide(request_id, approve=True))
        self.assertIsNone(self.queue.take_grant_for_adapter(swapped, request_id, "sunshine"))

    def test_denial_is_final_and_does_not_allow_quick_new_request(self):
        request_id = self.queue.request(self.alice, "wolf")
        self.assertTrue(self.queue.owner_decide(request_id, approve=False))
        self.assertEqual(self.queue.status_for_peer(self.alice, request_id), "denied")
        self.assertFalse(self.queue.owner_decide(request_id, approve=True))
        self.assertIsNone(self.queue.take_grant_for_adapter(self.alice, request_id, "wolf"))
        self.assertEqual(self.queue.request(self.alice, "wolf"), request_id)
        with self.assertRaises(ValueError):
            self.queue.request(self.alice, "sunshine")

    def test_cancel_does_not_grant_and_requires_verified_same_peer(self):
        request_id = self.queue.request(self.alice, "wolf")
        self.assertTrue(self.queue.cancel_for_peer(self.alice, request_id))
        self.assertEqual(self.queue.status_for_peer(self.alice, request_id), "unknown")
        self.assertFalse(self.queue.owner_decide(request_id, approve=True))
        self.assertFalse(self.queue.cancel_for_peer(self.alice, request_id))

    def test_requests_expire_and_cannot_be_approved_or_replayed(self):
        request_id = self.queue.request(self.alice, "wolf")
        self.clock.tick(180)
        self.assertEqual(self.queue.status_for_peer(self.alice, request_id), "unknown")
        self.assertFalse(self.queue.owner_decide(request_id, approve=True))
        self.assertIsNone(self.queue.take_grant_for_adapter(self.alice, request_id, "wolf"))
        self.assertNotEqual(self.queue.request(self.alice, "wolf"), request_id)

    def test_approval_expires_even_after_owner_approved(self):
        request_id = self.queue.request(self.alice, "sunshine")
        self.assertTrue(self.queue.owner_decide(request_id, approve=True))
        self.clock.tick(181)
        self.assertIsNone(self.queue.take_grant_for_adapter(self.alice, request_id, "sunshine"))

    def test_queue_limit_fails_closed(self):
        queue = pairing.PairingRequests(clock=self.clock, max_requests=1)
        alice_req = queue.request(self.alice, "wolf")
        with self.assertRaises(RuntimeError):
            queue.request(self.bob, "wolf")
        self.assertTrue(queue.owner_decide(alice_req, approve=False))
        with self.assertRaises(RuntimeError):
            queue.request(self.bob, "sunshine")
        self.clock.tick(181)
        self.assertIsInstance(queue.request(self.bob, "sunshine"), str)

    def test_duplicate_requests_are_idempotent_and_single_pending(self):
        request_id = self.queue.request(self.alice, "wolf")
        self.clock.tick(90)
        self.assertEqual(self.queue.request(self.alice, "wolf"), request_id)
        self.assertEqual(len(self.queue.owner_pending()), 1)
        self.clock.tick(91)
        self.assertEqual(self.queue.status_for_peer(self.alice, request_id), "unknown")

    def test_invalid_identity_backend_and_options_fail_closed(self):
        for kwargs in (
            {"node_id": "node_ok", "user_id": ""},
            {"node_id": "node;sudo", "user_id": "user_ok"},
            {"node_id": "node_ok", "user_id": "user@domain"},
            {"node_id": 123, "user_id": "user_ok"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                pairing.PeerIdentity(**kwargs)
        with self.assertRaises(TypeError):
            self.queue.request({"node_id": "node_alice", "user_id": "user_alice"}, "wolf")
        for backend in ("docker", "unknown", "WOLF", None, 2):
            with self.subTest(backend=backend), self.assertRaises(ValueError):
                self.queue.request(self.alice, backend)
        for options in ({"ttl_seconds": 0}, {"ttl_seconds": 9999},
                        {"max_requests": 0}, {"max_requests": True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                pairing.PairingRequests(**options)
        self.assertEqual(self.queue.status_for_peer(self.alice, "../../../etc"), "unknown")

    def test_owner_decision_requires_boolean_and_valid_id(self):
        request_id = self.queue.request(self.alice, "wolf")
        for bad in ("yes", 1, None):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                self.queue.owner_decide(request_id, approve=bad)
        self.assertFalse(self.queue.owner_decide("invalid", approve=True))
        self.assertFalse(self.queue.owner_decide("A" * 40, approve=True))

    def test_independent_queues_cannot_share_approval(self):
        request_id = self.queue.request(self.alice, "sunshine")
        self.assertTrue(self.queue.owner_decide(request_id, approve=True))
        other = pairing.PairingRequests(clock=self.clock)
        self.assertIsNone(other.take_grant_for_adapter(self.alice, request_id, "sunshine"))

    def test_thread_safe_one_time_grant(self):
        request_id = self.queue.request(self.alice, "wolf")
        self.assertTrue(self.queue.owner_decide(request_id, approve=True))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda _: self.queue.take_grant_for_adapter(self.alice, request_id, "wolf"),
                range(100)))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_request_id_collision_fails_closed(self):
        request_id = self.queue.request(self.alice, "wolf")
        with patch.object(pairing.secrets, "token_urlsafe", return_value=request_id):
            with self.assertRaises(RuntimeError):
                self.queue.request(self.bob, "wolf")
        self.assertEqual(len(self.queue.owner_pending()), 1)


if __name__ == "__main__":
    unittest.main()
