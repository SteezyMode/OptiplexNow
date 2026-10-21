"""Offline tests for Tailscale peer discovery. No socket or daemon required."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "src" / "find-servers.py"
spec = importlib.util.spec_from_file_location("now_find_servers", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DiscoveryTests(unittest.TestCase):
    def test_requires_running_tailnet(self):
        with self.assertRaises(ValueError):
            module.candidates({"BackendState": "NeedsLogin", "Peer": {}},
                              probe=lambda host: True)

    def test_online_streaming_hint_is_priority_not_authorization(self):
        status = {
            "BackendState": "Running",
            "Self": {"TailscaleIPs": ["100.64.0.1"]},
            "Peer": {
                "one": {"Online": True, "HostName": "living-room",
                        "TailscaleIPs": ["100.64.0.2"]},
                "two": {"Online": False, "HostName": "old-client",
                        "TailscaleIPs": ["100.64.0.3"]},
                "three": {"Online": True, "HostName": "game-host",
                          "TailscaleIPs": ["100.64.0.4", "fd7a:115c:a1e0::4"]},
            }
        }
        rows = module.candidates(status, probe=lambda host: host == "100.64.0.4")
        self.assertEqual([row[0] for row in rows],
                         ["100.64.0.4", "100.64.0.2", "100.64.0.3"])
        self.assertIn("Game streaming port reachable", rows[0][1])
        self.assertNotIn("100.64.0.1", str(rows))

    def test_duplicate_peer_addresses_and_invalid_ip_are_not_listed(self):
        status = {"BackendState": "Running", "Peer": {
            "a": {"Online": True, "TailscaleIPs": ["not-an-ip", "100.64.1.8"]},
            "b": {"Online": False, "TailscaleIPs": ["100.64.1.8"]},
            "c": {"Online": True, "TailscaleIPs": []},
        }}
        rows = module.candidates(status, probe=lambda host: False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "100.64.1.8")

    def test_self_address_is_never_a_selectable_server(self):
        data = {"BackendState": "Running",
                "Self": {"TailscaleIPs": ["100.64.0.1"]},
                "Peer": {"unexpected-self": {"Online": True,
                           "TailscaleIPs": ["100.64.0.1"]},
                         "host": {"Online": True,
                                  "TailscaleIPs": ["100.64.0.9"]}}}
        rows = module.candidates(data, probe=lambda host: False)
        self.assertEqual([row[0] for row in rows], ["100.64.0.9"])

    def test_malformed_peers_are_rejected(self):
        with self.assertRaises(ValueError):
            module.candidates({"BackendState": "Running", "Peer": ["wrong"]},
                              probe=lambda host: False)

    def test_empty_peers_is_not_an_error(self):
        self.assertEqual(module.candidates({"BackendState": "Running", "Peer": {}},
                                            probe=lambda host: False), [])


if __name__ == "__main__":
    unittest.main()
