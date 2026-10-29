"""No-network contract checks for isolated, bounded qBittorrent searches."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from download_inventory import InventoryError
from download_search import (SearchError, checked_magnet, checked_query,
                             search_once, stream_search)

VPN = "a" * 64
QBIT = "b" * 64


def topology(*, healthy="healthy", mode="container:" + VPN):
    return [
        {"Id": VPN, "Name": "/music-vpn",
         "Config": {"Image": "qmcgaw/gluetun:v3.41", "Env": []},
         "HostConfig": {"NetworkMode": "bridge"},
         "State": {"Health": {"Status": healthy}}},
        {"Id": QBIT, "Name": "/qbittorrent-vpn",
         "Config": {"Image": "lscr.io/linuxserver/qbittorrent:5.1.4",
                    "Env": ["WEBUI_PORT=8085"]},
         "HostConfig": {"NetworkMode": mode}, "State": {}},
    ]


MAGNET = "magnet:?xt=urn:btih:" + "f" * 40


class FakeAPI:
    def __init__(self, *, result=None, healthy="healthy", mode="container:" + VPN):
        self.records = topology(healthy=healthy, mode=mode)
        self.commands = []
        self.result = result or {
            "status": "Stopped", "total": 2, "results": [
                {"fileName": "Example Linux distro", "fileSize": 900,
                 "nbSeeders": 3, "fileUrl": MAGNET},
                {"fileName": "Website-only plugin result", "fileSize": 800,
                 "nbSeeders": 1, "fileUrl": "https://example.org/info.html"},
            ]}
        self.fail_get = False
        self.sid = "test+search/42="

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        if command[:2] == ["docker", "ps"]:
            return subprocess.CompletedProcess(
                command, 0, "\n".join(r["Id"] for r in self.records), "")
        if command[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(
                command, 0, json.dumps(self.records), "")
        assert command[:3] == ["docker", "exec", VPN]
        assert "127.0.0.1:8085/api/v2/search/" in command[-1]
        assert not any(part in command[-1] for part in
                       ("example.org", "localhost.evil", "file:///"))
        assert "--header" in command
        assert "Referer: http://127.0.0.1:8085/" in command
        if command[-1].endswith("/start"):
            assert "-S" in command
            assert not any(c.startswith("Cookie:") for c in command)
            assert "--post-data=pattern=Ubuntu+ISO&plugins=enabled&category=all" in command
            out = b'{"id":42}'
            headers = b"  HTTP/1.1 200 OK\r\n  set-cookie: SID=test+search/42=; HttpOnly\r\n"
        else:
            assert "-S" not in command
            assert "Cookie: SID=" + self.sid in command
            headers = b""
            if command[-1].endswith("/stop") or command[-1].endswith("/delete"):
                assert "--post-data=id=42" in command
                out = b""
            else:
                uri=urlsplit(command[-1])
                assert uri.path.endswith("/results")
                params=parse_qs(uri.query)
                assert params["id"]==["42"]
                offset=int(params["offset"][0])
                limit=int(params["limit"][0])
                assert 0<=offset<=1000 and 1<=limit<=100
                if self.fail_get:
                    return subprocess.CompletedProcess(command, 1, b"Internal Error", b"")
                batch={**self.result,
                       "results":self.result["results"][offset:offset+limit]}
                out=json.dumps(batch).encode()
        return subprocess.CompletedProcess(command, 0, out, headers)


class DownloadSearchTests(unittest.TestCase):
    def test_search_magnet_and_unsupported_html_result(self):
        fake = FakeAPI()
        data = search_once("Ubuntu ISO", runner=fake, sleeper=lambda x: None)
        self.assertFalse(data["partial"])
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["results"]), 2)
        self.assertTrue(data["results"][0]["can_add"])
        self.assertEqual(data["results"][0]["magnet"], MAGNET)
        self.assertFalse(data["results"][1]["can_add"])
        self.assertIsNone(data["results"][1]["magnet"])
        self.assertEqual([x[-1].split("/")[-1] for x in fake.commands[-2:]],
                         ["stop", "delete"])
        self.assertFalse(any("torrents/add" in str(c) for c in fake.commands))

    def test_missing_sid_fails_closed_and_does_not_poll(self):
        fake = FakeAPI()
        original = fake.__call__

        def without_sid(command, **kwargs):
            result = original(command, **kwargs)
            if command[-1].endswith("/start"):
                return subprocess.CompletedProcess(command, 0, result.stdout, b"")
            return result

        with self.assertRaisesRegex(SearchError, "session unavailable"):
            search_once("Ubuntu ISO", runner=without_sid, sleeper=lambda x: None)
        self.assertFalse(any("api/v2/search/results" in str(c) for c in fake.commands))

    def test_running_result_returns_explicit_partial(self):
        fake = FakeAPI(result={"status":"Running","total":0,"results":[]})
        data = search_once("Ubuntu ISO", runner=fake, sleeper=lambda x: None)
        self.assertTrue(data["partial"])
        self.assertEqual(data["results"], [])
        urls = [c[-1] for c in fake.commands if "api/v2/search/results" in c[-1]]
        self.assertEqual(len(urls), 12)

    def test_running_results_return_after_first_poll_and_cleanup(self):
        fake = FakeAPI(result={"status":"Running","total":24,"results":[
            {"fileName":"Linux ISO","fileSize":2048,"nbSeeders":12,
             "fileUrl":MAGNET}]})
        sleeps=[]
        data = search_once("Ubuntu ISO", runner=fake, sleeper=sleeps.append)
        self.assertTrue(data["partial"])
        self.assertEqual(len(data["results"]),1)
        self.assertEqual(data["results"][0]["magnet"],MAGNET)
        self.assertEqual(sleeps,[1])
        queries=[c for c in fake.commands
                 if "/api/v2/search/results?" in c[-1]]
        self.assertEqual(len(queries),1)
        self.assertEqual([c[-1].rsplit("/",1)[-1]
                          for c in fake.commands[-2:]],["stop","delete"])

    def test_thorough_search_collects_later_smaller_results(self):
        fake = FakeAPI(result={"status":"Running","total":25,"results":[
            {"fileName":"Large 2160p","fileSize":40_000_000_000,
             "nbSeeders":12,"fileUrl":MAGNET}]})
        original=fake.__call__
        polls=[]
        def runner(command, **kwargs):
            if "/api/v2/search/results?" in command[-1]:
                polls.append(len(polls)+1)
                if len(polls)>=3:
                    fake.result={"status":"Stopped","total":2,"results":[
                        {"fileName":"Large 2160p","fileSize":40_000_000_000,
                         "nbSeeders":12,"fileUrl":MAGNET},
                        {"fileName":"Normal 1080p","fileSize":4_000_000_000,
                         "nbSeeders":9,"fileUrl":MAGNET}]}
            return original(command,**kwargs)
        sleeps=[]
        data=search_once("Ubuntu ISO",full=True,runner=runner,sleeper=sleeps.append)
        self.assertFalse(data["partial"])
        self.assertEqual(len(data["results"]),2)
        self.assertEqual(data["results"][1]["name"],"Normal 1080p")
        self.assertEqual(sleeps,[1,1,1])
        self.assertEqual(len(polls),3)
        self.assertEqual([c[-1].rsplit("/",1)[-1]
                          for c in fake.commands[-2:]],["stop","delete"])

    def test_publication_dates_are_bounded_and_optional(self):
        cases=[(1767225600,1767225600),(None,-1),(-1,-1),(0,-1)]
        for value,expected in cases:
            result={"status":"Stopped","total":1,"results":[{
                "fileName":"Public domain video","fileSize":3000,
                "nbSeeders":8,"fileUrl":MAGNET}]}
            if value is not None:
                result["results"][0]["pubDate"]=value
            data=search_once("Ubuntu ISO",runner=FakeAPI(result=result),
                             sleeper=lambda _:None)
            self.assertEqual(data["results"][0]["published"],expected)
        for invalid in ("today",True,253402300800,-2):
            result={"status":"Stopped","total":1,"results":[{
                "fileName":"Public domain video","fileSize":3000,
                "nbSeeders":8,"fileUrl":MAGNET,"pubDate":invalid}]}
            with self.subTest(value=invalid),self.assertRaises(SearchError):
                search_once("Ubuntu ISO",runner=FakeAPI(result=result),
                            sleeper=lambda _:None)

    def test_stream_collects_later_1080p_without_restarting_search(self):
        fake=FakeAPI(result={"status":"Running","total":1,"results":[
            {"fileName":"Large 2160p","fileSize":40_000_000_000,
             "nbSeeders":9,"fileUrl":MAGNET}]})
        base=fake.__call__
        polls=[]
        def runner(command,**kwargs):
            if "/api/v2/search/results?" in command[-1]:
                polls.append(True)
                if len(polls)==3:
                    fake.result={"status":"Stopped","total":2,"results":[
                        {"fileName":"Large 2160p","fileSize":40_000_000_000,
                         "nbSeeders":9,"fileUrl":MAGNET},
                        {"fileName":"Smaller 1080p","fileSize":4_000_000_000,
                         "nbSeeders":17,"fileUrl":MAGNET}]}
            return base(command,**kwargs)
        updates=[]
        result=stream_search("Ubuntu ISO",updates.append,runner=runner,
                             sleeper=lambda _:None)
        self.assertEqual([len(x["results"]) for x in updates],[1,1])
        self.assertFalse(result["partial"])
        self.assertTrue(updates[-1]["append"])
        self.assertEqual(updates[-1]["results"][0]["name"],"Smaller 1080p")
        urls=[c[-1] for c in fake.commands]
        self.assertEqual(sum(url.endswith("/start") for url in urls),1)
        self.assertEqual(len(polls),3)
        self.assertEqual(sum("offset=1" in url for url in urls),2)
        self.assertTrue(urls[-2].endswith("/stop"))
        self.assertTrue(urls[-1].endswith("/delete"))
        self.assertFalse(any("torrents/add" in str(c) for c in fake.commands))

    def test_thorough_mode_rejects_non_boolean_before_network(self):
        with self.assertRaisesRegex(SearchError,"search depth"):
            search_once("Ubuntu ISO",full="yes",
                runner=lambda *a,**kw:self.fail("No Docker"))

    def test_results_can_fill_multiple_ui_pages(self):
        fake=FakeAPI(result={"status":"Stopped","total":100,
             "results":[{"fileName":f"Linux ISO {i}","fileSize":500+i,
                         "nbSeeders":i,"fileUrl":MAGNET} for i in range(100)]})
        data=search_once("Ubuntu ISO",runner=fake,sleeper=lambda _:None)
        self.assertEqual(len(data["results"]),100)
        self.assertEqual(data["total"],100)

    def test_reject_query_before_docker(self):
        for query in ("", "x", "x" * 97, "hello\nworld",
                      "two\x00names", None, 12, " "):
            with self.subTest(query=query), self.assertRaises(SearchError):
                search_once(query, runner=lambda *a,**kw: self.fail("No Docker"))

    def test_no_vpn_bind_or_unhealthy(self):
        for cfg in ({"mode":"bridge"},{"healthy":"unhealthy"}):
            fake = FakeAPI(**cfg)
            with self.subTest(cfg=cfg), self.assertRaises(InventoryError):
                search_once("Ubuntu ISO", runner=fake)
            self.assertFalse(any("api/v2/search/" in str(c) for c in fake.commands))

    def test_fail_closed_on_invalid_result_and_cleanup(self):
        invalid = [
            {"status":"Stopped","total":0,"results":[{}]},
            {"status":"Running","total":True,"results":[]},
            {"status":"Stopped","total":0,"results":{}},
            {"status":"Stopped","total":0,"results":[{"fileName":"a",
             "fileSize":1,"nbSeeders":False,"fileUrl":MAGNET}]},
            {"status":"Stopped","total":0,"results":[{"fileName":"a",
             "fileSize":1,"nbSeeders":2,"fileUrl":MAGNET}]*101},
        ]
        for result in invalid:
            fake=FakeAPI(result=result)
            with self.subTest(result=str(result)[:80]), self.assertRaises(SearchError):
                search_once("Ubuntu ISO", runner=fake, sleeper=lambda x:None)
            self.assertTrue(fake.commands[-1][-1].endswith("/delete"))

    def test_failed_result_query_still_cleans_own_job(self):
        fake=FakeAPI()
        fake.fail_get=True
        with self.assertRaises(SearchError):
            search_once("Ubuntu ISO",runner=fake,sleeper=lambda x:None)
        self.assertTrue(fake.commands[-1][-1].endswith("/delete"))

    def test_magnet_validation(self):
        self.assertEqual(checked_magnet(MAGNET), MAGNET)
        for value in ("https://example.org/magnet?xt=...",
                      "javascript:alert(1)", "file:///etc/passwd",
                      "magnet:?dn=title", "magnet:?xt=urn:btih:oops",
                      "magnet:?xt=urn:btih:"+"f"*40+"\n"):
            with self.subTest(value=value):
                self.assertIsNone(checked_magnet(value))


if __name__ == "__main__":
    unittest.main()
