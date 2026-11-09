"""No-network tests for opt-in owner-only Moonlight/Wolf pairing coordinator."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "src/moonlight-auto-pair.py"
spec = importlib.util.spec_from_file_location("now_moonlight_auto_pair", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
HOST = "100.121.156.34"
PEER = "100.123.253.77"
MOON = ["moonlight"]


class FakePair:
    def __init__(self, exit_code=0):
        self.returncode = None
        self.exit_code = exit_code
        self.terminated = False
    def poll(self):
        return self.returncode
    def wait(self, timeout=None):
        self.returncode = self.exit_code
        return self.exit_code
    def terminate(self):
        self.terminated = True
        self.returncode = -15
    def kill(self):
        self.returncode = -9


class AutoPairTests(unittest.TestCase):
    def test_existing_paired_moonlight_is_not_repaired_or_probed_for_wolf(self):
        def no_wolf(*_args):
            self.fail("No Wolf API call for an already paired machine")
        def no_spawn(*_args, **_kwargs):
            self.fail("No Moonlight pairing subprocess for an already paired machine")
        runner = mock.Mock(return_value=SimpleNamespace(returncode=0))
        status = module.ensure_paired(HOST, PEER, MOON, invoke=no_wolf,
                                      runner=runner, spawn=no_spawn)
        self.assertEqual(status, "ALREADY_PAIRED")
        self.assertEqual(runner.call_args.args[0], ["moonlight", "list", HOST])

    def test_owner_fresh_pair_prepared_before_start_and_verified_after(self):
        events = []
        current = {"paired": False, "pending": 0}
        def run(argv, **kwargs):
            events.append(("list", argv))
            self.assertEqual(argv, ["moonlight", "list", HOST])
            self.assertIn("timeout", kwargs)
            return SimpleNamespace(returncode=0 if current["paired"] else 1)
        def invoke(host, action, payload=None):
            self.assertEqual(host, HOST)
            events.append((action, payload))
            if action == "prepare":
                return {"success": True, "status": "prepared"}
            if action == "pending":
                current["pending"] += 1
                if current["pending"] == 1:
                    return {"success": True, "clients": []}
                return {"success": True, "clients": [
                    {"index": 3, "client_ip": PEER}]}
            if action == "pair":
                self.assertEqual(payload, {"index": 3, "client_ip": PEER, "pin": "0423"})
                current["paired"] = True
                return {"success": True}
            self.fail("Unrecognized Wolf action")
        proc = FakePair()
        def spawn(argv, **kwargs):
            events.append(("moonlight", argv))
            self.assertEqual(argv, ["moonlight", "pair", HOST, "--pin", "0423"])
            self.assertTrue(kwargs["close_fds"])
            return proc
        status = module.ensure_paired(HOST, PEER, MOON, invoke=invoke,
                                      runner=run, spawn=spawn,
                                      pin_factory=lambda: "0423",
                                      sleeper=lambda _: None)
        self.assertEqual(status, "PAIRED")
        self.assertEqual([x[0] for x in events],
                         ["list", "prepare", "moonlight", "pending",
                          "pending", "pair", "list"])
        self.assertFalse(proc.terminated)

    def test_unapproved_or_missing_broker_cannot_start_local_moonlight(self):
        def denied(*_):
            raise ValueError("Owner pairing not enabled")
        def no_spawn(*_args, **_kwargs):
            self.fail("Never spawn Moonlight on a denied owner")
        with self.assertRaisesRegex(ValueError, "not enabled"):
            module.ensure_paired(HOST, PEER, MOON, invoke=denied, spawn=no_spawn,
                runner=lambda *_a, **_k: SimpleNamespace(returncode=1))

    def test_refuses_other_peers_pending_request_and_terminates_only_own_process(self):
        actions = []
        def invoke(host, action, payload=None):
            actions.append(action)
            if action == "prepare":
                return {"success": True, "status": "prepared"}
            return {"success": True, "clients": [
                {"index": 1, "client_ip": "100.80.99.9"}]}
        proc = FakePair()
        with self.assertRaisesRegex(ValueError, "differs from this device"):
            module.ensure_paired(HOST, PEER, MOON, invoke=invoke,
                runner=lambda *_a, **_k: SimpleNamespace(returncode=1),
                spawn=lambda *_a, **_k: proc, pin_factory=lambda: "0000")
        self.assertNotIn("pair", actions)
        self.assertTrue(proc.terminated)

    def test_failed_moonlight_handshake_never_claims_success(self):
        def invoke(host, action, payload=None):
            if action == "prepare":
                return {"success": True, "status": "prepared"}
            if action == "pending":
                return {"success": True, "clients": [
                    {"index": 1, "client_ip": PEER}]}
            return {"success": True}
        with self.assertRaisesRegex(ValueError, "did not finish"):
            module.ensure_paired(HOST, PEER, MOON, invoke=invoke,
                runner=lambda *_a, **_k: SimpleNamespace(returncode=1),
                spawn=lambda *_a, **_k: FakePair(exit_code=1),
                pin_factory=lambda: "5050")

    def test_no_candidate_is_bounded_and_owned_process_is_stopped(self):
        now = [0.0]
        def invoke(host, action, payload=None):
            if action == "prepare":
                return {"success": True, "status": "prepared"}
            return {"success": True, "clients": []}
        proc = FakePair()
        with self.assertRaisesRegex(ValueError, "No fresh pairing request"):
            module.ensure_paired(HOST, PEER, MOON, invoke=invoke,
                runner=lambda *_a, **_k: SimpleNamespace(returncode=1),
                spawn=lambda *_a, **_k: proc, clock=lambda: now[0],
                sleeper=lambda _: now.__setitem__(0, now[0] + 5),
                pin_factory=lambda: "1234")
        self.assertTrue(proc.terminated)

    def test_rejects_self_host_wrong_ip_and_malformed_pin(self):
        with self.assertRaisesRegex(ValueError, "own local Wolf"):
            module.ensure_paired(PEER, PEER, MOON,
                runner=lambda *_a, **_k: self.fail("Must not connect"))
        for address in ("127.0.0.1", "100.100.100.100", "evil.invalid"):
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    module.tailnet_address(address)
        with self.assertRaisesRegex(ValueError, "Invalid generated"):
            module.ensure_paired(HOST, PEER, MOON,
                runner=lambda *_a, **_k: SimpleNamespace(returncode=1),
                invoke=lambda *_a, **_k: {"success": True, "status": "prepared"},
                pin_factory=lambda: "12345", spawn=lambda *_a, **_k:
                self.fail("Bad PIN must not spawn"))

    def test_requires_running_local_tailscale_with_one_ipv4(self):
        valid = {"BackendState": "Running", "Self": {
            "TailscaleIPs": [PEER, "fd7a:115c:a1e0::77"]}}
        def runner_for(state):
            return lambda *_a, **_k: SimpleNamespace(
                returncode=0, stdout=json.dumps(state))
        self.assertEqual(module.own_tailnet_address(runner=runner_for(valid)), PEER)
        for data in ({"BackendState": "NeedsLogin"}, {"BackendState": "Running",
                        "Self": {"TailscaleIPs": []}}):
            with self.assertRaises(ValueError):
                module.own_tailnet_address(runner=runner_for(data))

    def test_only_owner_verified_tailnet_endpoint_not_admin_ssh_fallback(self):
        source = path.read_text(encoding="utf-8")
        self.assertIn("return module.invoke_tailnet(host, action, payload)", source)
        self.assertNotIn("module.invoke_preferred(", source)
        self.assertNotIn("ssh-copy-id", source)
        self.assertNotIn("sudo ", source)


if __name__ == "__main__":
    unittest.main()
