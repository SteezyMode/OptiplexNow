"""Tailscale owner Wolf pairing pilot: offline, with fake source and Wolf API."""
import http.client
import importlib.util
import json
from http.server import HTTPServer
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "server")]
from owner_access import PolicyError
from tailnet_wolf_pair import (pending_owner_wolf, pair_owner_wolf,
                               host_wolf_pair_api)
from tailnet_enrollment import (make_handler, PAIR_PENDING_ROUTE,
                                PAIR_APPROVE_ROUTE)

spec=importlib.util.spec_from_file_location(
    "client_wolf_pair", ROOT / "src/wolf-pair-client.py")
client=importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

PEER="100.86.77.3"
OTHER="100.86.77.4"


class FakeWolfPair:
    def __init__(self, entries=None):
        self.entries = [{"client_ip": PEER, "pair_secret": "private-pair-secret"}] if entries is None else entries
        self.calls = []
        self.success = True

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if (method, path) == ("GET", "/api/v1/pair/pending"):
            return {"success": True, "requests": self.entries}
        if (method, path) == ("POST", "/api/v1/pair/client"):
            return {"success": self.success}
        raise AssertionError("Unallowed Wolf route")


class AdapterTests(unittest.TestCase):
    def test_only_source_matched_owner_pair_can_be_listed_and_paired(self):
        wolf = FakeWolfPair([
            {"client_ip": OTHER, "pair_secret": "other-client-private"},
            {"client_ip": PEER, "pair_secret": "selected-private"}])
        result = pending_owner_wolf(PEER, call_api=wolf)
        self.assertEqual(result, {"success": True, "clients": [
            {"index": 2, "client_ip": PEER}]})
        self.assertNotIn("selected-private", str(result))
        self.assertNotIn("other-client-private", str(result))
        self.assertEqual(pair_owner_wolf(PEER, {
            "index": 2, "client_ip": PEER, "pin": "0419"}, call_api=wolf),
                         {"success": True})
        self.assertEqual(wolf.calls[-1], (
            "POST", "/api/v1/pair/client",
            {"pair_secret": "selected-private", "pin": "0419"}))

    def test_cannot_pair_different_tailscale_source_or_changed_pending(self):
        wolf = FakeWolfPair([{"client_ip": OTHER, "pair_secret": "someone-else"}])
        self.assertEqual(pending_owner_wolf(PEER, call_api=wolf)["clients"], [])
        with self.assertRaises(PolicyError):
            pair_owner_wolf(PEER, {
                "index": 1, "client_ip": PEER, "pin": "0419"}, call_api=wolf)
        self.assertFalse(any(method == "POST" for method, _, _ in wolf.calls))
        wolf = FakeWolfPair()
        for data in [
            {"index": 1, "client_ip": OTHER, "pin": "0419"},
            {"index": True, "client_ip": PEER, "pin": "0419"},
            {"index": 1, "client_ip": PEER, "pin": "04ab"},
            {"index": 1, "client_ip": PEER, "pin": "123"},
            {"index": 1, "client_ip": PEER, "pin": "0419", "owner": True},
            {"index": 2, "client_ip": PEER, "pin": "0419"},
        ]:
            with self.subTest(data=data), self.assertRaises(PolicyError):
                pair_owner_wolf(PEER, data, call_api=wolf)
        self.assertFalse(any(method == "POST" for method, _, _ in wolf.calls))

    def test_ambiguous_same_ip_or_backend_refusal_fails_closed(self):
        wolf=FakeWolfPair([
            {"client_ip": PEER, "pair_secret": "one"},
            {"client_ip": PEER, "pair_secret": "two"}])
        with self.assertRaises(PolicyError):
            pending_owner_wolf(PEER, call_api=wolf)
        wolf=FakeWolfPair()
        wolf.success=False
        with self.assertRaises(PolicyError):
            pair_owner_wolf(PEER, {
                "index":1,"client_ip":PEER,"pin":"1234"}, call_api=wolf)

    def test_rejects_non_tailnet_peer_before_wolf_call(self):
        wolf=FakeWolfPair()
        for peer in ("192.168.1.1","100.100.100.100","invalid",None):
            with self.subTest(peer=peer), self.assertRaises(PolicyError):
                pending_owner_wolf(peer, call_api=wolf)
        self.assertEqual(wolf.calls, [])

    def test_fixed_host_adapter_rejects_arbitrary_api(self):
        for method,path,payload in [
            ("POST","/api/v1/lobbies/stop",{}),
            ("GET","/api/v1/clients",None),
            ("POST","/api/v1/pair/client",{"command":"docker ps"}),
        ]:
            with self.subTest(path=path),self.assertRaises(PolicyError):
                host_wolf_pair_api(method,path,payload)


