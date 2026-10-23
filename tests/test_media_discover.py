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
