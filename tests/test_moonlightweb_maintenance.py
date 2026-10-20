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
