"""Synthetic/offline tests for the opt-in NOW Host Agent."""
import http.client
import importlib.util
import json
from pathlib import Path
from threading import Thread
import unittest
from http.server import HTTPServer
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "server" / "now-host-agent.py"
spec = importlib.util.spec_from_file_location("now_host_agent", FILE)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class FakeResult:
    returncode = 0

    def __init__(self, data):
        self.stdout = json.dumps(data)


class AgentTests(unittest.TestCase):
    def status(self, **extra):
        self_node = {"ID": "nHOST01", "TailscaleIPs": ["100.90.40.21"]}
        self_node.update(extra)
        return {"BackendState": "Running", "Self": self_node}

    def test_bind_address_is_tailscale_only(self):
        ip, payload = agent.host_identity(self.status(), backend="wolf")
        self.assertEqual(ip, "100.90.40.21")
        self.assertEqual(payload["name"], "NOW Server")
        self.assertEqual(payload["service"], "now-host")
        self.assertEqual(payload["pairing"], "not_implemented")
        self.assertEqual(len(payload["server_id"]), 32)
        self.assertEqual(payload["server_id"], agent.host_identity(self.status())[1]["server_id"])

    def test_no_public_private_or_loopback_bind(self):
        for addr in ("0.0.0.0", "127.0.0.1", "192.168.10.5", "100.100.100.100",
                     "8.8.8.8", "fd7a:115c:a1e0::5"):
            with self.subTest(addr=addr):
                with self.assertRaises(ValueError):
                    agent.host_identity(self.status(TailscaleIPs=[addr]))

    def test_requires_enrolled_running_machine(self):
        with self.assertRaises(ValueError):
            agent.host_identity({"BackendState": "NeedsLogin"})
        with self.assertRaises(ValueError):
            agent.host_identity(self.status(ID=""))
        with self.assertRaises(ValueError):
            agent.host_identity(self.status(), name="../../etc/passwd")

    def test_whois_authorizes_exact_tailscale_address(self):
        calls = []

        def run(args, **kw):
            calls.append(args)
            return FakeResult({"Node": {
                "ID": 99, "Addresses": ["100.99.0.18/32"],
                "UserProfile": {"LoginName": "private@example.com"}}})
        self.assertTrue(agent.peer_authorized("100.99.0.18", runner=run))
        self.assertEqual(calls[0], ["tailscale", "whois", "--json", "100.99.0.18"])
        self.assertFalse(agent.peer_authorized("100.99.0.19", runner=run))
        self.assertFalse(agent.peer_authorized("192.168.0.18", runner=run))
        self.assertEqual(len(calls), 2)

    def test_whois_never_authorizes_subnet_routes(self):
        """A node with an advertised route is not the routed device."""
        cases = (
            {"ID": 8, "AllowedIPs": ["100.78.0.0/16"]},
            {"ID": 8, "Addresses": ["100.78.0.0/16"]},
            {"ID": 8, "Addresses": ["100.78.22.6/32"],
             "AllowedIPs": ["100.78.0.0/16"]},
            {"ID": 8, "Addresses": ["not-an-ip"], "AllowedIPs": ["100.78.0.0/16"]},
        )
        for node in cases:
            with self.subTest(node=node):
                def run(args, **kwargs):
                    return FakeResult({"Node": node})
                self.assertFalse(agent.peer_authorized("100.78.22.5", runner=run))
        def run_exact(args, **kwargs):
            return FakeResult({"Node": {"ID": 8,
                "Addresses": ["100.78.22.5/32"],
                "AllowedIPs": ["100.78.0.0/16"]}})
        self.assertTrue(agent.peer_authorized("100.78.22.5", runner=run_exact))

    def test_whois_errors_fail_closed(self):
        for response in ({}, {"Node": {"ID": 2}},
                         {"Node": {"ID": 2, "Addresses": ["192.168.1.2"]}}):
            def run(args, **kw):
                return FakeResult(response)
            with self.subTest(response=response):
                self.assertFalse(agent.peer_authorized("100.77.88.99", runner=run))

    def test_http_exposes_only_read_only_discovery(self):
        _, payload = agent.host_identity(self.status(), backend="sunshine")
        httpd = HTTPServer(("127.0.0.1", 0),
                           agent.make_handler(payload, authorize=lambda peer: True))
        worker = Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=2)
            conn.request("GET", "/v1/discover")
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            data = json.loads(response.read())
            self.assertEqual(data, payload)
            self.assertNotIn("100.90.40.21", json.dumps(data))
            conn.close()

            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=2)
            conn.request("POST", "/v1/discover", body="cmd=restart")
            self.assertEqual(conn.getresponse().status, 405)
            conn.close()

            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=2)
            conn.request("GET", "/v1/admin")
            self.assertEqual(conn.getresponse().status, 404)
            conn.close()
        finally:
            httpd.shutdown()
            worker.join(timeout=2)
            httpd.server_close()

    def test_unauthorized_peer_cannot_discover(self):
        _, payload = agent.host_identity(self.status())
        httpd = HTTPServer(("127.0.0.1", 0),
                           agent.make_handler(payload, authorize=lambda peer: False))
        worker = Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=2)
            conn.request("GET", "/v1/discover")
            response = conn.getresponse()
            self.assertEqual(response.status, 403)
            self.assertNotIn(b"server_id", response.read())
            conn.close()
        finally:
            httpd.shutdown()
            worker.join(timeout=2)
            httpd.server_close()

    def test_no_automatic_server_start(self):
        with patch.object(agent, "tailscale_json", return_value=self.status()), \
             patch.object(agent.http.server, "HTTPServer") as server:
            with patch("builtins.print"):
                self.assertEqual(agent.main([]), 0)
            server.assert_not_called()


if __name__ == "__main__":
    unittest.main()
