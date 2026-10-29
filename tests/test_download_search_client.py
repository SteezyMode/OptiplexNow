"""No-network tests for bounded, owner-bound native search transport."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("now_search_client",
                                           ROOT/"src"/"download-search-client.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
MAGNET="magnet:?xt=urn:btih:"+"f"*40

class SearchClientTests(unittest.TestCase):
    def payload(self,query="Ubuntu ISO", response=None,full=False):
        response=response or {"success":True,"service":"qbittorrent",
            "status":"Stopped","partial":False,"total":2,"results":[
                {"name":"Ubuntu test","bytes":1000,"seeders":3,
                 "can_add":True,"magnet":MAGNET},
                {"name":"no\tmagnet\nfrom plugin","bytes":-1,"seeders":-1,
                 "can_add":False,"magnet":None}]}
        with tempfile.TemporaryDirectory() as tmp:
            key=Path(tmp)/"id_ed25519"
            key.write_text("testing only")
            def runner(cmd,**kwargs):
                self.assertEqual(cmd[0],"ssh")
                self.assertIn("IdentitiesOnly=yes",cmd)
                self.assertIn("StrictHostKeyChecking=yes",cmd)
                self.assertEqual(cmd[-1],"optiplex@100.121.156.34")
                self.assertEqual(kwargs["timeout"],65)
                expected={"version":1,"action":"downloads_search","query":query.strip()}
                if full:
                    expected["full"]=True
                self.assertEqual(json.loads(kwargs["input"]),expected)
                return subprocess.CompletedProcess(cmd,0,json.dumps(response).encode(),b"")
            with patch.object(mod,"KEY",key):
                return mod.fetch("100.121.156.34","optiplex",query,full=full,runner=runner)

    def test_thorough_mode_is_explicit_and_bounded(self):
        quick=self.payload()
        full=self.payload(full=True)
        self.assertEqual(quick,full)
        with self.assertRaisesRegex(ValueError,"search depth"):
            self.payload(full="true")

    def test_safe_search_results_keep_only_validated_magnet_for_local_add(self):
        output=self.payload()
        self.assertEqual(output,
            "SEARCH\t0\t2\nRESULT\t1000\t3\t1\tUbuntu test\t"+MAGNET+"\n"
            "RESULT\t-1\t-1\t0\tno magnet from plugin\t-")
        self.assertIn(MAGNET,output)
        self.assertNotIn("https://",output)

    def test_stream_fetch_yields_multiple_sanitized_frames(self):
        response={"success":True,"service":"qbittorrent",
                  "status":"Running","partial":True,"total":1,
                  "results":[{"name":"Big","bytes":40_000_000_000,
                              "seeders":4,"can_add":True,"magnet":MAGNET}]}
        second={"success":True,"service":"qbittorrent",
                "status":"Stopped","partial":False,"total":2,
                "results":response["results"]+[{
                    "name":"Small","bytes":4_000_000_000,
                    "seeders":12,"can_add":True,"magnet":MAGNET}]}
        observed={}
        class FakeProcess:
            def __init__(self):
                self.stdin=io.BytesIO()
                self.stdout=io.BytesIO(
                    (json.dumps(response)+"\n"+json.dumps(second)+"\n").encode())
                self.returncode=None
            def wait(self,timeout=0):
                self.returncode=0
                return 0
            def poll(self):
                return self.returncode
        def popen(cmd,**kwargs):
            self.assertEqual(cmd[0],"ssh")
            self.assertEqual(cmd[-1],"optiplex@100.121.156.34")
            observed["proc"]=FakeProcess()
            return observed["proc"]
        with tempfile.TemporaryDirectory() as tmp:
            key=Path(tmp)/"id_ed25519"
            key.write_text("testing only")
            with patch.object(mod,"KEY",key):
                output=io.StringIO()
                with contextlib.redirect_stdout(output):
                    mod.stream_fetch("100.121.156.34","optiplex","Ubuntu ISO",
                                     popen=popen)
        frames=output.getvalue().splitlines()
        self.assertEqual(len(frames),3)
        self.assertEqual(frames[-1],"DONE")
        import base64
        first=base64.b64decode(frames[0].split("\t",1)[1]).decode()
        final=base64.b64decode(frames[1].split("\t",1)[1]).decode()
        self.assertIn("Big",first)
        self.assertNotIn("Small",first)
        self.assertIn("Small",final)

    def test_stream_accepts_all_forty_bounded_poll_frames(self):
        frame={"success":True,"service":"qbittorrent","status":"Running",
               "partial":True,"total":0,"append":False,"results":[]}
        class FakeProcess:
            def __init__(self):
                self.stdin=io.BytesIO()
                self.stdout=io.BytesIO(
                    (json.dumps(frame)+"\n").encode()*40)
                self.returncode=None
            def wait(self,timeout=0):
                self.returncode=0
                return 0
            def poll(self):
                return self.returncode
        with tempfile.TemporaryDirectory() as tmp:
            key=Path(tmp)/"id_ed25519"
            key.write_text("fixture")
            with patch.object(mod,"KEY",key):
                output=io.StringIO()
                with contextlib.redirect_stdout(output):
                    mod.stream_fetch("100.121.156.34","optiplex","Ubuntu ISO",
                                     popen=lambda *args,**kw:FakeProcess())
        lines=output.getvalue().splitlines()
        self.assertEqual(len(lines),41)
        self.assertEqual(lines[-1],"DONE")

    def test_publication_date_seven_field_wire_and_legacy_six(self):
        response={"success":True,"service":"qbittorrent",
                  "status":"Running","partial":True,"total":1,
                  "results":[{"name":"Old film","bytes":2000,
                              "seeders":3,"can_add":True,"magnet":MAGNET,
                              "published":1727740800}]}
        full=self.payload(response=response)
        self.assertTrue(full.endswith("\t1727740800"))
        response["results"][0].pop("published")
        legacy=self.payload(response=response)
        self.assertTrue(legacy.endswith("\t"+MAGNET))
        response["results"][0]["published"]="newest"
        with self.assertRaises(ValueError):
            self.payload(response=response)

    def test_leechers_eighth_field_and_incremental_append(self):
        response={"success":True,"service":"qbittorrent","status":"Running",
                  "partial":True,"total":35,"append":True,
                  "results":[{"name":"Film 1080p","bytes":4500000000,
                              "seeders":20,"leechers":4,
                              "published":1730000000,
                              "can_add":True,"magnet":MAGNET}]}
        output=self.payload(response=response)
        self.assertTrue(output.startswith("APPEND\t1\t35\n"))
        self.assertTrue(output.endswith("\t1730000000\t4"))
        response["results"][0]["leechers"]="4"
        with self.assertRaises(ValueError):
            self.payload(response=response)
        response["results"][0]["leechers"]=-1
        output=self.payload(response=response)
        self.assertTrue(output.endswith("\t-1"))

    def test_100_results_pass_as_one_bounded_payload_for_gtk_paging(self):
        entries=[{"name":f"Linux ISO {i}","bytes":1000+i,
                  "seeders":i,"can_add":True,"magnet":MAGNET}
                 for i in range(100)]
        response={"success":True,"service":"qbittorrent",
                  "status":"Running","partial":True,
                  "total":150,"results":entries}
        output=self.payload(response=response)
        self.assertEqual(len(output.splitlines()),101)
        self.assertTrue(output.startswith("SEARCH\t1\t150"))
        self.assertLess(len(output.encode()),180000)
        response["results"].append(entries[0])
        with self.assertRaises(ValueError):
            self.payload(response=response)

    def test_reject_bogus_responses(self):
        invalid=[
            {"success":False,"status":"search_unavailable"},
            {"success":True,"service":"qbittorrent","status":"Unknown",
             "partial":False,"total":1,"results":[]},
            {"success":True,"service":"qbittorrent","status":"Stopped",
             "partial":1,"total":1,"results":[]},
            {"success":True,"service":"qbittorrent","status":"Stopped",
             "partial":False,"total":True,"results":[]},
            {"success":True,"service":"qbittorrent","status":"Stopped",
             "partial":False,"total":1,"results":[{"name":"test","bytes":1,
                 "seeders":0,"can_add":True,"magnet":None}]},
        ]
        for response in invalid:
            with self.subTest(response=response),self.assertRaises(ValueError):
                self.payload(response=response)

    def test_missing_key_and_bad_queries_stop_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mod,"KEY",Path(tmp)/"missing"):
                with self.assertRaises(ValueError):
                    mod.fetch("100.121.156.34","optiplex","Ubuntu",
                              runner=lambda *a,**kw:self.fail("No SSH"))
        for query in ("a","", "x"*97,"bad\nquery",12,None):
            with self.subTest(query=query),self.assertRaises(ValueError):
                self.payload(query=query)

    def test_invalid_host_and_user(self):
        self.assertFalse(mod.valid_host("-oProxyCommand=evil"))
        self.assertFalse(mod.valid_user("-evil"))
        self.assertFalse(mod.valid_user("spaced user"))

if __name__=="__main__":
    unittest.main()
