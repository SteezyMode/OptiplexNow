"""Isolated GPU power contract tests; no GPU, SSH, LACT or host changes."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import gpu_power_host as gpu


SAMPLE = "GeForce RTX 3050, 18.3, 55.0, 35.0, 70.0, 54, 62, 1605, P2\n"


class GpuPowerTests(unittest.TestCase):
    def test_nvidia_cap_vs_max_and_detailed_readings(self):
        data = gpu.parse_gpu(SAMPLE)
        self.assertEqual((data["limit_w"], data["max_w"]), (55.0, 70.0))
        self.assertEqual((data["draw_w"], data["temp_c"], data["pstate"]),
                         (18.3, 54.0, "P2"))

    def test_gpu_probe_rejects_ambiguous_or_invalid_hardware(self):
        for output in ("", "N/A\n", SAMPLE + SAMPLE,
                       SAMPLE.replace("55.0", "-1")):
            with self.subTest(output=output), self.assertRaises(gpu.GpuPowerError):
                gpu.parse_gpu(output)

    def test_gpu_monitoring_remains_read_only_when_maximum_unavailable(self):
        details = gpu.parse_gpu(SAMPLE.replace("70.0", "N/A"))
        self.assertEqual(details["limit_w"], 55.0)
        self.assertIsNone(details["max_w"])
        self.assertIsNone(details["min_w"])

    def test_power_limits_reject_invalid_requests_before_lact(self):
        requested = []
        def call(name, args=None):
            requested.append((name, args))
            return None
        for watts in (False, 0, 34, 71, 1001, 55.5, "55", None):
            with self.subTest(watts=watts), self.assertRaises(gpu.GpuPowerError):
                gpu.set_cap(watts, probe=lambda:gpu.parse_gpu(SAMPLE), call=call)
        self.assertEqual(requested, [])

    def test_owner_power_change_preserves_fan_config_and_confirms(self):
        requests = []
        def call(name, args=None):
            requests.append((name, args))
            if name == "list_devices":
                return [{"id": "10DE:25FA-0000:0000-0000:01:00.0"}]
            if name == "get_gpu_config":
                return {"power_cap": None, "fan_control_enabled": True,
                        "fan_control_settings": {"mode": "curve"}}
            if name in ("set_gpu_config", "confirm_pending_config"):
                return None
            self.fail("Unexpected RPC method")
        readings = iter((55.0, 65.0))
        def probe():
            data = gpu.parse_gpu(SAMPLE)
            data["limit_w"] = next(readings)
            return data
        result = gpu.set_cap(65, probe=probe, call=call)
        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(result["applied_w"], 65.0)
        self.assertEqual([item[0] for item in requests],
                         ["list_devices", "get_gpu_config",
                          "set_gpu_config", "confirm_pending_config"])
        payload = requests[2][1]["config"]
        self.assertEqual(payload["power_cap"], 65.0)
        self.assertEqual(payload["fan_control_settings"], {"mode": "curve"})

    def test_lact_confirmation_without_nvidia_readback_is_not_success(self):
        """A successful LACT reply can still fail to apply the NVIDIA cap."""
        calls = []
        def call(name, args=None):
            calls.append(name)
            if name == "list_devices":
                return [{"id": "10DE:25FA-0000:0000-0000:01:00.0"}]
            if name == "get_gpu_config":
                return {"power_cap": 55.0}
            return None
        with self.assertRaisesRegex(gpu.GpuPowerError, "NVIDIA did not report"):
            gpu.set_cap(65, probe=lambda:gpu.parse_gpu(SAMPLE), call=call)
        self.assertEqual(calls, ["list_devices", "get_gpu_config",
                                 "set_gpu_config", "confirm_pending_config"])

    def test_driver_readback_allows_nvidia_rounding_within_one_watt(self):
        readings = iter((55.0, 64.5))
        def probe():
            data = gpu.parse_gpu(SAMPLE)
            data["limit_w"] = next(readings)
            return data
        def call(name, args=None):
            if name == "list_devices":
                return [{"id": "10DE:25FA-0000:0000-0000:01:00.0"}]
            if name == "get_gpu_config":
                return {"power_cap": 55.0}
            return None
        result = gpu.set_cap(65, probe=probe, call=call)
        self.assertEqual(result["applied_w"], 64.5)

    def test_mutation_failure_never_confirms_or_retries(self):
        seen = []
        def call(name, args=None):
            seen.append(name)
            if name == "list_devices":
                return [{"id": "10DE:25FA-0000:0000-0000:01:00.0"}]
            if name == "get_gpu_config":
                return {"power_cap": 55.0}
            raise gpu.GpuPowerError("GPU refused change")
        with self.assertRaises(gpu.GpuPowerError):
            gpu.set_cap(60, probe=lambda:gpu.parse_gpu(SAMPLE), call=call)
        self.assertEqual(seen, ["list_devices", "get_gpu_config", "set_gpu_config"])

    def test_only_one_nvidia_device_is_accepted(self):
        def call(_):
            return [{"id": "10DE:1"}, {"id": "10DE:2"}]
        with self.assertRaises(gpu.GpuPowerError):
            gpu.gpu_id(call)

    def test_read_only_monitoring_remains_available_without_lact(self):
        def unavailable(*args, **kwargs):
            raise gpu.GpuPowerError("No LACT permission")
        result = gpu.inspect(probe=lambda:gpu.parse_gpu(SAMPLE),call=unavailable)
        self.assertTrue(result["success"])
        self.assertFalse(result["control_available"])
        self.assertEqual(result["limit_w"], 55.0)

    def test_rpc_json_newline_and_response_boundary(self):
        class FakeSocket:
            def __init__(self):
                self.sent = b""
                self.closed = False
            def settimeout(self, _): pass
            def connect(self, path): self.path = path
            def sendall(self, data): self.sent += data
            def recv(self, _): return b'{"status":"ok","data":[{"id":"10DE:1234"}]}\n'
            def close(self): self.closed = True
        sock = FakeSocket()
        result = gpu.rpc("list_devices", socket_factory=lambda *args: sock)
        self.assertEqual(result, [{"id": "10DE:1234"}])
        self.assertTrue(sock.closed)
        self.assertEqual(json.loads(sock.sent), {"command":"list_devices"})
        self.assertEqual(sock.path, "/run/lactd.sock")

    def test_no_arbitrary_actions(self):
        for args in (["clock", "1200"], ["set", "5;rm"], ["set", "nan"],
                     ["set", "55", "extra"]):
            with self.subTest(args=args), self.assertRaises(gpu.GpuPowerError):
                gpu.handle(args, probe=lambda:None, call=lambda *args:None)


if __name__ == "__main__":
    unittest.main()
