"""Mock-only NOW discovery tests: never contact the user's tailnet."""
import importlib.util
import io
import json
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
import unittest

FILE = Path(__file__).resolve().parents[1] / "src" / "find-now-hosts.py"
spec = importlib.util.spec_from_file_location("find_now_hosts", FILE)
discovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discovery)


def peer(node, ip, *, online=True):
    return {"ID": node, "TailscaleIPs": [ip], "Online": online}


class StubResponse:
    status = 200

    def __init__(self, payload, kind="application/json"):
        self.payload = payload
        self.kind = kind

    def getheader(self, field, fallback=None):
        return self.kind if field == "Content-Type" else fallback

    def read(self, size):
        return self.payload[:size]


class StubConnection:
    def __init__(self, host, port, timeout, response):
        self.host, self.port, self.timeout = host, port, timeout
        self.response = response
        self.method = None
        self.closed = False

    def request(self, method, path, headers=None):
        self.method, self.path, self.headers = method, path, headers

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class DiscoveryTests(unittest.TestCase):
    def test_candidates_reject_lan_self_and_offline(self):
        status = {"BackendState": "Running", "Self": peer("self", "100.88.88.88"),
                  "Peer": {
                      "good": peer("n1", "100.80.0.7"),
                      "other": peer("n2", "100.80.0.8"),
                      "offline": peer("n3", "100.80.0.9", online=False),
                      "lan": peer("n4", "192.168.1.9"),
                      "dns": peer("n5", "100.100.100.100")}}
        result = discovery.peers_to_check(status)
        self.assertEqual([x[0] for x in result], ["100.80.0.7", "100.80.0.8"])
        self.assertEqual(len(result[0][1]), 32)
        self.assertFalse(any(x[0] == "100.88.88.88" for x in result))

    def test_requires_connected_tailscale(self):
        with self.assertRaises(ValueError):
            discovery.peers_to_check({"BackendState": "NeedsLogin"})

    def test_caps_probes(self):
        status = {"BackendState": "Running", "Peer": {
            str(i): peer("n" + str(i), "100.67.2." + str(i))
            for i in range(1, 80)}}
        self.assertEqual(len(discovery.peers_to_check(status)), discovery.MAX_PEERS)

    def test_accept_matching_host_identity(self):
        node = "n1"
        expected = discovery.peers_to_check({
            "BackendState": "Running",
            "Peer": {"x": peer(node, "100.80.4.8")}})[0][1]
        document = {
            "service": "now-host", "protocol": 1,
            "server_id": expected, "name": "NOW Test", "backend": "sunshine"
        }
        objects = []
        def factory(host, port, timeout):
            c = StubConnection(host, port, timeout,
                               StubResponse(json.dumps(document).encode()))
            objects.append(c)
            return c
        match = discovery.probe("100.80.4.8", expected, connector=factory)
        self.assertEqual(match["name"], "NOW Test")
        self.assertEqual(match["backend"], "sunshine")
        self.assertEqual(objects[0].method, "GET")
        self.assertEqual(objects[0].path, "/v1/discover")
        self.assertTrue(objects[0].closed)
        self.assertLessEqual(objects[0].timeout, 1)

    def test_reject_identity_mismatch_and_unsafe_labels(self):
        valid = {"service": "now-host", "protocol": 1,
                 "server_id": "a" * 32, "name": "NOW Server",
                 "backend": "wolf"}
        for change in ({"server_id": "b" * 32},
                       {"name": "Bad\tServer"},
                       {"name": "<script>"},
                       {"service": "something-else"},
                       {"protocol": 8},
                       {"backend": "ssh"},
                       {"protocol": True}):
            document = {**valid, **change}
            with self.subTest(change=change):
                conn = lambda *args, **kwargs: StubConnection(
                    "100.90.0.2", 18791, 1,
                    StubResponse(json.dumps(document).encode()))
                self.assertIsNone(discovery.probe("100.90.0.2", "a" * 32, connector=conn))
        self.assertIsNone(discovery.probe("8.8.8.8", "a" * 32,
                                          connector=lambda *args, **kwargs: self.fail()))

    def test_ignores_oversized_json_and_wrong_mimetype(self):
        large = b"X" * 5000
        for response in (StubResponse(large), StubResponse(b"{}", kind="text/html")):
            connector = lambda *args, **kwargs: StubConnection(
                "100.90.0.2", 18791, 1, response)
            self.assertIsNone(discovery.probe("100.90.0.2", "a" * 32, connector=connector))

    def test_discover_skips_unresponsive_nodes(self):
        status = {"BackendState": "Running", "Peer": {
            "a": peer("a", "100.90.1.1"), "b": peer("b", "100.90.1.2")}}
        seen = []
        def fake_probe(ip, identifier):
            seen.append(ip)
            return {"ip": ip, "server_id": identifier, "name": "Found",
                    "backend": "unknown"} if ip.endswith(".2") else None
        found = discovery.discover(status, probe_fn=fake_probe)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["ip"], "100.90.1.2")
        self.assertEqual(set(seen), {"100.90.1.1", "100.90.1.2"})

    def test_no_implicit_network_signin(self):
        with patch.object(discovery.subprocess, "run") as runner:
            runner.return_value.returncode = 1
            with redirect_stdout(io.StringIO()):
                self.assertEqual(discovery.main(["--json"]), 1)
            cmd = runner.call_args[0][0]
            self.assertEqual(cmd, ["tailscale", "status", "--json"])


if __name__ == "__main__":
    unittest.main()