class PairingHttpTests(unittest.TestCase):
    def setUp(self):
        self.authorized=True
        self.wolf=FakeWolfPair()
        self.server=HTTPServer(("127.0.0.1",0),
            make_handler("1042","/no/live/host",
                 verify=lambda *_: ("1042","node-1") if self.authorized else None,
                 pair_api=self.wolf,owner_pair_enabled=True))
        self.thread=threading.Thread(target=self.server.serve_forever,
                                     kwargs={"poll_interval":0.01},daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def query(self,method,path,payload=None,headers=None):
        con=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=2)
        try:
            body=json.dumps(payload) if payload is not None else None
            h={"Content-Type":"application/json"}
            if headers:h.update(headers)
            con.request(method,path,body=body,headers=h)
            resp=con.getresponse()
            return resp.status,json.loads(resp.read())
        finally:
            con.close()

    def test_owner_can_list_only_own_pending(self):
        # The test HTTP loopback source is 127.0.0.1, and the fake Wolf
        # inventory must match that source to exercise endpoint plumbing.
        self.wolf.entries=[{"client_ip":"127.0.0.1","pair_secret":"hidden"}]
        code,result=self.query("GET",PAIR_PENDING_ROUTE)
        self.assertEqual(code,200)
        self.assertEqual(result["clients"], [{"index":1,"client_ip":"127.0.0.1"}])
        self.assertNotIn("hidden",str(result))

    def test_guest_and_mutation_are_rejected_without_wolf_post(self):
        self.authorized=False
        self.assertEqual(self.query("GET",PAIR_PENDING_ROUTE)[0],403)
        self.assertEqual(self.query("POST",PAIR_APPROVE_ROUTE,
                                    {"index":1,"client_ip":PEER,"pin":"1234"})[0],403)
        self.authorized=True
        self.assertEqual(self.query("POST",PAIR_APPROVE_ROUTE,
                                   {"index":1,"client_ip":OTHER,"pin":"1234"})[0],400)
        self.assertEqual(self.query("POST",PAIR_APPROVE_ROUTE,
                                   {"index":1,"client_ip":PEER,"pin":"1234"},
                                   {"Origin":"https://malicious.invalid"})[0],403)
        self.assertEqual(self.query("POST","/api/v1/exec",{})[0],404)
        self.assertFalse(any(x[0]=="POST" for x in self.wolf.calls))

    def test_disabled_default_rejects_pairing(self):
        # The real host never exposes pairing merely by installing .deb.
        handler=make_handler("1042","/no/live/host",
                             verify=lambda *_: ("1042","node-1"),
                             pair_api=self.wolf)
        with mock.patch.object(handler, "_verified_owner", return_value=True):
            self.assertFalse(handler.__dict__.get("owner_pair_enabled",False))
        source=(ROOT/"server/tailnet_enrollment.py").read_text()
        self.assertIn("owner_pair_enabled=False",source)
        pkg=(ROOT/"package.py").read_text()
        self.assertIn("'tailnet_wolf_pair.py'",pkg)
        self.assertIn("'wolf-pair-local.py'",pkg)
        self.assertNotIn("tailnet_enrollment.py --serve",pkg)


class ClientTransportTests(unittest.TestCase):
    def test_pending_and_pair_fixed_tailnet_routes(self):
        calls=[]
        class Conn:
            def __init__(self,host,port,timeout):
                calls.append(("host",host,port))
                self.path=""
            def request(self,method,path,body=None,headers=None):
                calls.append((method,path,json.loads(body) if body else None))
                self.path=path
            def getresponse(self):
                path=self.path
                class Reply:
                    status=200
                    def read(self,n):
                        return json.dumps(
                            {"success":True,"clients":[{"index":1,"client_ip":PEER}]}
                            if path==PAIR_PENDING_ROUTE else
                            {"success":True}).encode()
                return Reply()
            def close(self):
                pass
        self.assertEqual(client.invoke_tailnet(
            PEER,"pending-text",connection=Conn)["clients"][0]["client_ip"],PEER)
        self.assertEqual(client.invoke_tailnet(
            PEER,"pair",{"index":1,"client_ip":PEER,"pin":"0123"},
            connection=Conn),{"success":True})
        self.assertEqual(calls[1][0:2],("GET",PAIR_PENDING_ROUTE))
        self.assertEqual(calls[3][0:2],("POST",PAIR_APPROVE_ROUTE))
        self.assertNotIn("private-pair-secret",str(calls))

    def test_identity_denial_never_invokes_legacy_admin_ssh(self):
        with mock.patch.object(client,"invoke_tailnet",
                               side_effect=RuntimeError("forbidden")):
            with mock.patch.object(client,"invoke") as admin:
                with self.assertRaises(RuntimeError):
                    client.invoke_preferred(PEER,"","pair",{
                        "index":1,"client_ip":PEER,"pin":"1234"})
                admin.assert_not_called()
        with mock.patch.object(client,"invoke_tailnet",
                               side_effect=ConnectionRefusedError):
            with mock.patch.object(client,"invoke",
                                   return_value={"success":True}) as admin:
                client.invoke_preferred(PEER,"owner","pending-text")
                admin.assert_called_once()

    def test_normal_gui_no_longer_needs_ssh_username_for_pairing(self):
        c=(ROOT/"src/main.c").read_text()
        part=c.split("static void pair_wolf(GtkWidget *origin)",1)[1].split(
            "static void on_games_action(",1)[0]
        self.assertIn("if(!now_valid_host(cfg[0]))",part)
        self.assertNotIn("now_valid_user(cfg[1])",part)
        self.assertIn("invoke_preferred", (ROOT/"src/wolf-pair-client.py").read_text())


if __name__=="__main__":
    unittest.main()
