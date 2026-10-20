"""Remote NOW owner client and GTK wiring: no network or server changes."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "now_owner_client", ROOT/"src"/"now-owner-approvals.py")
client=importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
GTK=(ROOT/"src"/"main.c").read_text()
PKG=(ROOT/"package.py").read_text()


class StubResponse:
    def __init__(self,status=200,message=None):
        self.status=status
        self.data=json.dumps(message if message is not None else {}).encode()
    def read(self,cap):
        return self.data[:cap]


class StubConnection:
    def __init__(self,response):
        self.response=response
        self.method=None
        self.path=None
        self.headers=None
        self.body=None
        self.closed=False
    def request(self,method,path,body=None,headers=None):
        self.method=method
        self.path=path
        self.body=body
        self.headers=headers
    def getresponse(self):
        return self.response
    def close(self):
        self.closed=True


class RemoteOwnerClientTests(unittest.TestCase):
    def invoke(self,action="list",request_id=None,status=200,message=None):
        fake=StubConnection(StubResponse(status,message))
        observed=[]
        def new_connection(host,port,timeout):
            observed.append((host,port,timeout))
            return fake
        value=client.query_owner("100.85.22.1",action,request_id,
                                 connection=new_connection)
        return value,fake,observed

    def test_tailnet_addresses_only_no_dns_fallback_or_public(self):
        self.assertTrue(client.valid_host("100.90.10.8"))
        for host in ("127.0.0.1","192.168.0.1","8.8.8.8",
                     "100.100.100.100","fd7a:115c:a1e0::1",
                     "games.monumentrisk.com","",None):
            self.assertFalse(client.valid_host(host))
            self.assertEqual(client.query_owner(host,"list"),(False,"invalid_host"))

    def test_list_pending_and_verify_no_admin_credentials(self):
        req="a"*32
        payload={"pending":[{"request_id":req,"device_id":"nClient",
                             "account_id":"2055","backend":"wolf"}]}
        result,conn,args=self.invoke(message=payload)
        self.assertEqual(result,(True,[(req,"nClient","wolf")]))
        self.assertEqual(args,[("100.85.22.1",18792,4)])
        self.assertEqual(conn.method,"GET")
        self.assertEqual(conn.path,"/v1/owner/pairing/requests")
        self.assertEqual(conn.headers["X-NOW-Owner-Client"],"desktop-v1")
        self.assertNotIn("Authorization",conn.headers)
        self.assertTrue(conn.closed)

    def test_authorize_or_deny_exact_request_only(self):
        rid="b"*32
        for action in ("approve","deny"):
            result,conn,_=self.invoke(action,rid,message={"decision_recorded":True})
            self.assertEqual(result,(True,"decision_recorded"))
            self.assertEqual(conn.method,"POST")
            self.assertEqual(conn.body,b"")
            self.assertEqual(conn.path,
                             f"/v1/owner/pairing/requests/{rid}/{action}")
        for invalid in ("../admin","x"*256,"",None):
            self.assertEqual(client.query_owner("100.85.22.1","approve",invalid),
                             (False,"invalid_request"))

    def test_new_client_can_request_access_without_ssh_or_host_console(self):
        req="n"*32
        fake=StubConnection(StubResponse(202,{"request_id":req,
                            "owner_status":"pending","moonlight_paired":False}))
        answer=client.request_access("100.85.22.1",
                connection=lambda host,port,timeout:fake)
        self.assertEqual(answer,(True,"pending"))
        self.assertEqual(fake.method,"POST")
        self.assertEqual(fake.path,"/v1/pairing/requests")
        self.assertEqual(json.loads(fake.body),{"backend":"wolf"})
        self.assertNotIn("Authorization",fake.headers)
        self.assertEqual(client.request_access("127.0.0.1"),
                         (False,"invalid_host"))
        self.assertTrue(fake.closed)

    def test_server_does_not_advertise_pairing_success_from_owner_approval(self):
        fake=StubConnection(StubResponse(202,{"request_id":"n"*32,
                            "owner_status":"approved","moonlight_paired":False}))
        self.assertEqual(client.request_access("100.85.22.1",
                    connection=lambda *args,**kw:fake),(True,"approved"))
        self.assertIn('REQUEST GAMING ACCESS TO SERVER',GTK)
        self.assertIn('static void on_now_request_access(',GTK)
        self.assertIn('SERVER OWNER APPROVED. COMPLETE NATIVE MOONLIGHT PAIRING',GTK)

    def test_errors_are_fixed_and_status_is_not_approval(self):
        self.assertEqual(self.invoke(status=403)[0],(False,"owner_not_authorized"))
        self.assertEqual(self.invoke(status=409)[0],(False,"request_expired"))
        self.assertEqual(self.invoke(status=500)[0],(False,"server_unavailable"))
        self.assertEqual(self.invoke("approve","a"*32,message={"moonlight_paired":True})[0],
                         (False,"invalid_response"))
        self.assertEqual(self.invoke(message={"pending":[{"request_id":"oops",
                          "device_id":"nTrusted","backend":"wolf"}]})[0],
                         (False,"invalid_response"))
        self.assertEqual(self.invoke(message={"pending":[{"request_id":"a"*32,
                          "device_id":"nX\\ninjection","backend":"wolf"}]})[0],
                         (False,"invalid_response"))

    def test_gtk_ships_remote_owner_dialog_without_shell(self):
        self.assertIn('PENDING DEVICE APPROVALS (REMOTE OWNER)',GTK)
        self.assertIn('static void remote_owner_list_finished(',GTK)
        self.assertIn('static void remote_owner_decision_finished(',GTK)
        self.assertIn('gtk_combo_box_text_append(',GTK)
        self.assertIn('g_subprocess_communicate_utf8_async(',GTK)
        self.assertIn('gtk_dialog_run(GTK_DIALOG(dialog))',GTK)
        owner=GTK[GTK.index('static void on_remote_owner_approvals('):
                  GTK.index('static void on_web_gaming_admin(')]
        self.assertNotIn('terminal_launch(',owner)
        self.assertNotIn('"ssh"',owner)
        self.assertIn('now-owner-approvals.py',PKG)


if __name__=="__main__":
    unittest.main()
