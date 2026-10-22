"""Contract and admission tests. No Docker, GPU or real Wolf POST."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
spec = importlib.util.spec_from_file_location(
    "now_wolf_contract", ROOT / "server" / "verify_wolf_lobby_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def schema_fixture():
    def obj(req, props=None):
        return {"type": "object", "required": list(req),
                "properties": props or {}}
    return {"paths": {
        "/api/v1/lobbies/create": {"post": {}},
        "/api/v1/lobbies/join": {"post": {}}},
        "components": {"schemas": {
            "wolf__api__CreateLobbyRequest": obj(
                contract.REQUIRED_CREATE,
                {"runner": {"anyOf": [{"$ref":
                    "#/components/schemas/wolf__config__AppDocker__tagged"}]}}),
            "wolf__core__events__VideoSettings": obj(
                contract.REQUIRED_VIDEO, {
                    k: {"type": "integer" if k in ("width","height","refresh_rate")
                        else "string"} for k in contract.REQUIRED_VIDEO}),
            "wolf__config__AppDocker__tagged": obj(
                contract.REQUIRED_DOCKER, {"type":{"enum":["docker"]}}),
            "wolf__core__events__JoinLobbyEvent": obj(
                contract.REQUIRED_JOIN, {"moonlight_session_id":{"type":"string"}}),
        }}}


def inspect_fixture(name, tempdir):
    return {"Name": "/" + name,
            "Config": {"Labels": {
                "io.optiplex-now.compat-disposable": "true"
                }, "Image": contract.WOLF_IMAGE,
                "Volumes": {"/run/user/wolf/":{}}},
            "State": {"Running": True},
            "HostConfig": {"Privileged": False, "NetworkMode": "none",
                           "Binds": [f"{tempdir}/{name}:/etc/wolf:rw"]},
            "Mounts": [
                {"Type":"volume","Name":"f"*64,"Destination":"/run/user/wolf"},
                {"Type":"bind","Source":f"{tempdir}/{name}",
                 "Destination":"/etc/wolf","RW":True},
            ]}


class LiveContractTests(unittest.TestCase):
    def test_schema_contains_native_wolf_required_fields(self):
        x = contract.verify_schema(schema_fixture())
        self.assertTrue(x["schema_compatible"])
        self.assertTrue(x["lobby_join_id_is_string"])
        self.assertEqual(x["docker_runner_required"], 7)

    def test_schema_drift_fails_closed(self):
        for mutate in (
            lambda x: x["components"]["schemas"]["wolf__api__CreateLobbyRequest"]
                     ["required"].append("new_required_field"),
            lambda x: x["components"]["schemas"]["wolf__core__events__JoinLobbyEvent"]
                     ["properties"]["moonlight_session_id"].update({"type":"integer"}),
            lambda x: x["components"]["schemas"]["wolf__config__AppDocker__tagged"]
                     ["required"].remove("devices"),
            lambda x: x["paths"].pop("/api/v1/lobbies/join"),
        ):
            payload = schema_fixture()
            mutate(payload)
            with self.assertRaises(contract.isolated.ProbeError):
                contract.verify_schema(payload)

    def test_rejects_wrong_owner_host_name_before_docker(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("Docker must not be called")
        with self.assertRaises(contract.isolated.ProbeError):
            contract.attempt("wolf", forbidden, ci_run_id="1234",
                             runner_temp="/tmp")

    def test_real_probe_one_post_only_after_clean_inventory(self):
        name = "now-wolf-compat-1234"
        tmp = "/tmp"
        calls = []
        schema = schema_fixture()
        def docker(args, input_data=b""):
            calls.append((args,input_data))
            if args[0] == "inspect":
                return json.dumps([inspect_fixture(name,tmp)]).encode()
            path = args[-1]
            if path == "/api/v1/openapi-schema":
                return json.dumps(schema).encode()
            if path in ("/api/v1/clients","/api/v1/sessions","/api/v1/lobbies"):
                key = path.rsplit("/", 1)[-1]
                return json.dumps({"success":True,key:[]}).encode()
            if path == "/api/v1/lobbies/create":
                self.assertEqual(args[-2],"POST")
                body = json.loads(input_data)
                self.assertEqual(body["runner"]["type"], "process")
                self.assertEqual(body["runner"]["run_cmd"], "sleep 10")
                self.assertEqual(body["profile_id"], "now-ci-disposable")
                return json.dumps({"success":True,"lobby_id":"throwaway"}).encode()
            raise AssertionError(path)
        result = contract.attempt(name,docker,ci_run_id="1234",runner_temp=tmp)
        self.assertEqual(result["actual_disposable_create"],"created_disposable_lobby")
        self.assertFalse(result["actual_join_executed"])
        self.assertEqual(sum(1 for args,_ in calls if args[-1].endswith("/create")),1)
        self.assertNotIn("throwaway",json.dumps(result))

    def test_refuses_existing_session_before_write(self):
        name = "now-wolf-compat-1234"
        calls = []
        def docker(args, input_data=b""):
            calls.append(args)
            if args[0]=="inspect":
                return json.dumps([inspect_fixture(name,"/tmp")]).encode()
            if args[-1]=="/api/v1/openapi-schema":
                return json.dumps(schema_fixture()).encode()
            if args[-1].endswith("/clients"):
                return b'{"success":true,"clients":[]}'
            if args[-1].endswith("/sessions"):
                return b'{"success":true,"sessions":[{"client_id":"1234"}]}'
            raise AssertionError("No other endpoints should be reached")
        with self.assertRaisesRegex(contract.isolated.ProbeError, "nonempty"):
            contract.attempt(name,docker,ci_run_id="1234",runner_temp="/tmp")
        self.assertFalse(any(args[-2]=="POST" for args in calls[1:]))

    def test_wrong_image_or_scratch_refused_before_any_get(self):
        name = "now-wolf-compat-1234"
        for mutate in (
            lambda x: x["Config"].update({"Image":"wolf:stable"}),
            lambda x: x["Mounts"][1].update({"Source":"/tmp/now-wolf-compat-9999"}),
        ):
            calls = []
            def docker(args, input_data=b""):
                calls.append(args)
                if args[0]=="inspect":
                    item=inspect_fixture(name,"/tmp")
                    mutate(item)
                    return json.dumps([item]).encode()
                raise AssertionError("Unsafe GET attempted")
            with self.assertRaises(contract.isolated.ProbeError):
                contract.attempt(name,docker,ci_run_id="1234",runner_temp="/tmp")
            self.assertEqual(len(calls),1)


if __name__=="__main__":
    unittest.main()
