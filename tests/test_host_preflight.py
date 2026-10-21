"""Offline NOW Host preflight tests. Never inspects a real Docker daemon or Wolf host."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server"))
import host_preflight as preflight  # noqa: E402


def snapshot(**overrides):
    defaults = {
        "os_id": "ubuntu", "os_version": "24.04", "architecture": "x86_64",
        "gpu_vendors": ["Intel"], "render_nodes": ["renderD128"],
        "nvidia_node": False, "nvidia_driver": "", "nvidia_drm_modeset": "",
        "controller_devices": {"uinput": True, "uhid": True}, "udev_present": True,
        "docker_cli": True, "docker_socket": True, "docker_version": "27.1.1",
        "port_reads": {"tcp": [], "tcp6": [], "udp": [], "udp6": []},
        "disk_free_bytes": 32 * 1024**3,
        "memory_available_bytes": 8 * 1024**3,
    }
    defaults.update(overrides)
    return defaults


def by_id(report):
    return {item["id"]: item for item in report["checks"]}


class HostPreflightTests(unittest.TestCase):
    def test_healthy_inventory_is_not_a_streaming_certificate(self):
        result = preflight.evaluate(snapshot())
        checks = by_id(result)
        self.assertEqual(result["overall"], "unknown")
        self.assertFalse(result["verified_streaming"])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(checks["hardware_encoder"]["status"], "unknown")
        self.assertEqual(checks["wolf_ports"]["status"], "pass")
        self.assertEqual(checks["container_runtime"]["status"], "pass")
        self.assertEqual(checks["operating_system"]["status"], "pass")

    def test_other_distributions_unknown_not_automatically_rejected(self):
        result = preflight.evaluate(snapshot(os_id="fedora", os_version="42"))
        self.assertEqual(by_id(result)["operating_system"]["status"], "unknown")
        self.assertEqual(result["overall"], "unknown")

    def test_wrong_architecture_is_unsupported(self):
        result = preflight.evaluate(snapshot(architecture="aarch64", docker_version=None))
        self.assertEqual(result["overall"], "unsupported")
        self.assertEqual(by_id(result)["architecture"]["status"], "unsupported")

    def test_nvidia_bad_driver_and_modeset_are_actionable(self):
        report = preflight.evaluate(snapshot(
            gpu_vendors=["NVIDIA"], nvidia_node=True, nvidia_driver="525.147.05",
            nvidia_drm_modeset="N", controller_devices={"uinput": True, "uhid": False}))
        checks = by_id(report)
        self.assertEqual(report["overall"], "requires_attention")
        self.assertEqual(checks["nvidia_driver"]["status"], "attention")
        self.assertEqual(checks["nvidia_drm_modeset"]["status"], "attention")
        self.assertEqual(checks["virtual_controller_devices"]["status"], "attention")

    def test_driver_version_comparison(self):
        self.assertEqual(preflight.driver_version("550.40.07\n"), (550, 40, 7))
        self.assertEqual(preflight.driver_version("530.30"), (530, 30, 0))
        self.assertIsNone(preflight.driver_version("error loading module"))
        report = preflight.evaluate(snapshot(gpu_vendors=["NVIDIA"],
                                             nvidia_driver="550.40.07", nvidia_drm_modeset="Y"))
        self.assertEqual(by_id(report)["nvidia_driver"]["status"], "pass")

    def test_no_gpu_or_render_node_does_not_claim_compatibility(self):
        report = preflight.evaluate(snapshot(gpu_vendors=[], render_nodes=[]))
        self.assertEqual(by_id(report)["gpu_detection"]["status"], "attention")
        self.assertEqual(report["overall"], "requires_attention")

    def test_missing_daemon_permission_storage_and_memory(self):
        report = preflight.evaluate(snapshot(
            docker_version=None, disk_free_bytes=3 * 1024**3,
            memory_available_bytes=500 * 1024**2, udev_present=False))
        checks = by_id(report)
        self.assertEqual(checks["container_runtime"]["status"], "attention")
        self.assertEqual(checks["disk_space"]["status"], "attention")
        self.assertEqual(checks["memory"]["status"], "attention")
        self.assertEqual(checks["udev"]["status"], "attention")

    def test_port_parser_only_counts_tcp_listeners_and_binds_udp(self):
        tcp = ("  sl  local_address rem_address   st\n"
               "  0: 00000000:BB70 00000000:0000 0A\n"  # 47984
               "  1: 0100007F:BB75 00000000:0000 01\n")
        udp = ("  sl  local_address rem_address st\n"
               "  0: 00000000:BB7F 00000000:0000 07\n")  # 47999
        self.assertEqual(preflight.parse_bound_ports(tcp, "tcp"), {47984})
        self.assertEqual(preflight.parse_bound_ports(udp, "udp"), {47999})
        self.assertIsNone(preflight.parse_bound_ports(None, "tcp"))
        report = preflight.evaluate(snapshot(port_reads={
            "tcp": [47984], "tcp6": [], "udp": [], "udp6": [47999]}))
        self.assertEqual(by_id(report)["wolf_ports"]["status"], "attention")
        self.assertIn("47984/tcp", by_id(report)["wolf_ports"]["detail"])
        self.assertIn("47999/udp", by_id(report)["wolf_ports"]["detail"])

    def test_missing_socket_tables_are_unknown(self):
        report = preflight.evaluate(snapshot(port_reads={
            "tcp": [], "tcp6": None, "udp": [], "udp6": []}))
        self.assertEqual(by_id(report)["wolf_ports"]["status"], "unknown")

    def test_os_release_parser_bounds_and_missing_data(self):
        parsed = preflight.parse_os_release(
            'NAME="Ubuntu Linux"\nID=ubuntu\nVERSION_ID="24.04"\nID_LIKE="debian"\n'
            'INVALID key=bad\n# comment\n')
        self.assertEqual(parsed["NAME"], "Ubuntu Linux")
        self.assertEqual(parsed["VERSION_ID"], "24.04")
        self.assertNotIn("INVALID key", parsed)
        self.assertEqual(preflight.parse_mem_available("MemAvailable: 4096 kB\n"), 4096 * 1024)
        self.assertIsNone(preflight.parse_mem_available("MemTotal: 8192 kB\n"))

    def test_collection_reads_only_disposable_fixture(self):
        with tempfile.TemporaryDirectory(prefix="now-preflight-") as temp:
            root = Path(temp)

            def put(relative, text):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)

            put("etc/os-release", 'ID=ubuntu\nVERSION_ID="24.04"\n')
            put("proc/meminfo", "MemAvailable: 8123456 kB\n")
            put("sys/bus/pci/devices/0000:01:00.0/class", "0x030000\n")
            put("sys/bus/pci/devices/0000:01:00.0/vendor", "0x10de\n")
            put("sys/module/nvidia/version", "550.40.07\n")
            put("sys/module/nvidia_drm/parameters/modeset", "Y\n")
            put("dev/dri/renderD128", "")
            put("dev/uinput", "")
            put("dev/uhid", "")
            (root / "run/udev").mkdir(parents=True)
            put("proc/net/tcp", "  sl local_address rem_address st\n"
                                "  0: 00000000:BB70 00000000:0000 0A\n")
            put("proc/net/tcp6", "  sl local_address rem_address st\n")
            put("proc/net/udp", "  sl local_address rem_address st\n")
            put("proc/net/udp6", "  sl local_address rem_address st\n")
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = preflight.collect_snapshot(root, machine="x86_64", check_docker=False)
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(result["gpu_vendors"], ["NVIDIA"])
            self.assertEqual(result["render_nodes"], ["renderD128"])
            self.assertEqual(result["port_reads"]["tcp"], [47984])
            self.assertIsNone(result["docker_version"])
            self.assertEqual(result["memory_available_bytes"], 8123456 * 1024)
            self.assertEqual(by_id(preflight.evaluate(result))["wolf_ports"]["status"], "attention")
            self.assertNotIn("hostname", json.dumps(preflight.evaluate(result)))
            self.assertNotIn("ssh", json.dumps(preflight.evaluate(result)))

    def test_pop_os_24_04_is_candidate_not_stream_verified(self):
        report = preflight.evaluate(snapshot(
            os_id="pop", os_version="24.04",
            gpu_vendors=["Intel"], render_nodes=["renderD128"]))
        checks = by_id(report)
        self.assertEqual(checks["operating_system"]["status"], "pass")
        self.assertIn("Pop!_OS", checks["operating_system"]["detail"])
        self.assertEqual(checks["hardware_encoder"]["status"], "unknown")
        self.assertFalse(report["verified_streaming"])

    def test_cli_json_contract_and_no_privileged_actions(self):
        process = subprocess.run(
            [sys.executable, str(REPO / "server/host_preflight.py"), "--json"],
            capture_output=True, text=True, timeout=8, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["schema_version"], 1)
        self.assertTrue(report["read_only"])
        self.assertFalse(report["verified_streaming"])
        self.assertIn(report["overall"], {"unsupported", "requires_attention", "unknown"})
        self.assertEqual({item["status"] for item in report["checks"]}
                         - {"pass", "attention", "unsupported", "unknown"}, set())


if __name__ == "__main__":
    unittest.main()
