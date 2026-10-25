"""Offline owner QR approval tests (no real Tailscale or host)."""
import http.client
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from http.server import HTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"server"),str(ROOT/"src")]
from owner_qr_approval import PAGE_PREFIX, parse_page_request, render_page
from tailnet_enrollment import make_handler, APPROVE_ROUTE, ROUTE

spec=importlib.util.spec_from_file_location("now_owner_qr_client",ROOT/"src/owner-qr.py")
qr=importlib.util.module_from_spec(spec)
spec.loader.exec_module(qr)
REQUEST="a"*32
CODE="654321"
FP="b"*20


class QrCodeTests(unittest.TestCase):
    def test_link_and_fragment(self):
        url=qr.approval_url("100.85.2.8",REQUEST,CODE)
        self.assertEqual(url,"http://100.85.2.8:18793/owner/approve/"+REQUEST+"#"+CODE)
        self.assertNotIn(CODE,url.split("#")[0])
        self.assertEqual(parse_page_request(PAGE_PREFIX+REQUEST),REQUEST)
        for host in ("192.168.40.212","100.100.100.100","example.com","8.8.8.8"):
            with self.subTest(host=host),self.assertRaises(ValueError):
                qr.approval_url(host,REQUEST,CODE)
        for request,code in (("bad",CODE),(REQUEST,"12345"),(REQUEST,"1234567"),
                             (REQUEST+"/bad",CODE),(REQUEST,"xx2345")):
            with self.subTest(request=request,code=code),self.assertRaises(ValueError):
                qr.approval_url("100.85.2.8",request,code)

    def test_qr_is_generated_locally_with_no_secret_in_process_args(self):
        commands=[]
        class Result:
            stdout=b"\x89PNG\r\n\x1a\n" + b"DATA"
        def runner(argv,**opts):
            commands.append((argv,opts))
            return Result()
        url=qr.approval_url("100.85.2.8",REQUEST,CODE)
        self.assertTrue(qr.qr_png(url,runner=runner).startswith(b"\x89PNG"))
        argv,opts=commands[0]
        self.assertNotIn(CODE,str(argv))
        self.assertEqual(opts["input"],url.encode("ascii"))

    def test_page_no_secret_or_external_script(self):
        html,nonce=render_page(REQUEST,FP,600,nonce="A"*24)
        self.assertIn('script nonce="'+nonce+'"',html)
        self.assertIn("history.replaceState",html)
        self.assertIn("/v1/owner/enrollment/approve",html)
        self.assertNotIn(CODE,html)
        self.assertNotIn("https://",html)
        for path in (PAGE_PREFIX, PAGE_PREFIX+REQUEST+"?x=1",PAGE_PREFIX+REQUEST+"/"):
            with self.assertRaises(ValueError): parse_page_request(path)
        with self.assertRaises(ValueError): render_page(REQUEST,"<unsafe>",600)


class PhoneHTTPTests(unittest.TestCase):
    def setUp(self):
        self.owner=True
        self.entries=[{"request_id":REQUEST,"fingerprint":FP,"seconds_remaining":500}]
        self.approvals=[]
        def verify(addr,owner):
            return ("1042","phoneNode") if self.owner and owner=="1042" else None
        def pending(state):
            return self.entries
        def approve(state,rid,code,client,*,wolf_api,approval):
            self.approvals.append((rid,code,client,approval))
            return {"success":True,"status":"approved"}
        self.server=HTTPServer(("127.0.0.1",0),make_handler(
            "1042","/private/owner",verify=verify,pending=pending,
            remote_approve_enabled=True,approve=approve,wolf_factory=lambda:object()))
        self.worker=threading.Thread(target=self.server.serve_forever,
                                     kwargs={"poll_interval":0.01},daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def call(self,method,path,payload=None,headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=2)
        try:
            body=json.dumps(payload) if payload is not None else None
            values={"Content-Type":"application/json"} if payload is not None else {}
            values.update(headers or {})
            conn.request(method,path,body=body,headers=values)
            resp=conn.getresponse()
            return resp.status,dict(resp.getheaders()),resp.read().decode("utf-8")
        finally:
            conn.close()

    def test_get_requires_owner_and_active_request(self):
        status,headers,body=self.call("GET",PAGE_PREFIX+REQUEST)
        self.assertEqual(status,200)
        self.assertIn("text/html",headers["Content-Type"])
        self.assertIn("no-store",headers["Cache-Control"])
        self.assertIn("frame-ancestors 'none'",headers["Content-Security-Policy"])
        self.assertIn(FP,body)
        self.assertNotIn(CODE,body)
        self.owner=False
        self.assertEqual(self.call("GET",PAGE_PREFIX+REQUEST)[0],403)
        self.owner=True
        self.entries=[]
        self.assertEqual(self.call("GET",PAGE_PREFIX+REQUEST)[0],404)
        self.assertEqual(self.call("GET",PAGE_PREFIX+REQUEST+"?x=1")[0],404)

    def test_browser_same_origin_and_verified_owner(self):
        target={"request_id":REQUEST,"code":CODE,"wolf_client_id":"100123456","confirmed":True}
        origin="http://127.0.0.1:"+str(self.server.server_port)
        self.assertEqual(self.call("GET",PAGE_PREFIX+REQUEST,headers={"Host":"evil.example"})[0],403)
        self.assertEqual(self.call("POST",APPROVE_ROUTE,target,{"Origin":"https://evil.example"})[0],403)
        self.assertEqual(self.call("POST",ROUTE,{"version":1,"public_key":"bad"},{"Origin":origin})[0],403)
        self.assertEqual(self.call("POST",APPROVE_ROUTE,target,
                                   {"Origin":origin,"Sec-Fetch-Site":"cross-site"})[0],403)
        self.assertFalse(self.approvals)
        self.owner=False
        self.assertEqual(self.call("POST",APPROVE_ROUTE,target,{"Origin":origin})[0],403)
        self.owner=True
        status,_,result=self.call("POST",APPROVE_ROUTE,target,{"Origin":origin})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(result)["status"],"approved")
        self.assertEqual(self.approvals,[(REQUEST,CODE,"100123456",True)])

    def test_explicit_approval_required(self):
        base={"request_id":REQUEST,"code":CODE,"wolf_client_id":"100123456"}
        for payload in (base,dict(base,confirmed=False),
                        dict(base,confirmed=True,source="bad"),
                        dict(base,confirmed=True,request_id=12)):
            self.assertEqual(self.call("POST",APPROVE_ROUTE,payload)[0],400)
        self.assertEqual(self.approvals,[])


if __name__=="__main__":
    unittest.main()
