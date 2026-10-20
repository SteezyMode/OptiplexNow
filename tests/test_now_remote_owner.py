"""No-host-screen owner approval contract: tailnet WhoIs + pinned install identity.

Loopback HTTP fixtures emulate Tailscale's authenticated peer; no production
network, server, Docker, email or Wolf service is accessed.
"""
import http.client
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest

HERE=Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0,str(HERE))
import now_pairing_broker as broker
import now_pairing_requests as pairing
import now_pairing_owner_identity as identity


class PinnedOwnerTests(unittest.TestCase):
    def test_parse_rejects_bad_owner_identity(self):
        self.assertEqual(identity.parse_owner_user_id("1042\n"),"1042")
        for value in ("", "0", "-1", "foo@example.com", "001", " 1 2 ",
                      "owner", "1"*21, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    identity.parse_owner_user_id(value)

    def test_trusted_server_tailscale_owner_needs_no_host_screen(self):
        class Result:
            returncode=0
            stdout=json.dumps({"BackendState":"Running",
                "Self":{"UserID":1042, "Tags":[], "TailscaleIPs":["100.85.8.2"]}})
        commands=[]
        def fake_run(args, **kw):
            commands.append((args, kw))
            return Result()
        self.assertEqual(identity.owner_from_local_tailscale(runner=fake_run),"1042")
        self.assertEqual(commands[0][0],["tailscale","status","--json"])
        self.assertLessEqual(commands[0][1]["timeout"],3)

    def test_automatic_owner_binding_rejects_tagged_or_unenrolled_server(self):
        class Result:
            returncode=0
            stdout=""
        for status in [
            {"BackendState":"NeedsLogin","Self":{"UserID":1042,"TailscaleIPs":["100.85.8.2"]}},
            {"BackendState":"Running","Self":{"UserID":0,"TailscaleIPs":["100.85.8.2"]}},
            {"BackendState":"Running","Self":{"UserID":1042,"Tags":["tag:server"],"TailscaleIPs":["100.85.8.2"]}},
            {"BackendState":"Running","Self":{"UserID":1042,"ShareeNode":True,"TailscaleIPs":["100.85.8.2"]}},
            {"BackendState":"Running","Self":{"UserID":1042,"TailscaleIPs":["192.168.1.10"]}},
        ]:
            with self.subTest(status=status):
                def runner(*args, **kwargs):
                    r=Result()
                    r.stdout=json.dumps(status)
                    return r
                with self.assertRaises(ValueError):
                    identity.owner_from_local_tailscale(runner=runner)

    def test_pinned_owner_from_private_installer_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"owner-id"
            path.write_text("1042\n")
            path.chmod(0o600)
            self.assertEqual(identity.load_pinned_owner(str(path)),"1042")
            path.chmod(0o644)
            with self.assertRaises(PermissionError):
                identity.load_pinned_owner(str(path))
            path.chmod(0o600)
            link=Path(folder)/"linked"
            link.symlink_to(path)
            with self.assertRaises(PermissionError):
                identity.load_pinned_owner(str(link))
            path.write_text("not-an-owner")
            with self.assertRaises(ValueError):
                identity.load_pinned_owner(str(path))
            with self.assertRaises(ValueError):
                identity.load_pinned_owner("relative-file")


class RemoteOwnerTests(unittest.TestCase):
    def setUp(self):
        self.queue=pairing.PairingRequests()
        self.owner=pairing.PeerIdentity("nOwnerLaptop","1042")
        self.other=pairing.PeerIdentity("nGuestClient","2048")
        self.peer=self.other
        self.owner_id="1042"
        def verifier(_ip):
            return self.peer
        self.server=broker.PairingHTTPServer(
            ("127.0.0.1",0),
            broker.make_handler(self.queue,verify=verifier,
                                owner_user_id=self.owner_id))
        self.thread=threading.Thread(target=self.server.serve_forever,
                                     kwargs={"poll_interval":0.01},daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def call(self,method,path,headers=None,host_override=None,body=None):
        con=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=2)
        try:
            h={"X-NOW-Owner-Client":"desktop-v1"}
            if headers:h.update(headers)
            if host_override:
                h["Host"]=host_override
            con.request(method,path,body=body,headers=h)
            result=con.getresponse()
            return result.status,json.loads(result.read())
        finally:
            con.close()

    def create_request(self):
        return self.queue.request(self.other,"wolf")

    def test_owner_can_approve_without_host_terminal_or_screen(self):
        rid=self.create_request()
        self.peer=self.owner
        status,payload=self.call("GET",broker.OWNER_LIST)
        self.assertEqual(status,200)
        self.assertEqual(payload["pending"][0]["request_id"],rid)
        self.assertEqual(payload["pending"][0]["account_id"],self.other.user_id)
        self.assertEqual(payload["pending"][0]["device_id"],self.other.node_id)
        target=f"{broker.OWNER_LIST}/{rid}/approve"
        self.assertEqual(self.call("POST",target)[0],200)
        self.assertEqual(self.queue.status_for_peer(self.other,rid),"approved")
        self.assertEqual(self.call("POST",target)[0],409)
        self.assertIsNone(self.queue.take_grant_for_adapter(self.owner,rid,"wolf"))
        self.assertIsNotNone(self.queue.take_grant_for_adapter(self.other,rid,"wolf"))

    def test_other_tailnet_member_cannot_approve_or_view_owner_queue(self):
        rid=self.create_request()
        self.assertEqual(self.call("GET",broker.OWNER_LIST)[0],403)
        self.assertEqual(self.call("POST",f"{broker.OWNER_LIST}/{rid}/approve")[0],403)
        self.assertEqual(self.queue.status_for_peer(self.other,rid),"pending")

    def test_missing_owner_bootstrap_disables_remote_admin(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        # Reuse fixture with disabled owner route, no auto-claim.
        self.server=broker.PairingHTTPServer(
            ("127.0.0.1",0),
            broker.make_handler(self.queue,verify=lambda ip:self.owner))
        self.thread=threading.Thread(target=self.server.serve_forever,
                                    daemon=True)
        self.thread.start()
        self.assertEqual(self.call("GET",broker.OWNER_LIST)[0],403)

    def test_owner_identity_cannot_be_supplied_in_request_headers(self):
        rid=self.create_request()
        forged={"X-Tailscale-User":"1042","X-Owner":"true","Cookie":"owner=1042"}
        self.assertEqual(self.call("GET",broker.OWNER_LIST,headers=forged)[0],403)
        self.assertEqual(self.call("POST",f"{broker.OWNER_LIST}/{rid}/approve",
                                   headers=forged)[0],403)
        self.assertEqual(self.queue.status_for_peer(self.other,rid),"pending")

    def test_owner_browser_cross_origin_and_dns_rebinding_denied(self):
        rid=self.create_request()
        self.peer=self.owner
        path=f"{broker.OWNER_LIST}/{rid}/approve"
        self.assertEqual(self.call("POST",path,headers={"Origin":"https://evil.example"})[0],403)
        self.assertEqual(self.call("POST",path,headers={"X-NOW-Owner-Client":""})[0],403)
        self.assertEqual(self.call("POST",path,host_override="evil.example")[0],403)
        self.assertEqual(self.call("POST",path,body=b'{"owner":true}')[0],400)
        self.assertEqual(self.queue.status_for_peer(self.other,rid),"pending")

    def test_owner_can_deny_without_backend_grant(self):
        rid=self.create_request()
        self.peer=self.owner
        path=f"{broker.OWNER_LIST}/{rid}/deny"
        self.assertEqual(self.call("POST",path)[0],200)
        self.assertEqual(self.queue.status_for_peer(self.other,rid),"denied")
        self.assertIsNone(self.queue.take_grant_for_adapter(self.other,rid,"wolf"))

    def test_no_remote_admin_or_docker_capability(self):
        self.peer=self.owner
        for route in ("/v1/owner/exec","/v1/owner/docker",
                      "/v1/owner/pairing/grant","/v1/owner/pairing/claim"):
            self.assertEqual(self.call("POST",route)[0],404)


if __name__=="__main__":
    unittest.main()
