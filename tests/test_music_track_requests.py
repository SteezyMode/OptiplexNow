"""Explicit remote song acquisition uses only an approved DroppedNeedle bearer."""
import base64
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import music_rest as rest

A="11111111-1111-4111-8111-111111111111"
R="22222222-2222-4222-8222-222222222222"
BASE="http://127.0.0.1:8688"
TOKEN="scoped-companion-session-token-1234"

def encoded(*items):
    return "|".join(quote(x,safe="") for x in items)

class MockResponse:
    def __init__(self,body):self.body=body
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,*args):return self.body

class MockOpener:
    def __init__(self,body):self.body=body;self.requests=[]
    def open(self,req,timeout):
        self.requests.append(req)
        return MockResponse(self.body)

class TrackRequestTests(unittest.TestCase):
    def test_album_track_list_is_read_only_and_reports_real_recording_ids(self):
        opener=MockOpener(b'{"tracks":[{"recording_id":"'+R.encode()+
                          b'","title":"Song One"},{"title":"Unidentified"}]}')
        with patch.object(rest,"build_opener",return_value=opener):
            result=rest.request(BASE,"catalog_tracks",token=TOKEN,
                                value=encoded(A,"Circa Survive","Blue Sky Noise"))
        fields=[[base64.b64decode(x).decode() for x in line.split("\t")]
                for line in rest._catalog_track_rows(result).splitlines()]
        self.assertEqual(len(fields),1)
        self.assertEqual(fields[0][:4],["catalog_track",R,"Song One","Circa Survive"])
        self.assertEqual(fields[0][5],"Blue Sky Noise")
        self.assertEqual(opener.requests[0].get_method(),"GET")
        self.assertTrue(opener.requests[0].full_url.endswith("/api/v1/albums/"+A+"/tracks"))

    def test_track_request_uses_scoped_bearer_and_exact_recording(self):
        opener=MockOpener(b'{"status":"queued"}')
        value=encoded(R,"Circa Survive","Get Out","Blue Sky Noise",A)
        with patch.object(rest,"build_opener",return_value=opener):
            result=rest.request(BASE,"request_track",token=TOKEN,value=value)
        req=opener.requests[0]
        self.assertEqual(result["status"],"queued")
        self.assertEqual(req.get_method(),"POST")
        self.assertEqual(req.full_url,BASE+"/api/v1/tracks/"+R+"/request")
        self.assertEqual(req.headers["Authorization"],"Bearer "+TOKEN)
        import json
        self.assertEqual(json.loads(req.data),{
            "artist_name":"Circa Survive","track_title":"Get Out",
            "album_title":"Blue Sky Noise","release_group_mbid":A})
        self.assertNotIn(TOKEN,req.full_url)

    def test_invalid_recordings_and_metadata_are_rejected_before_network(self):
        for value in ("", "not-a-uuid|Artist|Song|Album|"+A,
                      encoded(R,"","Song","Album",A),
                      encoded(R,"Artist","Song","Album","wrong"),
                      encoded(R,"Artist","bad\\nname","Album",A),
                      encoded(R,"Artist","Song")):
            with self.subTest(value=value),self.assertRaises(rest.MusicRESTError):
                rest.request(BASE,"request_track",token=TOKEN,value=value)

    def test_native_ui_contains_explicit_non_autonomous_song_action(self):
        code=(ROOT/"src/ui_music.c").read_text()
        self.assertIn('gtk_button_new_with_label("Add Song")',code)
        self.assertIn('"request_track":"request"',code)
        self.assertIn('query_start(view,"catalog_tracks",v,heading)',code)
        self.assertNotIn('query_start(view,"request_track"',code)

if __name__=="__main__":
    unittest.main()
