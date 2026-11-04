"""Offline checks for the safe, persistent DroppedNeedle host repair."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/music/install_discover_hotfix.py"
spec = importlib.util.spec_from_file_location("bruiser_discover_hotfix", SCRIPT)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class DiscoverPersistentTests(unittest.TestCase):
    BASE = """from infrastructure.observability.optional_work import OptionalWorkDeferred, optional_work_budget, optional_dispatch_guard

def warm():
    with optional_work_budget(), optional_dispatch_guard(lambda: True):
        pass
"""

    def test_patch_only_the_discover_budget(self):
        patched = repair.make_patch(self.BASE)
        self.assertIn("OptionalWorkBudget(remaining=64)", patched)
        self.assertIn("import OptionalWorkBudget, OptionalWorkDeferred", patched)
        self.assertNotIn("with optional_work_budget(),", patched)
        self.assertIn("def warm():", patched)

    def test_drift_fails_closed(self):
        for source in ("", "with optional_work_budget():", self.BASE + self.BASE):
            with self.assertRaises(repair.RepairError):
                repair.make_patch(source)

    def test_compose_write_changes_only_target_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compose.json"
            original = {
                "services": {
                    "gluetun": {"image": "qmcgaw/gluetun:v3.41", "restart": "unless-stopped"},
                    "droppedneedle": {
                        "image": "droppedneedle/droppedneedle:latest",
                        "volumes": ["/mnt/2TB:/data", "./config:/app/config"],
                        "environment": {"BASE_PATH": ""},
                    },
                    "slskd": {"image": "slskd/slskd:0.25.1"},
                },
            }
            path.write_text(json.dumps(original), encoding="utf8")
            new = repair.load_compose(path)
            new["services"]["droppedneedle"]["image"] = "bruiser/droppedneedle-discover:123-b64-v1"
            repair.write_compose_atomic(path, new)
            actual = repair.load_compose(path)
            self.assertEqual(actual, new)
            restored = json.loads(path.read_text())
            restored["services"]["droppedneedle"]["image"] = "droppedneedle/droppedneedle:latest"
            self.assertEqual(restored, original)

    def test_required_mount_fingerprint(self):
        data = {"Mounts": [
            {"Type": "bind", "Source": "/mnt/2TB", "Destination": "/data", "RW": True},
            {"Type": "bind", "Source": "/host/config", "Destination": "/app/config", "RW": True},
        ]}
        self.assertEqual(repair.mount_fingerprint(data), [
            ("bind", "/host/config", "/app/config", True),
            ("bind", "/mnt/2TB", "/data", True),
        ])


if __name__ == "__main__":
    unittest.main()
