"""Mocked media helper authorization and exact-host verification."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/"src/media-discover.py"
spec=importlib.util.spec_from_file_location("now_media_discover",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeReply:
    def __init__(self, status=200, body=b'{"Id":"one"}'):
        self.status=status
        self.body=body
    def read(self, n):
        return self.body[:n]


class FakeConn:
    def __init__(self, host, port, timeout):
        assert (host,port,timeout)==("100.121.156.34",8096,4)
        self.path=None
    def request(self, method,path,headers=None):
        assert method=="GET" and path=="/System/Info/Public"
        self.path=path
    def getresponse(self):
        return FakeReply()
    def close(self):
        pass


class MediaDiscoveryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        key=Path(tmp.name)/"id_ed25519"
        key.write_text("placeholder")
        key.chmod(0o600)
        patcher=patch.object(mod,"KEY",key)
        patcher.start()
        self.addCleanup(patcher.stop)

    def runner(self,args,**kwargs):
        self.assertIn("StrictHostKeyChecking=yes",args)
        self.assertEqual(args[-1],"100.121.156.34")
        self.assertEqual(kwargs["input"],b'{"version":1,"action":"media"}\n')
        return subprocess.CompletedProcess(args,0,
            b'{"success":true,"service":"jellyfin","available":true}')

    def test_approved_host_and_reachable_jellyfin(self):
        self.assertTrue(mod.discover("100.121.156.34","optiplex",
                         runner=self.runner,connector=FakeConn))

    def test_verified_server_id_must_match_client_reachable_instance(self):
        def trusted(args, **kwargs):
            return subprocess.CompletedProcess(args, 0,
                b'{"success":true,"service":"jellyfin","available":true,'
                b'"server_id":"one"}')
        self.assertTrue(mod.discover("100.121.156.34", "optiplex",
                     runner=trusted, connector=FakeConn))

        def wrong(args, **kwargs):
            return subprocess.CompletedProcess(args, 0,
                b'{"success":true,"service":"jellyfin","available":true,'
                b'"server_id":"different-jellyfin"}')
        with self.assertRaisesRegex(ValueError, "differs from authorized"):
            mod.discover("100.121.156.34", "optiplex",
                         runner=wrong, connector=FakeConn)

    def test_reject_malformed_host_id_before_client_network_request(self):
        for bad_id in ("../wrong", "http://evil.invalid/", "", "x" * 129, 42):
            with self.subTest(bad_id=bad_id):
                import json
                response = {"success": True, "service": "jellyfin",
                            "available": True, "server_id": bad_id}
                def response_from_host(args, **kwargs):
                    return subprocess.CompletedProcess(
                        args, 0, json.dumps(response).encode())
                with self.assertRaises(ValueError):
                    mod.discover("100.121.156.34", "optiplex",
                        runner=response_from_host,
                        connector=lambda *a, **k: self.fail(
                            "Client attempted network request for invalid ID"))

    def test_host_approved_port_and_path_are_verified_before_launch(self):
        import json
        payload={"success":True,"service":"jellyfin","available":True,
                 "server_id":"one","endpoint":
                 {"scheme":"http","port":12345,"base_path":"/jellyfin"}}
        def runner(args, **kwargs):
            return subprocess.CompletedProcess(
                args,0,json.dumps(payload).encode())
        class Routed(FakeConn):
            def __init__(self, host, port, timeout):
                self.asserted = (host,port,timeout)
                assert self.asserted == ("100.121.156.34",12345,4)
            def request(self,method,path,headers=None):
                assert (method,path)==("GET","/jellyfin/System/Info/Public")
        self.assertEqual(mod.discover(
            "100.121.156.34","optiplex",runner=runner,connector=Routed),
            payload["endpoint"])
        for bad in (
            {"scheme":"http","port":12345,"base_path":"//outside"},
            {"scheme":"http","port":12345,"base_path":"/../outside"},
            {"scheme":"http","port":12345,"base_path":"/jellyfin?admin=1"},
            {"scheme":"http","port":True,"base_path":"/"},
            {"scheme":"http","port":12345,"base_path":"/","host":"evil.invalid"},
        ):
            with self.subTest(bad=bad):
                payload["endpoint"]=bad
                with self.assertRaises(ValueError):
                    mod.discover("100.121.156.34","optiplex",
                                 runner=runner,
                                 connector=lambda *a,**k: self.fail(
                                     "Invalid endpoint must not be probed"))

    def test_owner_endpoint_must_bind_server_id_and_not_change_host(self):
        import json
        response={"success":True,"service":"jellyfin","available":True,
                  "endpoint":{"scheme":"http","port":8096,"base_path":"/"}}
        def runner(args,**kwargs):
            return subprocess.CompletedProcess(
                args,0,json.dumps(response).encode())
        with self.assertRaises(ValueError):
            mod.discover("100.121.156.34","optiplex",runner=runner,
                connector=lambda *a,**k:self.fail("Missing ID must not probe"))
        response["server_id"]="different"
        with self.assertRaisesRegex(ValueError,"differs"):
            mod.discover("100.121.156.34","optiplex",runner=runner,
                         connector=FakeConn)

    def test_denied_or_unavailable_media_never_opens_url(self):
        for stdout in (b'{"success":false}',b'{"success":true,"service":"plex","available":true}',
                       b'{"success":true,"service":"jellyfin","available":false}'):
            with self.subTest(stdout=stdout):
                def deny(args,**kwargs):
                    return subprocess.CompletedProcess(args,0,stdout)
                with self.assertRaises(ValueError):
                    mod.discover("100.121.156.34","optiplex",
                                 runner=deny, connector=lambda *a,**k: self.fail("network probe"))

    def test_rejects_host_injection_before_ssh(self):
        for host in ("https://bad.invalid","127.0.0.1;rm -rf /","a..b"):
            with self.assertRaises(ValueError):
                mod.discover(host,"optiplex",runner=lambda *a,**k: self.fail("ssh"))


if __name__=="__main__":
    unittest.main()
