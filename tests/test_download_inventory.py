"""Offline inventory unit tests: no running Docker daemon required."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

MODULE = Path(__file__).resolve().parents[1] / "server" / "download_inventory.py"
spec = importlib.util.spec_from_file_location("download_inventory", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
VPN_ID = "a" * 64
QBIT_ID = "b" * 64


def runner(records):
    def run(command, **kwargs):
        assert command[:2] == ["docker", "ps"] or command[:2] == ["docker", "inspect"]
        if command[1] == "ps":
            output = "\n".join(x["Id"] for x in records)
        else:
            output = json.dumps(records)
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")
    return run


def record(identifier, image, mode="bridge", health=None):
    return {"Id": identifier, "Name": "/test", "Config": {"Image": image},
            "HostConfig": {"NetworkMode": mode},
            "State": {"Health": {"Status": health}}}


class InventoryTests(unittest.TestCase):
    def test_verified_attachment_is_not_egress_proof(self):
        records = [record(VPN_ID, "qmcgaw/gluetun:v3.41", health="healthy"),
                   record(QBIT_ID, "lscr.io/linuxserver/qbittorrent:5.1.4",
                          mode="container:" + VPN_ID)]
        result = mod.inspect_download_topology(runner=runner(records))
        self.assertEqual(result["downloaders"], [{
            "service": "qbittorrent", "gateway_bound": True,
            "gateway_healthy": True, "vpn_egress_verified": False,
            "killswitch_verified": False}])
        self.assertNotIn("Id", str(result))

    def test_unbound_downloader_is_not_safe(self):
        records = [record(QBIT_ID, "lscr.io/linuxserver/qbittorrent:5.1.4")]
        self.assertEqual(mod.inspect_download_topology(runner=runner(records))[
            "downloaders"], [{"service": "qbittorrent", "gateway_bound": False}])

    def test_lookalike_gateway_does_not_count(self):
        records = [record(VPN_ID, "unknown/gluetun-fake:latest"),
                   record(QBIT_ID, "lscr.io/linuxserver/qbittorrent:5.1.4",
                          mode="container:" + VPN_ID)]
        self.assertFalse(mod.inspect_download_topology(
            runner=runner(records))["downloaders"][0]["gateway_bound"])


if __name__ == "__main__":
    unittest.main()
