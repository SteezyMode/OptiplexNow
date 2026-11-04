"""Offline DroppedNeedle REST companion-session and request integration tests."""
from __future__ import annotations

import io
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
from urllib.parse import urlsplit,parse_qs
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import music_rest as rest


TOKEN="REST-companion-token-12345"
ALBUM="550e8400-e29b-41d4-a716-446655440000"


class FakeSecret:
    COLLECTION_DEFAULT="default"
    saved={}
    @classmethod
    def password_lookup_sync(cls,schema,attributes,cancellable):
        return cls.saved.get(attributes["server"])
    @classmethod
    def password_store_sync(cls,schema,attributes,collection,label,value,cancellable):
        assert collection=="default" and "Bruiser Music" in label
        cls.saved[attributes["server"]]=value
        return True
    @classmethod
    def password_clear_sync(cls,schema,attributes,cancellable):
        cls.saved.pop(attributes["server"],None)
        return True


def secret_provider():
    return FakeSecret,object()


class FakeDroppedNeedle(BaseHTTPRequestHandler):
    observed=[]
    def log_message(self,*args):pass
    def handle_action(self):
        path=urlsplit(self.path)
        parsed=parse_qs(path.query)
        data=b""
        if self.command=="POST":
            data=self.rfile.read(int(self.headers.get("Content-Length",0)))
        token=self.headers.get("Authorization")
        type(self).observed.append((self.command,path.path,parsed,
                                    token,self.headers.get("Cookie"),data))
        if token!="Bearer "+TOKEN:
            self.send_response(401);self.end_headers();return
        if path.path=="/api/v1/auth/sessions":
            result={"sessions":[]};status=200
        elif path.path=="/api/v1/search":
            result={"artists":[],"albums":[{"type":"album",
                 "musicbrainz_id":ALBUM,"title":"My next album",
                 "artist":"Some Band","in_library":False,
                 "requested":False}]};status=200
        elif path.path=="/api/v1/requests/new":
            payload=json.loads(data)
            if payload!={"musicbrainz_id":ALBUM}:
                self.send_response(400);self.end_headers();return
            result={"id":"request01","status":"queued"};status=202
        elif path.path=="/api/v1/downloads/activity-summary":
            result={"active_count":1,"held_count":0,"failed_count":0};status=200
        elif path.path=="/api/v1/downloads":
            result={"tasks":[{"id":"task1","status":"downloading",
                               "release_group_mbid":ALBUM}]};status=200
        elif path.path=="/api/v1/discover":
            result={"sections":[]};status=200
        else:
            self.send_response(404);self.end_headers();return
        raw=json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):self.handle_action()
    def do_POST(self):self.handle_action()


class RestAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host=ThreadingHTTPServer(("127.0.0.1",0),FakeDroppedNeedle)
        cls.thread=threading.Thread(target=cls.host.serve_forever,daemon=True)
        cls.thread.start()
        cls.base="http://127.0.0.1:%d"%cls.host.server_port
    @classmethod
    def tearDownClass(cls):
        cls.host.shutdown()
        cls.host.server_close()
        cls.thread.join(timeout=3)
    def setUp(self):
        FakeDroppedNeedle.observed.clear()
        FakeSecret.saved.clear()

    def test_onetime_link_verify_save_and_reconnect(self):
        self.assertRaises(rest.MusicRESTError,rest.get_session,self.base,secret_provider)
        rest.save_session(self.base,TOKEN,secret_provider)
        self.assertEqual(rest.get_session(self.base,secret_provider),TOKEN)
        self.assertIn(rest.canonical_url(self.base),FakeSecret.saved)
        self.assertEqual(FakeDroppedNeedle.observed[0][1],"/api/v1/auth/sessions")
        self.assertIsNone(FakeDroppedNeedle.observed[0][4])
        rest.clear_session(self.base,secret_provider)
        self.assertRaises(rest.MusicRESTError,rest.get_session,self.base,secret_provider)

    def test_existing_request_api_is_used_with_authorized_bearer(self):
        catalog=rest.request(self.base,"search",token=TOKEN,value="dream pop")
        self.assertEqual(catalog["albums"][0]["musicbrainz_id"],ALBUM)
        result=rest.request(self.base,"request",token=TOKEN,value=ALBUM)
        self.assertEqual(result["status"],"queued")
        activity=rest.request(self.base,"activity",token=TOKEN)
        self.assertEqual(activity["active_count"],1)
        downloads=rest.request(self.base,"downloads",token=TOKEN,value=ALBUM)
        all_downloads=rest.request(self.base,"downloads",token=TOKEN)
        self.assertEqual(all_downloads["tasks"][0]["status"],"downloading")
        self.assertEqual(downloads["tasks"][0]["status"],"downloading")
        observed=FakeDroppedNeedle.observed
        self.assertEqual([r[1] for r in observed],[
           "/api/v1/search","/api/v1/requests/new",
           "/api/v1/downloads/activity-summary","/api/v1/downloads",
           "/api/v1/downloads"])
        self.assertEqual(observed[0][2]["q"],["dream pop"])
        self.assertEqual(observed[1][0],"POST")
        self.assertEqual(json.loads(observed[1][5]),{"musicbrainz_id":ALBUM})
        self.assertTrue(all(r[3]=="Bearer "+TOKEN and r[4] is None for r in observed))
        self.assertNotIn(TOKEN," ".join(str(r[1:3]) for r in observed))

    def test_secret_never_reaches_cli_arguments_or_wrong_host(self):
        rest.save_session(self.base,TOKEN,secret_provider)
        self.assertRaises(rest.MusicRESTError,rest.get_session,
                          "http://127.0.0.1:8888",secret_provider)
        for invalid in ("http://8.8.8.8","http://public.example.test",
                        "http://user:password@127.0.0.1",
                        "https://example.test/?key=secret"):
            with self.subTest(invalid=invalid),self.assertRaises(rest.MusicRESTError):
                rest.get_session(invalid,secret_provider)
        self.assertNotIn(TOKEN,str(FakeSecret.saved.keys()))
        self.assertNotIn(TOKEN,str(rest.ALLOWED))

    def test_rejects_non_album_and_injection_before_any_request(self):
        for bad in ("not-a-uuid","../other",ALBUM+"?secret=true","",None):
            with self.subTest(bad=bad),self.assertRaises(rest.MusicRESTError):
                rest.request(self.base,"request",token=TOKEN,value=bad)
        for bad in ("", "x"*201, "\n",None):
            with self.subTest(bad=bad),self.assertRaises(Exception):
                rest.request(self.base,"search",token=TOKEN,value=bad)
        self.assertFalse(FakeDroppedNeedle.observed)

    def test_real_download_queue_states_are_sanitized_and_not_equated_to_library(self):
        rows=rest._download_rows({"items":[
            {"release_group_mbid":ALBUM,"status":"queued","progress_percent":0},
            {"release_group_mbid":ALBUM,"status":"downloading","progress_percent":42},
            {"release_group_mbid":ALBUM,"status":"completed","progress_percent":100},
            {"release_group_mbid":"not-a-uuid","status":"downloading","progress_percent":100},
        ]})
        self.assertEqual(rows,ALBUM+"\tDownloading 42%\n")
        self.assertNotIn("Ready",rows)
        self.assertEqual(rest._download_rows({"items":[
            {"release_group_mbid":ALBUM,"status":"completed",
             "progress_percent":100}]}),
             ALBUM+"\tDownloaded — check library\n")
        self.assertEqual(rest._download_rows({"items":[
            {"release_group_mbid":ALBUM,"status":"held_for_review",
             "progress_percent":0}]}),
             ALBUM+"\tNeeds review\n")
        self.assertEqual(rest._download_rows({"items":[
            {"release_group_mbid":ALBUM,"status":"downloading",
             "progress_percent":0,"held_for_review":True}]}),
             ALBUM+"\tNeeds review\n")
        self.assertEqual(rest._download_rows({"items":[
            {"release_group_mbid":ALBUM,"status":"downloading",
             "progress_percent":"oops"}]}),
             ALBUM+"\tDownloading 0%\n")

    def test_upstream_discover_sections_become_real_card_groups(self):
        album_id="9c1a1111-2dd3-4000-8111-7e9000010000"
        artist_id="9c1a1111-2dd3-4000-8111-7e9000010001"
        sections={"fresh_releases":{"title":"Fresh releases","type":"albums",
                   "items":[{"name":"New record","mbid":album_id,
                             "artist_name":"Band","in_library":False}]},
                  "artists_you_might_like":{"title":"For you","type":"artists",
                   "items":[{"name":"New artist","mbid":artist_id,
                             "in_library":False}]}}
        import base64
        rows=[[base64.b64decode(x).decode() for x in line.split("\t")]
              for line in rest._discover_rows(sections).splitlines()]
        self.assertEqual([r[0] for r in rows],["section","catalog_album"])
        self.assertEqual(rows[0][2],"Fresh releases")
        self.assertEqual(rows[1][1],album_id)
        self.assertIn("Not in library",rows[1][3])
        self.assertNotIn(artist_id,[r[1] for r in rows])

    def test_missing_bearer_is_not_an_open_rest_request(self):
        with self.assertRaises(rest.MusicRESTError):
            rest.request(self.base,"search",token="this-is-invalid-token",value="rock")

    def test_rows_filter_owned_albums_and_preserve_valid_mbids(self):
        rows=rest._rows({"albums":[{"musicbrainz_id":ALBUM,
                   "title":"Album","artist":"Band","in_library":False},
                  {"musicbrainz_id":ALBUM,"title":"Already owned",
                   "artist":"Band","in_library":True},
                  {"musicbrainz_id":"xx","title":"Bad id","in_library":False}]})
        import base64
        lines=[[base64.b64decode(x).decode() for x in line.split("\t")]
               for line in rows.splitlines()]
        self.assertEqual(len(lines),1)
        self.assertEqual(lines[0][:3],["catalog_album",ALBUM,"Album"])


if __name__=="__main__":
    unittest.main()
