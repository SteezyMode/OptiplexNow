"""Read-only and privilege-guarded Docker dependency installer tests.

Tests mock all system package commands. NEVER invoke real apt installation.
"""
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
import host_dependencies as deps  # noqa: E402


SIMULATED = (
    "Reading package lists...\n"
    "The following NEW packages will be installed:\n"
    "Inst containerd (1.0 Ubuntu:24.04/noble [amd64])\n"
    "Inst docker.io (29.0 Ubuntu:24.04/noble [amd64])\n"
    "Inst docker-compose-v2 (2.40 Ubuntu:24.04/noble [amd64])\n"
    "Conf docker.io (29.0 Ubuntu:24.04/noble [amd64])\n"
)


class HostDependenciesTests(unittest.TestCase):
    def test_simulation_allows_additive_distro_packages_only(self):
        with mock.patch.object(deps, "command", return_value=SIMULATED) as run:
            deps.simulate()
        self.assertEqual(run.call_args.args[0],
                         [deps.APT, "--simulate", "--no-remove",
                          "--no-install-recommends", "install", *deps.PACKAGES])

    def test_simulation_rejects_removal_upgrade_or_partial_plan(self):
        bad = (
            SIMULATED + "Remv docker-ce [5:29]\n",
            SIMULATED + "Inst libc6 [2.39] (2.40 Ubuntu:24.04/noble [amd64])\n",
            SIMULATED.replace("Inst docker-compose-v2 ", "Keep docker-compose-v2 "),
            "",
        )
        for plan in bad:
            with self.subTest(plan=plan[:40]), \
                 mock.patch.object(deps, "command", return_value=plan), \
                 self.assertRaises(deps.DependencyError):
                deps.simulate()

    def test_existing_or_unrecognized_hosts_are_not_installable(self):
        with mock.patch.object(deps, "clean_candidate",
                               return_value=(False, "runtime exists")), \
             mock.patch.object(deps, "simulate",
                               side_effect=AssertionError("Must not simulate")):
            report = deps.inspect()
        self.assertEqual(report["state"], "existing_or_unsupported")
        self.assertFalse(report["installable"])
        self.assertFalse(report["changes_performed"])

    def test_fresh_host_reports_reviewable_plan_without_changes(self):
        with mock.patch.object(deps, "clean_candidate", return_value=(True, "")), \
             mock.patch.object(deps, "simulate") as run:
            report = deps.inspect()
        self.assertTrue(report["installable"])
        self.assertEqual(report["packages"], ["docker.io", "docker-compose-v2"])
        self.assertFalse(report["changes_performed"])
        run.assert_called_once()

    def test_read_only_check_blocks_failed_simulation(self):
        with mock.patch.object(deps, "clean_candidate", return_value=(True, "")), \
             mock.patch.object(deps, "simulate", side_effect=deps.DependencyError("APT blocked")):
            report = deps.inspect()
        self.assertEqual(report["state"], "package_plan_blocked")
        self.assertFalse(report["installable"])

    def test_root_and_explicit_confirmation_before_changes(self):
        with mock.patch.object(deps.os, "geteuid", return_value=1000), \
             mock.patch.object(deps, "inspect",
                               side_effect=AssertionError("Inspected unexpectedly")):
            with self.assertRaisesRegex(deps.DependencyError, "Root authorization"):
                deps.install("INSTALL-DOCKER")
        with mock.patch.object(deps.os, "geteuid", return_value=0), \
             mock.patch.object(deps, "inspect",
                               side_effect=AssertionError("Inspected unexpectedly")):
            with self.assertRaisesRegex(deps.DependencyError, "approval"):
                deps.install("")

    def test_clean_host_must_be_rechecked_as_root_before_apt(self):
        with mock.patch.object(deps.os, "geteuid", return_value=0), \
             mock.patch.object(deps.os, "open", return_value=3), \
             mock.patch.object(deps.os, "close"), \
             mock.patch.object(deps.fcntl, "flock"), \
             mock.patch.object(deps, "inspect",
                               return_value={"installable": False,
                                             "reason": "Existing runtime"}), \
             mock.patch.object(deps, "command",
                               side_effect=AssertionError("APT invoked")):
            with self.assertRaisesRegex(deps.DependencyError, "Existing runtime"):
                deps.install("INSTALL-DOCKER")

    def test_package_action_uses_fixed_apt_command_not_shell(self):
        import inspect
        source = inspect.getsource(deps.install)
        self.assertIn('command([APT, "--yes", "--no-remove", "--no-install-recommends"', source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("apt-get update", source)
        self.assertNotIn("usermod", source)

    def test_cli_check_returns_json_without_root_or_apt_mutation(self):
        import contextlib
        import io
        output = io.StringIO()
        with mock.patch.object(deps.sys, "argv", ["host_dependencies.py", "--check"]), \
             mock.patch.object(deps, "inspect",
                               return_value={"state": "existing_or_unsupported",
                                             "installable": False,
                                             "changes_performed": False}), \
             contextlib.redirect_stdout(output):
            self.assertEqual(deps.main(), 0)
        self.assertIn('"installable": false', output.getvalue())


if __name__ == "__main__":
    unittest.main()
