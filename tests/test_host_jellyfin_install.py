"""Safety tests for disposable clean-host Jellyfin pilot (never run Docker)."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import host_jellyfin_install as installer


class CleanJellyfinInstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.media = root / "media"
        self.media.mkdir()
        self.patches = [
            patch.object(installer, "BASE", root / "managed"),
            patch.object(installer, "WORKSPACE", root / "managed" / "jellyfin-host-pilot"),
            patch.object(installer, "STOP_PREFIXES",
                         tuple(p for p in installer.STOP_PREFIXES
                               if p != Path("/tmp"))),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.uid = os.geteuid()
        self.report = {
            "tool":"now-host-services", "docker_access":"available",
            "services":{"jellyfin":{"status":"not_detected_in_docker"}}}
        self.digest = "a" * 64
        self.tail = "100.121.156.34"

    def candidate(self, **overrides):
        params = {
            "media_path":str(self.media), "digest":self.digest,
            "uid":self.uid, "privileged":True,
            "docker_report":self.report, "tail_ip":self.tail,
            "compose_ready":True, "ports_ready":True,
            "system_ok":True, "disk_ok":True,
            "project_clear":True, "docker_network_ok":True,
        }
        params.update(overrides)
        return installer.assess(**params)

    def test_privileged_check_is_source_only_and_requires_known_clean_host(self):
        if self.uid == 0:
            self.skipTest("Disposable media folder owner must not be root")
        result = self.candidate()
        self.assertEqual(result["status"], "candidate_after_admin_check")
        self.assertFalse(result["changes_performed"])
        self.assertEqual(result["blockers"], [])
        self.assertFalse(installer.WORKSPACE.exists())
        self.assertEqual(self.candidate(privileged=False)["status"], "blocked")
        self.assertEqual(self.candidate(compose_ready=False)["status"], "blocked")
        self.assertEqual(self.candidate(system_ok=False)["status"], "blocked")
        self.assertEqual(self.candidate(disk_ok=False)["status"], "blocked")
        self.assertEqual(self.candidate(project_clear=False)["status"], "blocked")
        self.assertEqual(self.candidate(docker_network_ok=False)["status"], "blocked")
        self.assertEqual(self.candidate(ports_ready=False)["status"], "blocked")
        self.assertEqual(self.candidate(digest="latest")["status"], "blocked")
        self.assertEqual(self.candidate(tail_ip="192.168.1.2")["status"], "blocked")

    def test_existing_jellyfin_unknown_inventory_and_existing_state_block(self):
        if self.uid == 0:
            self.skipTest("Disposable media folder owner must not be root")
        other = {**self.report, "services":{
            "jellyfin":{"status":"running_candidate"}}}
        self.assertEqual(self.candidate(docker_report=other)["status"],"blocked")
        unknown = {**self.report,"docker_access":"unavailable"}
        self.assertEqual(self.candidate(docker_report=unknown)["status"],"blocked")
        installer.WORKSPACE.mkdir(parents=True)
        self.assertEqual(self.candidate()["status"], "blocked")

    def test_media_path_must_be_existing_owner_directory_without_symlinks(self):
        if self.uid == 0:
            self.skipTest("Disposable media folder owner must not be root")
        self.assertEqual(installer.media_root_for_owner(str(self.media),self.uid),
                         str(self.media))
        link = self.media.parent / "link"
        link.symlink_to(self.media, target_is_directory=True)
        for bad in (str(link), str(self.media / "../media"),
                    "/etc", "/root", "/", "/proc", "/dev",
                    str(self.media / "not-created")):
            with self.subTest(bad=bad):
                with self.assertRaises(installer.JellyfinInstallError):
                    installer.media_root_for_owner(bad,self.uid)
        with self.assertRaises(installer.JellyfinInstallError):
            installer.media_root_for_owner(str(self.media),self.uid+1)

    def test_rendered_compose_is_immutable_single_project_tailnet_and_read_only_media(self):
        if self.uid == 0:
            self.skipTest("Disposable media folder owner must not be root")
        compose = json.loads(installer.render_compose(
            image_digest=self.digest, media_root=str(self.media),
            owner_uid=self.uid, owner_gid=os.getegid(), tail_ip=self.tail))
        self.assertEqual(set(compose),{"services"})
        self.assertEqual(set(compose["services"]),{"jellyfin"})
        service = compose["services"]["jellyfin"]
        self.assertEqual(service["image"],
                         "jellyfin/jellyfin@sha256:" + self.digest)
        self.assertEqual(service["user"],f"{self.uid}:{os.getegid()}")
        self.assertEqual(service["cap_drop"],["ALL"])
        self.assertIn("no-new-privileges:true",service["security_opt"])
        self.assertEqual({x["host_ip"] for x in service["ports"]},
                         {"127.0.0.1",self.tail})
        self.assertEqual({x["target"] for x in service["ports"]},{8096})
        self.assertFalse(any(x["host_ip"] in ("0.0.0.0","::")
                             for x in service["ports"]))
        mounts=service["volumes"]
        self.assertEqual(mounts[2],{
            "type":"bind","source":str(self.media),
            "target":"/media/library","read_only":True})
        self.assertTrue(all(x.get("type")=="bind" for x in mounts))
        self.assertTrue(all(x["source"]!=str(self.media) or x.get("read_only")
                            for x in mounts))
        with self.assertRaises(installer.JellyfinInstallError):
            installer.render_compose(image_digest="latest",
                media_root=str(self.media),owner_uid=self.uid,
                owner_gid=os.getegid(),tail_ip=self.tail)
        with self.assertRaises(installer.JellyfinInstallError):
            installer.render_compose(image_digest=self.digest,
                media_root=str(self.media),owner_uid=self.uid,
                owner_gid=os.getegid(),tail_ip="0.0.0.0")

    def test_install_never_acts_without_pkexec_and_exact_confirmation(self):
        if self.uid == 0:
            self.skipTest("No root privileges are used in these tests")
        for text in ("", "INSTALL-WOLF", "INSTALL-JELLYFIN "):
            with self.assertRaises(installer.JellyfinInstallError):
                installer.install(str(self.media),self.digest,self.uid,text)
        with self.assertRaises(installer.JellyfinInstallError):
            installer.install(str(self.media),self.digest,self.uid,"INSTALL-JELLYFIN")
        self.assertFalse(installer.WORKSPACE.exists())

    def test_docker_network_gate_rejects_legacy_or_ambiguous_daemons(self):
        for version, allowed in (("24.0.7", False), ("27.5.1", False),
                                 ("28.0.0", True), ("28.4.1", True),
                                 ("29.0.0+patch.1", True),
                                 ("Docker 28.0.0", False),
                                 ("28.0", False), ("28.0.0\\n29.0.0", False)):
            with self.subTest(version=version):
                with patch.object(installer, "_invoke", return_value=version) as runner:
                    self.assertEqual(installer._docker_network_gate(), allowed)
                    runner.assert_called_once_with(
                        ["/usr/bin/docker", "version", "--format",
                         "{{.Server.Version}}"])
        with patch.object(installer, "_invoke",
                          side_effect=installer.JellyfinInstallError("no Docker")):
            self.assertFalse(installer._docker_network_gate())

    def test_runtime_inspect_must_verify_actual_network_and_readonly_mount(self):
        cid = "b" * 64
        image = installer.IMAGE_BASE + self.digest
        expected = {
            "Id":cid, "State":{"Running":True},
            "Config":{"Image":image, "User":f"{self.uid}:{os.getegid()}",
                      "Labels":{"com.docker.compose.project":installer.PROJECT,
                                "io.optiplex-now.managed":"jellyfin-host-pilot"}},
            "HostConfig":{"NetworkMode":"optiplex-now-jellyfin-pilot_default"},
            "NetworkSettings":{"Ports":{
                "8096/tcp":[{"HostIp":"127.0.0.1","HostPort":"8096"},
                            {"HostIp":self.tail,"HostPort":"8096"}],
                "8920/tcp":None, "7359/udp":None}},
            "Mounts":[{"Type":"bind","Source":str(installer.WORKSPACE/"config"),
                       "Destination":"/config","RW":True},
                      {"Type":"bind","Source":str(installer.WORKSPACE/"cache"),
                       "Destination":"/cache","RW":True},
                      {"Type":"bind","Source":str(self.media),
                       "Destination":"/media/library","RW":False}]
        }
        import copy
        def verify(item):
            return installer._verified_container(
                item, cid=cid, image=image, tail_ip=self.tail,
                media_path=str(self.media), owner_uid=self.uid,
                owner_gid=os.getegid())
        self.assertTrue(verify(expected))
        mutated = copy.deepcopy(expected)
        mutated["NetworkSettings"]["Ports"]["8096/tcp"][1]["HostIp"] = "0.0.0.0"
        self.assertFalse(verify(mutated))
        mutated = copy.deepcopy(expected)
        mutated["NetworkSettings"]["Ports"]["8096/tcp"][1]["HostPort"] = "9090"
        self.assertFalse(verify(mutated))
        mutated = copy.deepcopy(expected)
        mutated["NetworkSettings"]["Ports"]["8920/tcp"] = [
            {"HostIp":"0.0.0.0", "HostPort":"8920"}]
        self.assertFalse(verify(mutated))
        mutated = copy.deepcopy(expected)
        mutated["Mounts"][2]["RW"] = True
        self.assertFalse(verify(mutated))
        mutated = copy.deepcopy(expected)
        mutated["Mounts"][2]["Source"] = "/unrelated/data"
        self.assertFalse(verify(mutated))
        mutated = copy.deepcopy(expected)
        mutated["Mounts"].pop()
        self.assertFalse(verify(mutated))
        mutated = copy.deepcopy(expected)
        mutated["Config"]["User"] = "0:0"
        self.assertFalse(verify(mutated))
        mutated = copy.deepcopy(expected)
        mutated["HostConfig"]["NetworkMode"] = "host"
        self.assertFalse(verify(mutated))
        mutated = copy.deepcopy(expected)
        mutated["State"] = None
        self.assertFalse(verify(mutated))
        mutated = copy.deepcopy(expected)
        mutated["Config"]["Labels"]["com.docker.compose.project"] = "someone-else"
        self.assertFalse(verify(mutated))

    def test_gui_source_and_packaging_are_not_implicit_host_install(self):
        gui = (ROOT / "src/host-jellyfin-new-ui.py").read_text()
        installer_source=(ROOT / "server/host_jellyfin_install.py").read_text()
        adoption = (ROOT / "src/host-media-setup.py").read_text()
        package = (ROOT / "package.py").read_text()
        self.assertIn("SET UP NEW JELLYFIN ON A CLEAN HOST", adoption)
        self.assertIn("CHECK CLEAN-HOST ELIGIBILITY (OS APPROVAL)", gui)
        self.assertIn("INSTALL ON THIS HOST", gui)
        self.assertIn("INSTALL-JELLYFIN", gui)
        self.assertIn("PKEXEC_UID", installer_source)
        self.assertIn("refused_or_interrupted", installer_source)
        self.assertIn('VERSION_ID") == "24.04"', installer_source)
        self.assertIn("--no-recreate", installer_source)
        self.assertIn("label=com.docker.compose.project=", installer_source)
        self.assertIn("host_jellyfin_install.py", package)
        self.assertNotIn("docker compose down", installer_source.lower())
        self.assertNotIn("docker system prune", installer_source.lower())
        compile(gui,"host-jellyfin-new-ui","exec")
        compile(installer_source,"host_jellyfin_install","exec")


if __name__ == "__main__":
    unittest.main()
