"""Pure, offline adoption-planner tests; never call a real Docker daemon."""
from pathlib import Path
import copy
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import host_adoption as adopt
import host_services as services

WOLF, JELLY, VPN, QBIT = ("a"*64, "b"*64, "c"*64, "d"*64)


def container(cid, image, name, *, status="running", mode="bridge",
              health="healthy"):
    return {"Id": cid, "Name": "/" + name, "Config": {"Image": image},
            "State": {"Status": status, "Health": {"Status": health}},
            "HostConfig": {"NetworkMode": mode},
            "Mounts": [{"Source": "/private/user/media", "Destination": "/media"}]}


def stack():
    return [
        container(WOLF, "ghcr.io/games-on-whales/wolf:stable", "wolf"),
        container(JELLY, "jellyfin/jellyfin:latest", "jellyfin"),
        container(VPN, "qmcgaw/gluetun:v3", "vpn"),
        container(QBIT, "lscr.io/linuxserver/qbittorrent:latest", "qbit",
                  mode="container:" + VPN),
    ]


class AdoptionPlannerTests(unittest.TestCase):
    def test_reference_stack_requires_manual_review(self):
        r = adopt.plan(services.assess(stack()))
        self.assertEqual(r["decision"], "existing_services_need_authorized_review")
        self.assertEqual(r["services"]["wolf"], "review_existing_without_changes")
        self.assertEqual(r["services"]["jellyfin"], "review_existing_without_changes")
        self.assertEqual(r["services"]["downloader_network"],
                         "review_topology_and_verify_vpn_fail_closed")
        self.assertTrue(r["read_only"])
        self.assertFalse(r["may_adopt"])
        self.assertFalse(r["may_install"])
        self.assertFalse(r["changes_performed"])
        self.assertNotIn("/private/user/media", str(r))
        self.assertNotIn(WOLF, str(r))
        self.assertNotIn(VPN, str(r))
        self.assertNotIn("vpn", r["services"])

    def test_empty_docker_is_not_permission_to_install(self):
        r = adopt.plan(services.assess([]))
        self.assertEqual(r["decision"], "native_service_scan_required")
        self.assertTrue(all(r["services"][s] ==
                            "inspect_native_services_before_new_setup"
                            for s in adopt.SERVICE_KEYS))
        self.assertFalse(r["may_install"])

    def test_existing_downloader_without_gateway_requires_manual_review(self):
        only_downloader = [stack()[-1]]
        r = adopt.plan(services.assess(only_downloader))
        self.assertEqual(r["decision"], "manual_review_required")
        self.assertEqual(r["services"]["downloader_network"],
                         "blocked_until_services_reviewed")
        self.assertFalse(r["may_install"])

    def test_unavailable_docker_is_never_empty(self):
        r = adopt.plan(services.assess(None))
        self.assertEqual(r["decision"], "cannot_inspect")
        self.assertEqual(r["services"]["wolf"],
                         "blocked_cannot_inspect_host")

    def test_multiples_and_stopped_services(self):
        s = stack()
        s[0]["State"]["Status"] = "exited"
        s.append(container("e"*64, "jellyfin/jellyfin:latest", "another"))
        r = adopt.plan(services.assess(s))
        self.assertEqual(r["services"]["wolf"],
                         "review_stopped_existing_without_restart")
        self.assertEqual(r["services"]["jellyfin"],
                         "blocked_multiple_cannot_choose")
        self.assertEqual(r["decision"], "manual_review_required")

    def test_unbound_downloader_refuses_adoption(self):
        s = stack()
        s[-1]["HostConfig"]["NetworkMode"] = "bridge"
        r = adopt.plan(services.assess(s))
        self.assertEqual(r["services"]["downloader_network"],
                         "blocked_downloader_vpn_binding_unverified")
        self.assertFalse(r["may_adopt"])

    def test_refuse_poisoned_or_optimistic_reports(self):
        good = services.assess(stack())
        mutators = [
            lambda x: x.update(may_adopt=True),
            lambda x: x.update(read_only=False),
            lambda x: x["services"]["wolf"].update(docker_count=True),
            lambda x: x["services"]["wolf"].update(docker_count=2),
            lambda x: x["services"]["wolf"].update(status="installed"),
            lambda x: x["downloads"].update(killswitch_verified=True),
            lambda x: x.update(storage_paths="/home/user"),
            lambda x: x.update(vuetorrent="available"),
            lambda x: x["services"]["jellyfin"].update(status="ambiguous_multiple"),
            lambda x: x.update(docker_access="unavailable"),
        ]
        for poison in mutators:
            item = copy.deepcopy(good)
            poison(item)
            with self.subTest(item=item), self.assertRaises(ValueError):
                adopt.plan(item)


if __name__ == "__main__":
    unittest.main()
