"""Mock-only MoonlightWeb maintenance tests. No Docker daemon or server touched."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "server" / "moonlightweb-maintenance.py"
spec = importlib.util.spec_from_file_location("moonlightweb_maintenance", FILE)
mw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mw)


def sample():
    return {
        "Name": "/moonlightweb",
        "Id": "sha256:original-container",
        "Image": "sha256:old",
        "Config": {
            "Image": mw.IMAGE,
            "Env": ["TZ=Asia/Tokyo", "MW_HTTPS_PORT=8443", "MW_HTTP_PORT=8080"],
            "Labels": {"org.opencontainers.image.version": "0.3.1"},
            "Entrypoint": ["/entrypoint.sh"], "Cmd": [], "User": "", "WorkingDir": "",
        },
        "HostConfig": {
            "NetworkMode": "host", "Privileged": False, "AutoRemove": False,
            "ReadonlyRootfs": False, "Binds": ["moonlightweb-test-data:/data:z"],
            "CapAdd": ["NET_BIND_SERVICE"], "CapDrop": ["ALL"],
            "RestartPolicy": {"Name": "unless-stopped"},
            "Devices": [], "Mounts": None, "PortBindings": None,
        },
        "Mounts": [{
            "Type": "volume", "Name": "moonlightweb-test-data",
            "Source": "/var/lib/docker/volumes/moonlightweb-test-data/_data",
            "Destination": "/data", "RW": True, "Mode": "z",
        }],
        "State": {"Running": True, "Health": {"Status": "healthy"}},
    }


class MoonlightWebMaintenanceTests(unittest.TestCase):
    def test_preserves_data_volume_ports_image_and_caps(self):
        args = mw.recreate_args(sample(), "sha256:new", Path("/tmp/mw-secret.env"))
        self.assertEqual(args[-1], "sha256:new")
        self.assertIn("moonlightweb-test-data:/data:z", args)
        self.assertIn("--env-file", args)
        self.assertIn("/tmp/mw-secret.env", args)
        self.assertNotIn("MW_HTTPS_PORT=8443", args)
        self.assertNotIn("MW_HTTP_PORT=8080", args)
        self.assertIn("unless-stopped", args)
        self.assertIn("NET_BIND_SERVICE", args)
        self.assertIn("ALL", args)
        self.assertNotIn("wolf", args)
        self.assertNotIn("rm", args)

    def test_preserves_existing_no_new_privileges_hardening(self):
        info = sample()
        # Observed Oct 20 reference server: no added capabilities, dropped ALL,
        # a named volume without mode suffix, and no-new-privileges.
        info["HostConfig"]["CapAdd"] = None
        info["HostConfig"]["SecurityOpt"] = ["no-new-privileges"]
        info["HostConfig"]["Binds"] = ["moonlightweb-test-data:/data"]
        info["Mounts"][0]["Mode"] = ""
        args = mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))
        self.assertIn("moonlightweb-test-data:/data", args)
        self.assertIn("--security-opt", args)
        position = args.index("--security-opt")
        self.assertEqual(args[position + 1], "no-new-privileges")
        self.assertEqual(args.count("--security-opt"), 1)
        self.assertNotIn("--cap-add", args)
        self.assertIn("ALL", args)

    def test_preserves_reference_memory_and_cpu_limits(self):
        info = sample()
        info["HostConfig"].update({
            "CapAdd": None,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "Binds": ["moonlightweb-test-data:/data"],
            "Memory": 1073741824,
            "MemorySwap": 2147483648,
            "NanoCpus": 1000000000,
            "CpuShares": 0,
        })
        info["Mounts"][0]["Mode"] = ""
        args = mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))
        self.assertEqual(args[args.index("--memory") + 1], "1073741824b")
        self.assertEqual(args[args.index("--memory-swap") + 1], "2147483648b")
        self.assertEqual(args[args.index("--cpus") + 1], "1")
        self.assertEqual(args[args.index("--security-opt") + 1], "no-new-privileges")
        self.assertIn("moonlightweb-test-data:/data", args)

    def test_rejects_invalid_memory_swap_limits(self):
        for value in (-2, 536870912):
            with self.subTest(value=value):
                info = sample()
                info["HostConfig"]["Memory"] = 1073741824
                info["HostConfig"]["MemorySwap"] = value
                with self.assertRaisesRegex(RuntimeError, "Invalid Docker resource limits"):
                    mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))

    def test_preserves_fractional_cpu_limits_without_float_rounding(self):
        info = sample()
        info["HostConfig"]["NanoCpus"] = 1250000000
        args = mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))
        self.assertEqual(args[args.index("--cpus") + 1], "1.25")

    def test_rejects_unhandled_resource_settings(self):
        for key, value in (
            ("CpuShares", 1024),
            ("MemoryReservation", 134217728),
            ("CpuQuota", 50000),
            ("PidsLimit", 100),
        ):
            with self.subTest(key=key):
                info = sample()
                info["HostConfig"][key] = value
                with self.assertRaisesRegex(RuntimeError, "resource limits"):
                    mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))

    def test_rejects_unrecognized_security_options(self):
        for value in (["apparmor=unconfined"], ["no-new-privileges", "label=disable"],
                      ["no-new-privileges=false"]):
            with self.subTest(value=value):
                info = sample()
                info["HostConfig"]["SecurityOpt"] = value
                with self.assertRaisesRegex(RuntimeError, "security options"):
                    mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))

    def test_rejects_bind_mount_change(self):
        info = sample()
        info["Mounts"][0]["Type"] = "bind"
        with self.assertRaises(RuntimeError):
            mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))

    def test_rejects_compose_adoption(self):
        info = sample()
        info["Config"]["Labels"]["com.docker.compose.project"] = "gaming"
        with self.assertRaises(RuntimeError):
            mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))

    def test_rejects_dangerous_docker_overrides(self):
        info = sample()
        info["HostConfig"]["Privileged"] = True
        with self.assertRaises(RuntimeError):
            mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))
        info = sample()
        info["HostConfig"]["Devices"] = [{"PathOnHost": "/dev/dri"}]
        with self.assertRaises(RuntimeError):
            mw.recreate_args(info, "sha256:new", Path("/tmp/mw-secret.env"))

    def test_wolf_ui_not_mistaken_for_user_session(self):
        with patch.object(mw, "docker", return_value="wolf\nWolf-UI_abc\nWolfStudioDesktop_123\nWolfSteam_456"):
            self.assertEqual(mw.active_wolf_apps(), ["WolfStudioDesktop_123", "WolfSteam_456"])

    def test_update_refuses_active_wolf_desktop_before_docker_mutation(self):
        with patch.object(mw, "active_wolf_apps", return_value=["WolfStudioDesktop_123"]), \
             patch.object(mw, "inspect") as inspect, \
             patch.object(mw, "docker") as docker:
            with self.assertRaisesRegex(RuntimeError, "Update deferred"):
                mw.update()
            inspect.assert_not_called()
            docker.assert_not_called()

    def test_preflight_never_pulls_or_stops_containers(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            info = sample()
            info["Mounts"][0]["Source"] = directory
            with patch.object(mw, "inspect", return_value=info), \
                 patch.object(mw, "check_image_defaults"), \
                 patch.object(mw, "active_wolf_apps", return_value=[]), \
                 patch.object(mw, "docker") as docker:
                mw.preflight()
                docker.assert_not_called()

    def test_preflight_blocks_when_persistent_volume_missing(self):
        info = sample()
        info["Mounts"][0]["Source"] = "/path/that/does/not/exist"
        with patch.object(mw, "inspect", return_value=info), \
             patch.object(mw, "check_image_defaults"), \
             patch.object(mw, "docker") as docker:
            with self.assertRaisesRegex(RuntimeError, "persistent data volume unavailable"):
                mw.preflight()
            docker.assert_not_called()

    def test_same_image_is_noop(self):
        original = sample()
        with patch.object(mw, "active_wolf_apps", return_value=[]), \
             patch.object(mw, "inspect", return_value=original), \
             patch.object(mw, "check_image_defaults"), \
             patch.object(mw, "docker") as docker:
            docker.side_effect = ["", '[{"Id": "sha256:old"}]']
            mw.update()
            self.assertEqual(docker.call_args_list[0].args, ("pull", mw.IMAGE))
            self.assertFalse(any(call.args[0] in ("stop", "rename", "rm")
                                 for call in docker.call_args_list))

    def test_successful_update_only_touches_moonlightweb(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("MW_HTTPS_PORT=8443\n")
            old = sample()
            old["Mounts"][0]["Source"] = directory
            def fake_docker(*args):
                if args[:2] == ("image", "inspect"):
                    return '[{"Id": "sha256:new"}]'
                return ""
            with patch.object(mw, "active_wolf_apps", return_value=[]), \
                 patch.object(mw, "inspect", return_value=old), \
                 patch.object(mw, "check_image_defaults"), \
                 patch.object(mw, "docker", side_effect=fake_docker) as docker, \
                 patch.object(mw, "save_backup", return_value=("teststamp", Path(directory) / "backup.tar.gz")), \
                 patch.object(mw, "write_private_env", return_value=env_file), \
                 patch.object(mw, "verify") as verify, \
                 patch.object(mw.subprocess, "run") as process:
                mw.update()
                verify.assert_called_once_with()
                commands = [call.args for call in docker.call_args_list]
                self.assertIn(("stop", "--time", "20", "moonlightweb"), commands)
                self.assertIn(("rename", "moonlightweb", "moonlightweb-preupdate-teststamp"), commands)
                self.assertIn(("start", "moonlightweb"), commands)
                self.assertFalse(any("wolf" in arg.lower() for command in commands for arg in command))
                create = process.call_args.args[0]
                self.assertEqual(create[-1], "sha256:new")
                self.assertIn("moonlightweb-test-data:/data:z", create)
                self.assertNotIn("MW_HTTPS_PORT=8443", create)

    def test_failed_update_restores_old_container_without_deleting_volume(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("MW_HTTPS_PORT=8443\n")
            old = sample()
            old["Mounts"][0]["Source"] = directory
            def fake_docker(*args):
                if args[:2] == ("image", "inspect"):
                    return '[{"Id": "sha256:new"}]'
                return ""
            with patch.object(mw, "active_wolf_apps", return_value=[]), \
                 patch.object(mw, "inspect", side_effect=[
                     old, {"Id": "sha256:replacement-container"}]), \
                 patch.object(mw, "check_image_defaults"), \
                 patch.object(mw, "docker", side_effect=fake_docker) as docker, \
                 patch.object(mw, "save_backup", return_value=("teststamp", Path(directory) / "backup.tar.gz")), \
                 patch.object(mw, "write_private_env", return_value=env_file), \
                 patch.object(mw, "verify", side_effect=RuntimeError("backend failed")), \
                 patch.object(mw.subprocess, "run"):
                with self.assertRaisesRegex(RuntimeError, "backend failed"):
                    mw.update()
                commands = [call.args for call in docker.call_args_list]
                self.assertIn(("rm", "-f", "moonlightweb"), commands)
                self.assertIn(("rename", "moonlightweb-preupdate-teststamp", "moonlightweb"), commands)
                self.assertIn(("update", "--restart=unless-stopped", "moonlightweb"), commands)
                self.assertIn(("start", "moonlightweb"), commands)
                self.assertFalse(any(command[0] in ("volume", "rmi") for command in commands))

    def test_partial_create_failure_cleans_replacement_before_rollback(self):
        from tempfile import TemporaryDirectory
        import subprocess
        with TemporaryDirectory() as directory:
            old = sample()
            old["Mounts"][0]["Source"] = directory
            env_file = Path(directory) / ".env"
            env_file.write_text("TZ=Asia/Tokyo\n")
            def fake_docker(*args):
                if args[:2] == ("image", "inspect"):
                    return '[{"Id": "sha256:new"}]'
                return ""
            with patch.object(mw, "active_wolf_apps", return_value=[]), \
                 patch.object(mw, "inspect", side_effect=[
                     old, {"Id": "sha256:replacement-container"}]), \
                 patch.object(mw, "check_image_defaults"), \
                 patch.object(mw, "docker", side_effect=fake_docker) as docker, \
                 patch.object(mw, "save_backup", return_value=("teststamp", Path(directory) / "backup")), \
                 patch.object(mw, "write_private_env", return_value=env_file), \
                 patch.object(mw.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "docker create")):
                with self.assertRaises(subprocess.CalledProcessError):
                    mw.update()
                commands = [call.args for call in docker.call_args_list]
                self.assertIn(("rm", "-f", "moonlightweb"), commands)
                self.assertIn(("rename", "moonlightweb-preupdate-teststamp", "moonlightweb"), commands)
                self.assertIn(("start", "moonlightweb"), commands)
                self.assertFalse(any(command[0] == "volume" for command in commands))

    def test_status_does_not_print_secrets(self):
        with patch.object(mw, "inspect", return_value=sample()), \
             patch.object(mw, "active_wolf_apps", return_value=[]), \
             patch("builtins.print") as printing:
            mw.status()
            lines = " ".join(" ".join(str(x) for x in call.args)
                             for call in printing.call_args_list)
            self.assertIn("moonlightweb-test-data", lines)
            self.assertNotIn("Access PIN", lines)


if __name__ == "__main__":
    unittest.main()
