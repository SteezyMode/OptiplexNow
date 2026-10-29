"""No-network contract checks for isolated, bounded qBittorrent searches."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from download_inventory import InventoryError
from download_search import (SearchError, checked_magnet, checked_query,
                             search_once)

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
                assert command[-1].endswith("/results?id=42&limit=100&offset=0")
                if self.fail_get:
                    return subprocess.CompletedProcess(command, 1, b"Internal Error", b"")
                out = json.dumps(self.result).encode()
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
