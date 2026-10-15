"""Unit tests for Wolf driver-maintenance configuration reconstruction."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "server" / "wolf-driver-maintenance.py"
spec = importlib.util.spec_from_file_location("wolf_maintenance", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WolfMaintenanceTests(unittest.TestCase):
    def sample(self):
        return {
            "Image": "sha256:deadbeef",
            "Config": {"Env": [
                "HOST_APPS_STATE_FOLDER=/etc/wolf",
                "NVIDIA_DRIVER_VOLUME_NAME=wolf-nvidia-driver-595.84",
            ]},
            "HostConfig": {
                "NetworkMode": "host", "Privileged": False,
                "Binds": None, "Mounts": None,
                "CapAdd": None, "SecurityOpt": None,
                "RestartPolicy": {"Name": "unless-stopped"},
                "Devices": [{"PathOnHost": "/dev/dri",
                             "PathInContainer": "/dev/dri",
                             "CgroupPermissions": "rwm"}],
            },
            "Mounts": [
                {"Type": "bind", "Source": "/etc/wolf",
                 "Destination": "/etc/wolf", "RW": True},
                {"Type": "volume", "Name": "session-volume",
                 "Destination": "/run/user/wolf", "RW": True},
                {"Type": "volume", "Name": "wolf-nvidia-driver-595.84",
                 "Destination": "/usr/nvidia", "RW": True},
            ],
        }

    def test_recreate_preserves_state_and_image(self):
        args = module.recreate_args(self.sample(), "wolf-nvidia-driver-595.104.02")
        self.assertIn("/etc/wolf:/etc/wolf", args)
        self.assertIn("session-volume:/run/user/wolf", args)
        self.assertIn("wolf-nvidia-driver-595.104.02:/usr/nvidia", args)
        self.assertIn("NVIDIA_DRIVER_VOLUME_NAME=wolf-nvidia-driver-595.104.02", args)
        self.assertIn("sha256:deadbeef", args)
        self.assertNotIn("wolf-nvidia-driver-595.84:/usr/nvidia", args)

    def test_reject_unknown_host_settings(self):
        info = self.sample()
        info["HostConfig"]["SecurityOpt"] = ["label=disable"]
        with self.assertRaises(RuntimeError):
            module.recreate_args(info, "wolf-nvidia-driver-595.104.02")

    def test_validates_driver_versions(self):
        with self.assertRaises(RuntimeError):
            module.recreate_args({**self.sample(), "HostConfig": {
                **self.sample()["HostConfig"], "NetworkMode": "bridge",
            }}, "wolf-nvidia-driver-595.104.02")


if __name__ == "__main__":
    unittest.main()
