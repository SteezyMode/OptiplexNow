"""Contract and fail-closed tests for the non-executable Host Plan preview."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server"))
import host_plan  # noqa: E402
import host_preflight  # noqa: E402


def report(**overrides):
    """Synthetic preflight output representing one candidate clean host."""
    details = {
        "architecture": "pass",
        "operating_system": "pass",
        "gpu_detection": "pass",
        "hardware_encoder": "unknown",
        "nvidia_driver": "pass",
        "nvidia_drm_modeset": "pass",
        "virtual_controller_devices": "pass",
        "udev": "pass",
        "container_runtime": "pass",
        "wolf_ports": "pass",
        "disk_space": "pass",
        "memory": "pass",
    }
    details.update(overrides)
    return {
        "tool": "now-host-preflight",
        "schema_version": host_preflight.SCHEMA_VERSION,
        "read_only": True,
        "verified_streaming": False,
        "overall": "unknown",
        "checks": [
            {"id": name, "status": state, "detail": "not retained in plan"}
            for name, state in details.items()
        ],
    }


def gates(plan):
    return {item["id"]: item for item in plan["gates"]}


class HostPlanTests(unittest.TestCase):
    def test_clean_snapshot_is_still_blocked_pending_verified_stream_and_image_pin(self):
        planned = host_plan.plan_from_preflight(report())
        self.assertFalse(planned["may_apply"])
        self.assertFalse(planned["changes_performed"])
        self.assertEqual(planned["decision"], "blocked")
        self.assertEqual(planned["mode"], "read_only_preview")
        self.assertEqual(planned["schema_version"], 1)
        self.assertEqual(gates(planned)["hardware_encoder"]["observation"], "unknown")
        self.assertEqual(gates(planned)["pinned_wolf_image"]["state"], "blocked")
        self.assertEqual(gates(planned)["owner_enrollment"]["state"], "blocked")
        self.assertEqual(gates(planned)["verified_gpu_stream"]["state"], "blocked")
        self.assertIsNone(planned["service_proposal"][0]["image_digest"])

    def test_known_live_host_requires_conflict_review_never_adoption(self):
        pop_host = report(operating_system="unknown", wolf_ports="attention",
                          nvidia_drm_modeset="unknown")
        planned = host_plan.plan_from_preflight(pop_host)
        self.assertFalse(planned["may_apply"])
        self.assertFalse(planned["ownership_proposal"]["adopt_unmanaged_containers"])
        self.assertFalse(planned["ownership_proposal"]["delete_existing_user_data"])
        self.assertEqual(gates(planned)["wolf_ports"]["reason_code"],
                         "conflict_or_missing_dependency")
        self.assertEqual(gates(planned)["operating_system"]["reason_code"],
                         "insufficient_evidence")
        self.assertIn("occupied", planned["note"].lower())
        # No incoming arbitrary descriptions are retained in plan JSON.
        self.assertNotIn("not retained in plan", json.dumps(planned))

    def test_unsupported_arch_never_overridden_by_clean_ports(self):
        planned = host_plan.plan_from_preflight(
            report(architecture="unsupported", wolf_ports="pass"))
        self.assertEqual(gates(planned)["architecture"]["reason_code"], "unsupported")
        self.assertFalse(planned["may_apply"])

    def test_hypothetical_all_pass_still_requires_hardware_and_security_gates(self):
        findings = report(**{check: "pass" for check in host_plan.REQUIRED_CHECKS})
        planned = host_plan.plan_from_preflight(findings)
        self.assertEqual(planned["decision"], "blocked")
        self.assertFalse(planned["may_apply"])
        self.assertFalse(planned["service_proposal"][0]["provisionable"])
        self.assertTrue(any(not phase.get("implemented", True)
                            for phase in planned["future_steps"]))

    def test_missing_or_duplicate_checks_fail_closed(self):
        omitted = report()
        omitted["checks"] = [x for x in omitted["checks"] if x["id"] != "wolf_ports"]
        planned = host_plan.plan_from_preflight(omitted)
        self.assertEqual(gates(planned)["wolf_ports"]["observation"], "unknown")
        duplicated = report()
        duplicated["checks"].append(duplicated["checks"][0].copy())
        with self.assertRaises(ValueError):
            host_plan.plan_from_preflight(duplicated)

    def test_reject_wrong_version_and_manipulated_contract(self):
        for changed in (
            {"schema_version": 999},
            {"tool": "some-unknown-scanner"},
            {"read_only": False},
            {"verified_streaming": True},
            {"checks": "pass"},
        ):
            candidate = report()
            candidate.update(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                host_plan.plan_from_preflight(candidate)
        malicious = report()
        malicious["checks"][0]["status"] = "super-ready"
        with self.assertRaises(ValueError):
            host_plan.plan_from_preflight(malicious)
        malicious = report()
        malicious["checks"][0]["id"] = "random_shell_command"
        with self.assertRaises(ValueError):
            host_plan.plan_from_preflight(malicious)

    def test_preview_has_no_secrets_and_uses_declared_namespaces(self):
        value = host_plan.plan_from_preflight(report())
        self.assertEqual(value["ownership_proposal"]["configuration_root"],
                         "/etc/optiplex-now/host")
        self.assertEqual(value["ownership_proposal"]["state_root"],
                         "/var/lib/optiplex-now/host")
        self.assertEqual({(x["port"], x["protocol"])
                          for x in value["service_proposal"][0]["ports"]},
                         {(47984, "tcp"), (47989, "tcp"), (48010, "tcp"),
                          (47999, "udp"), (48100, "udp"), (48200, "udp")})
        self.assertNotIn("password", json.dumps(value).lower())
        self.assertNotIn("SSH key", json.dumps(value))
        self.assertEqual(host_plan._render_text(value).splitlines()[0],
                         "NOW Host Installation Plan | BLOCKED | NO CHANGES")

    def test_cli_from_saved_preflight_and_non_mutating_behavior(self):
        with tempfile.TemporaryDirectory(prefix="now-host-plan-") as dirname:
            filename = Path(dirname) / "scan.json"
            filename.write_text(json.dumps(report(wolf_ports="attention")))
            before = filename.read_bytes()
            proc = subprocess.run(
                [sys.executable, str(REPO / "server/host_plan.py"),
                 "--preflight-json", str(filename), "--json"],
                capture_output=True, text=True, timeout=5, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertFalse(data["may_apply"])
            self.assertEqual(gates(data)["wolf_ports"]["observation"], "attention")
            self.assertEqual(filename.read_bytes(), before)

    def test_cli_rejects_garbage_and_oversized_inputs(self):
        with tempfile.TemporaryDirectory(prefix="now-host-plan-bad-") as dirname:
            filename = Path(dirname) / "bad.json"
            for content in ("{bad json", "A" * 65537,
                            json.dumps({"schema_version": 1})):
                filename.write_text(content)
                proc = subprocess.run(
                    [sys.executable, str(REPO / "server/host_plan.py"),
                     "--preflight-json", str(filename)],
                    capture_output=True, text=True, timeout=5, check=False)
                self.assertNotEqual(proc.returncode, 0)
                self.assertNotIn(content[:50], proc.stderr)
                self.assertEqual(filename.read_text(), content)


if __name__ == "__main__":
    unittest.main()
