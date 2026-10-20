"""Real HTTP wire-protocol integration under loopback with synthetic Tailscale.

This test deliberately never invokes the real daemon or touches external peers.
It catches mismatches between the actual host endpoint, JSON protocol, and
client scanner that unit tests with isolated stubs cannot catch.
"""
import hashlib
import http.client
from http.server import HTTPServer
import importlib.util
import json
from pathlib import Path
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent = load("now_host_wire", "server/now-host-agent.py")
client = load("now_client_wire", "src/find-now-hosts.py")

CLIENT_IP = "100.78.22.5"
HOST_IP = "100.88.44.7"
HOST_ID = "nTEST_HOST_XYZ"


class FakeCommandResult:
    returncode = 0

    def __init__(self, obj):
        self.stdout = json.dumps(obj)


def synthetic_whois(args, **kwargs):
    assert args == ["tailscale", "whois", "--json", CLIENT_IP]
    return FakeCommandResult({
        "Node": {
            "ID": "nTEST_CLIENT",
            "Addresses": [CLIENT_IP + "/32"],
            "AllowedIPs": ["100.78.0.0/16"],
        },
        "UserProfile": {"LoginName": "private-test-identity@example.invalid"},
    })


class RunningServer:
    def __init__(self, authorized=True, backend="wolf"):
        _, self.payload = agent.host_identity({
            "BackendState": "Running",
            "Self": {"StableID": HOST_ID, "TailscaleIPs": [HOST_IP]},
        }, name="Test Gaming PC", backend=backend)
        def permit_loopback(_observed_ip):
            # The loopback transport stands in for a real encrypted tailnet
            # connection. The injected WhoIs verifies the synthetic CLIENT_IP.
            return authorized and agent.peer_authorized(
                CLIENT_IP, runner=synthetic_whois)

        self.server = HTTPServer(
            ("127.0.0.1", 0), agent.make_handler(self.payload, authorize=permit_loopback))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def connect(self, _ip, _port, timeout):
        return http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=timeout)

    def close(self):
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()


class TailnetWireContractTests(unittest.TestCase):
    def client_status(self):
        return {
            "BackendState": "Running",
            "Self": {"StableID": "nTEST_CLIENT", "TailscaleIPs": [CLIENT_IP]},
            "Peer": {"server": {
                "StableID": HOST_ID, "Online": True,
                "TailscaleIPs": [HOST_IP],
                "DNSName": "test-gaming-pc.private.example.invalid",
            }},
        }

    def test_real_http_agent_to_client_discovery_flow(self):
        host = RunningServer(backend="wolf")
        try:
            # The real peer enumeration is used. Only the wire connection
            # is redirected to an isolated loopback HTTP listener.
            found = client.discover(
                self.client_status(),
                probe_fn=lambda ip, marker: client.probe(
                    ip, marker, connector=host.connect))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["name"], "Test Gaming PC")
            self.assertEqual(found[0]["backend"], "wolf")
            self.assertEqual(found[0]["ip"], HOST_IP)
            self.assertEqual(found[0]["server_id"], host.payload["server_id"])
            serialized = json.dumps(found)
            self.assertNotIn("private-test-identity", serialized)
            self.assertNotIn("private.example.invalid", serialized)
        finally:
            host.close()

    def test_real_http_denied_when_whois_or_network_auth_missing(self):
        host = RunningServer(authorized=False)
        try:
            discovered = client.discover(
                self.client_status(),
                probe_fn=lambda ip, marker: client.probe(
                    ip, marker, connector=host.connect))
            self.assertEqual(discovered, [])
        finally:
            host.close()

    def test_real_http_rejects_nonmatching_tailnet_node_marker(self):
        host = RunningServer()
        try:
            forged = hashlib.sha256(b"wrong node").hexdigest()[:32]
            self.assertIsNone(client.probe(HOST_IP, forged, connector=host.connect))
        finally:
            host.close()

    def test_real_http_discovery_is_read_only(self):
        host = RunningServer()
        try:
            conn = host.connect(HOST_IP, agent.PORT, timeout=2)
            conn.request("POST", "/v1/discover", body=b'{"restart":true}')
            response = conn.getresponse()
            self.assertEqual(response.status, 405)
            response.read()
            conn.close()

            conn = host.connect(HOST_IP, agent.PORT, timeout=2)
            conn.request("GET", "/v1/control")
            response = conn.getresponse()
            self.assertEqual(response.status, 404)
            response.read()
            conn.close()

            conn = host.connect(HOST_IP, agent.PORT, timeout=2)
            conn.request("GET", "/v1/discover")
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())["pairing"], "not_implemented")
            conn.close()
        finally:
            host.close()


if __name__ == "__main__":
    unittest.main()
