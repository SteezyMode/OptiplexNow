"""Never allow the real-Wolf probe to inspect a production Wolf container."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
mod_path = ROOT / "server" / "probe_real_wolf.py"
spec = importlib.util.spec_from_file_location("now_real_wolf_probe", mod_path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def safe_info():
    return {
        "Name": "/now-wolf-compat-test01",
        "Config": {"Labels": {"io.optiplex-now.compat-disposable": "true"}},
        "HostConfig": {"NetworkMode": "none", "Privileged": False,
                       "Binds": ["/tmp/now-wolf-compat-test01:/etc/wolf:rw"]},
        "State": {"Running": True},
        "Mounts": [{"Source": "/tmp/now-wolf-compat-test01",
                    "Destination": "/etc/wolf", "RW": True, "Type": "bind"}],
    }


class RealWolfSafetyTests(unittest.TestCase):
    def test_exactly_one_disposable_host_is_accepted(self):
        self.assertEqual(probe.validate_container("now-wolf-compat-test01", safe_info()),
                         "/tmp/now-wolf-compat-test01")

    def test_refuses_production_and_unisolated_container(self):
        for mutate in (
            lambda x: x.update({"Name": "/wolf"}),
            lambda x: x["Config"]["Labels"].clear(),
            lambda x: x["HostConfig"].update({"NetworkMode": "host"}),
            lambda x: x["HostConfig"].update({"Privileged": True}),
            lambda x: x["State"].update({"Running": False}),
            lambda x: x["Mounts"][0].update({"Source": "/etc/wolf"}),
            lambda x: x["Mounts"][0].update({"Source": "/home/user/wolf"}),
            lambda x: x["Mounts"][0].update({"Destination": "/etc/anything"}),
            lambda x: x["Mounts"].append(copy.deepcopy(x["Mounts"][0])),
            lambda x: x["Mounts"][0].update({"RW": False}),
        ):
            info = safe_info()
            mutate(info)
            with self.subTest(info=info):
                with self.assertRaises(probe.ProbeError):
                    probe.validate_container("now-wolf-compat-test01", info)
        with self.assertRaises(probe.ProbeError):
            probe.inspect_container("wolf", Mock(side_effect=AssertionError("called")))
        with self.assertRaises(probe.ProbeError):
            probe.inspect_container("now-wolf-compat-../wolf",
                                    Mock(side_effect=AssertionError("called")))

    def test_probe_only_uses_five_gets_and_redacts_session_keys(self):
        called = []
        responses = {
            "/api/v1/clients": {"success": True, "clients": []},
            "/api/v1/profiles": {"success": True, "profiles": []},
            "/api/v1/apps": {"success": True, "apps": []},
            "/api/v1/sessions": {"success": True, "sessions": [
                {"aes_key": "SECRET-NO-OUTPUT", "client_id": "123"}]},
            "/api/v1/lobbies": {"success": True, "lobbies": []},
        }
        def mock_docker(args, input_data=b""):
            called.append(args)
            if args[0] == "inspect":
                return json.dumps([safe_info()]).encode()
            self.assertEqual(args[:4], [
                "exec", "-i", "now-wolf-compat-test01", "python3"])
            self.assertEqual(args[-2], "GET")
            self.assertIn(args[-1], responses)
            return json.dumps(responses[args[-1]]).encode()
        result = probe.probe("now-wolf-compat-test01", mock_docker)
        self.assertEqual(result["result"], "pass")
        self.assertEqual(result["endpoint_counts"]["sessions"], 1)
        self.assertNotIn("SECRET-NO-OUTPUT", json.dumps(result))
        self.assertEqual(len(called), 6)
        self.assertFalse(any("POST" in arg for args in called for arg in args))

    def test_malformed_wolf_response_blocks_not_passes(self):
        def mock_docker(args, input_data=b""):
            if args[0] == "inspect":
                return json.dumps([safe_info()]).encode()
            return b'{"success":true,"sessions":[]}'
        with self.assertRaisesRegex(probe.ProbeError, "incompatible"):
            probe.probe("now-wolf-compat-test01", mock_docker)


if __name__ == "__main__":
    unittest.main()
