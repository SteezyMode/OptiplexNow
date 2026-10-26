"""Host Setup read-only service-review boundaries (no privileged CI run)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / "src/host_setup.c").read_text(encoding="utf-8")
INVENTORY = (ROOT / "server/host_services.py").read_text(encoding="utf-8")
PLANNER = (ROOT / "server/host_adoption.py").read_text(encoding="utf-8")


class HostServiceApprovalContract(unittest.TestCase):
    def test_ordinary_host_review_never_invokes_os_elevation(self):
        body = GUI.split("static void run_read_only_step(HostSetupUI *ui)\n{",1)[1].split(
            "static void on_check_clicked(", 1)[0]
        self.assertIn('"/usr/bin/python3", script,', body)
        self.assertIn('ui->step == 4 ? "--detect-target" :', body)
        self.assertIn('ui->step == 5 ? "--check" : NULL', body)
        self.assertIn('ui->step == 4 ? INSTALLER : DEPENDENCIES', body)
        self.assertNotIn("pkexec", body)
        self.assertNotIn('"--install"', body)

    def test_privileged_service_inventory_requires_separate_click(self):
        fn = GUI.split("static void on_verify_services(",1)[1].split(
            "static void on_window_destroy(",1)[0]
        self.assertIn('"/usr/bin/pkexec", "/usr/bin/python3", ADOPTION, NULL',fn)
        self.assertIn('if (ui->running || ui->installing || ui->closing)',fn)
        self.assertIn('G_CALLBACK(on_verify_services)',GUI)
        self.assertIn("VERIFY EXISTING SERVICES (OS APPROVAL)",GUI)

    def test_service_review_is_read_only_and_fixed_local_socket(self):
        self.assertIn('"/usr/bin/docker", "--host", "unix:///var/run/docker.sock"',INVENTORY)
        self.assertIn('"DOCKER_CONFIG": "/nonexistent/now-host-docker-config"',INVENTORY)
        self.assertNotIn("docker run", INVENTORY)
        self.assertIn('"may_adopt": False', PLANNER)
        self.assertIn('"may_install": False', PLANNER)
        self.assertIn('"changes_performed": False', PLANNER)


if __name__ == "__main__":
    unittest.main()
