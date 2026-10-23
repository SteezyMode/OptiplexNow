"""Unit tests for read-only host service discovery, without Docker access."""
from pathlib import Path
import json
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import host_services as services

WOLF = "a" * 64
JELLY = "b" * 64
QBIT = "c" * 64
VPN = "d" * 64


def record(cid, image, name=None, mode="bridge", status="running",
           health=None, env=None):
    return {
        "Id": cid, "Name": name or "/" + cid[:10],
        "Config": {"Image": image, "Env": env or []},
        "HostConfig": {"NetworkMode": mode},
        "State": {"Status": status, "Health": {"Status": health}},
        "Mounts": [{"Source": "/private/home/media", "Destination": "/downloads"}],
    }


def fake_docker(records, *, fail=False):
    def invoke(cmd, **kwargs):
        assert cmd[:3] == ["docker", "--host", "unix:///var/run/docker.sock"]
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["timeout"] == 8
        if fail:
            raise OSError("Docker unavailable")
        if cmd[3] == "ps":
            assert cmd[4:] == ["--all", "--no-trunc", "--quiet"]
            output = "\n".join(r["Id"] for r in records)
        else:
            assert cmd[3:6] == ["inspect", "--type", "container"]
            output = json.dumps(records)
        return subprocess.CompletedProcess(cmd, 0, output, "")
    return invoke


class HostServicesTests(unittest.TestCase):
    def full_stack(self):
        return [
            record(WOLF, "ghcr.io/games-on-whales/wolf:stable"),
            record(JELLY, "jellyfin/jellyfin:10.11.0"),
            record(VPN, "qmcgaw/gluetun:v3", name="/music-vpn",
                   health="healthy"),
            record(QBIT, "lscr.io/linuxserver/qbittorrent:5.1",
                   mode="container:music-vpn",
                   env=["WEBUI_PASSWORD=must-not-appear", "VPN_TOKEN=private"]),
        ]

    def test_existing_stack_is_only_a_candidate(self):
        result = services.collect(runner=fake_docker(self.full_stack()))
        self.assertTrue(result["read_only"])
        self.assertFalse(result["may_adopt"])
        self.assertFalse(result["changes_performed"])
        self.assertEqual(result["services"]["wolf"]["status"],
                         "running_candidate")
        self.assertEqual(result["services"]["jellyfin"]["status"],
                         "running_candidate")
        self.assertEqual(result["services"]["qbittorrent"]["docker_count"], 1)
        self.assertEqual(result["downloads"]["topology"],
                         "shared_gluetun_namespace")
        self.assertEqual(result["downloads"]["gateway_health"], "healthy")
        self.assertFalse(result["downloads"]["vpn_egress_verified"])
        self.assertFalse(result["downloads"]["killswitch_verified"])
        serialized = json.dumps(result)
        for secret in ("must-not-appear", "private", "/private/home/media",
                       "music-vpn", QBIT, VPN):
            self.assertNotIn(secret, serialized)

    def test_missing_is_not_claimed_absent_or_installable(self):
        result = services.collect(runner=fake_docker([]))
        self.assertEqual(result["services"]["jellyfin"]["status"],
                         "not_detected_in_docker")
        self.assertFalse(result["may_adopt"])
        self.assertEqual(result["storage_paths"], "not_inspected")

    def test_docker_not_available_is_not_empty_inventory(self):
        result = services.collect(runner=fake_docker([], fail=True))
        self.assertEqual(result["docker_access"], "unavailable")
        self.assertEqual(result["services"]["wolf"]["status"], "unknown")
        self.assertEqual(result["services"]["qbittorrent"]["status"],
                         "unknown")

    def test_multiple_and_lookalikes_do_not_allow_adoption(self):
        stack = self.full_stack()
        stack.append(record("e" * 64, "jellyfin/jellyfin:10.9"))
        stack.append(record("f" * 64, "evil.example/jellyfin:latest"))
        stack.append(record("1" * 64, "evil.example/wolf:latest"))
        result = services.collect(runner=fake_docker(stack))
        self.assertEqual(result["services"]["jellyfin"]["status"],
                         "ambiguous_multiple")
        self.assertEqual(result["services"]["wolf"]["docker_count"], 1)
        self.assertFalse(result["may_adopt"])

    def test_docker_relationship_not_egress_proof(self):
        stack = self.full_stack()
        stack[-1]["HostConfig"]["NetworkMode"] = "bridge"
        result = services.collect(runner=fake_docker(stack))
        self.assertEqual(result["downloads"]["topology"], "not_verified")

    def test_invalid_and_duplicate_ids_fail_closed(self):
        for recs in (
            [record("not-a-container-id", "jellyfin/jellyfin")],
            [record(WOLF, "jellyfin/jellyfin"),
             record(WOLF, "jellyfin/jellyfin")],
        ):
            with self.subTest(recs=recs), self.assertRaises(
                    services.InventoryUnavailable):
                services.docker_records(runner=fake_docker(recs))

    def test_stopped_and_unknown_state(self):
        self.assertEqual(
            services.assess([record(WOLF, "ghcr.io/games-on-whales/wolf:v",
                                    status="exited")])["services"]["wolf"]["status"],
            "stopped_candidate")

    def test_bounded_image_classification(self):
        self.assertEqual(services.classify_image(
            "ghcr.io/games-on-whales/wolf@sha256:" + "0" * 64), "wolf")
        for image in ("evil/wolf:latest", "qmcgaw/gluetun-fake",
                      "wolf", None, "jellyfin/jellyfin-extra",
                      "qmcgaw/gluetun" + "a" * 300):
            self.assertIsNone(services.classify_image(image))


if __name__ == "__main__":
    unittest.main()
