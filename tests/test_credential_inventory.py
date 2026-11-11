"""Contract tests for the deliberately non-secret service/credential inventory."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import credential_inventory as audit


class CredentialInventoryTests(unittest.TestCase):
    def test_catalog_is_structured_unique_and_has_clear_limits(self):
        entries = audit.report()["entries"]
        self.assertGreaterEqual(len(entries), 18)
        ids = [e["id"] for e in entries]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(audit.report()["secret_values_collected"], False)
        for entry in entries:
            for field in ("id", "system", "kind", "authority", "consumer",
                          "recommended_storage", "intended_experience", "recovery",
                          "applies_if"):
                self.assertTrue(entry[field], (entry["id"], field))
            self.assertEqual(entry["runtime_hint"], "not checked")

    def test_default_scan_does_not_invoke_docker_or_other_tools(self):
        def forbidden(*args, **kwargs):
            self.fail("A metadata-only catalog must not touch local services.")
        report = audit.report(runner=forbidden)
        self.assertFalse(report["host_check_requested"])
        self.assertEqual(report["entries"][0]["runtime_hint"], "not checked")

    def test_opt_in_host_probe_never_fetches_env_or_docker_inspection(self):
        calls = []
        def fake_runner(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(
                args, 0,
                stdout="qbittorrent-vpn\nsublarr-pilot\n"
                       "droppedneedle-password-hunter2\n"
                       "gluetun\nslskd-vpn\n")
        result = audit.report(host_check=True, runner=fake_runner)
        self.assertEqual(len(calls), 1)
        argv, kwargs = calls[0]
        self.assertEqual(argv, ["docker", "ps", "--format", "{{.Names}}"])
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
        self.assertTrue(kwargs["text"])
        self.assertFalse(kwargs["check"])
        self.assertLessEqual(kwargs["timeout"], 5)
        self.assertNotIn("inspect", " ".join(argv))
        output = json.dumps(result)
        self.assertNotIn("hunter2", output)
        self.assertNotIn("droppedneedle-password", output)
        self.assertNotIn("qbittorrent-vpn", output)
        self.assertNotIn("sublarr-pilot", output)
        systems = {x["system"]: x["runtime_hint"] for x in result["entries"]}
        self.assertIn("matched", systems["Gluetun"])
        self.assertIn("matched", systems["DroppedNeedle"])
        self.assertIn("matched", systems["qBittorrent + VueTorrent"])
        self.assertIn("matched", systems["SubHub/Sublarr"])
        self.assertIn("matched", systems["slskd"])

    def test_docker_permission_failure_is_unknown_not_absent(self):
        def inaccessible(args, **kwargs):
            return subprocess.CompletedProcess(args, 1, stdout="", stderr=None)
        result = audit.report(host_check=True, runner=inaccessible)
        for entry in result["entries"]:
            self.assertEqual(entry["runtime_hint"],
                             "not checked / Docker unavailable")
        def nonexistent(*args, **kwargs):
            raise FileNotFoundError("docker missing")
        result = audit.report(host_check=True, runner=nonexistent)
        self.assertTrue(all(
            e["runtime_hint"] == "not checked / Docker unavailable"
            for e in result["entries"]))

    def test_nonmatching_docker_name_cannot_claim_account_absence(self):
        def unrelated(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout="unrelated\n")
        result = audit.report(host_check=True, runner=unrelated)
        status = next(x["runtime_hint"] for x in result["entries"]
                      if x["system"] == "DroppedNeedle")
        self.assertEqual(status, "not detected among running Docker names")
        self.assertNotIn("absent", status)

    def test_default_cli_is_read_only_and_never_prints_secret_values(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(audit.main([]), 0)
        output = buffer.getvalue()
        self.assertIn("non-secret credential catalog", output)
        self.assertIn("No passwords", output)
        self.assertIn("credential categories cataloged", output)
        self.assertNotIn("test-value-should-not-appear", output)


if __name__ == "__main__":
    unittest.main()
