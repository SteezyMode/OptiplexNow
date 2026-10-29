"""Owner-only browse/Add client: no-network tests and exact safe wire fields."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("now_download_ops",
                    ROOT/"src"/"download-operations-client.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
MAGNET="magnet:?xt=urn:btih:"+"f"*40

class OwnerOperationsTests(unittest.TestCase):
    def call(self,action,root=None,path=None,magnet=None,result=None):
        result=result or {
            "roots":{"success":True,"service":"qbittorrent",
                     "roots":[{"id":"bigdisk","label":"4 TB"},
                              {"id":"expansion","label":"2 TB"}]},
            "browse":{"success":True,"service":"qbittorrent",
                      "root":"bigdisk","relative":"Movies",
                      "folders":["Action ","Horror"]},
            "add":{"success":True,"status":"submitted"},
        }[action]
        with tempfile.TemporaryDirectory() as tmp:
            key=Path(tmp)/"owner_key";key.write_text("test only")
            def runner(cmd,**kw):
                self.assertEqual(cmd[0],"ssh")
                self.assertIn("StrictHostKeyChecking=yes",cmd)
                self.assertIn("IdentitiesOnly=yes",cmd)
                self.assertEqual(cmd[-1],"optiplex@100.121.156.34")
                payload=json.loads(kw["input"])
                self.assertEqual(payload["action"],"downloads_"+action)
                if action=="add":
                    self.assertEqual(payload["magnet"],MAGNET)
                    self.assertEqual(payload["relative"],"Movies/Horror")
                return subprocess.CompletedProcess(cmd,0,json.dumps(result).encode(),b"")
            with patch.object(mod,"KEY",key):
                return mod.fetch("100.121.156.34","optiplex",
                                 action,root,path,magnet,runner=runner)

    def test_owner_root_and_browse_genre_space_preserved(self):
        self.assertEqual(self.call("roots"),
            "ROOTS\nROOT\tbigdisk\t4 TB\nROOT\texpansion\t2 TB")
        self.assertEqual(self.call("browse","bigdisk","Movies"),
            "FOLDERS\tbigdisk\tMovies\nFOLDER\tAction \nFOLDER\tHorror")

    def test_vpn_health_uses_authorized_inventory_and_never_claims_leak_proof(self):
        healthy={"success":True,"version":1,
            "downloaders":[{"service":"qbittorrent","gateway_bound":True,
                "gateway_healthy":True,"vpn_provider":"airvpn",
                "vpn_egress_verified":False,"killswitch_verified":False}]}
        self.assertEqual(mod.present("vpn",healthy),"VPN\tHEALTHY\tairvpn")
        healthy["downloaders"][0]["gateway_healthy"]=False
        self.assertEqual(mod.present("vpn",healthy),"VPN\tUNVERIFIED\tairvpn")
        healthy["downloaders"][0]["vpn_provider"]="injected-url"
        with self.assertRaises(ValueError):
            mod.present("vpn",healthy)

    def test_vpn_request_requires_same_owner_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            key=Path(tmp)/"id_ed25519";key.write_text("test only")
            def runner(cmd,**kwargs):
                self.assertEqual(json.loads(kwargs["input"]),
                    {"version":1,"action":"downloads_status"})
                result={"success":True,"version":1,
                        "downloaders":[{"service":"qbittorrent",
                                        "gateway_bound":True,
                                        "gateway_healthy":True}]}
                return subprocess.CompletedProcess(cmd,0,json.dumps(result).encode(),b"")
            with patch.object(mod,"KEY",key):
                self.assertEqual(mod.fetch("100.121.156.34","optiplex",
                                           "vpn",runner=runner),
                                 "VPN\tHEALTHY\tother")

    def test_add_only_explicit_client_request(self):
        self.assertEqual(self.call("add","bigdisk","Movies/Horror",MAGNET),
                         "SUBMITTED")

    def test_bad_destinations_and_magnets_fail_before_ssh(self):
        for action,root,path,magnet in [
            ("browse","/etc","",None),
            ("browse","bigdisk","../foo",None),
            ("add","bigdisk","Movies/Horror","https://example.org"),
            ("add","bigdisk","Movies/Horror","magnet:?dn=bad"),
        ]:
            with self.subTest(action=action,path=path):
                with tempfile.TemporaryDirectory() as tmp:
                    key=Path(tmp)/"id";key.write_text("test only")
                    with patch.object(mod,"KEY",key),self.assertRaises(ValueError):
                        mod.fetch("100.121.156.34","optiplex",action,root,path,
                                  magnet,runner=lambda *a,**kw:self.fail("SSH must not run"))

    def test_fake_response_cannot_grant_add_or_expose_paths(self):
        for output in ({"success":False,"status":"denied"},
                       {"success":True,"status":"idle"},
                       {"success":True,"status":"submitted",
                        "save_path":"/etc/ssh"}):
            if output.get("status")=="submitted":
                # Only the status is exposed; extra private fields are ignored.
                self.assertEqual(mod.present("add",output),"SUBMITTED")
            else:
                with self.assertRaises(ValueError):
                    mod.present("add",output)

if __name__=="__main__":
    unittest.main()
