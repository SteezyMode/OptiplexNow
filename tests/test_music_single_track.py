"""Optional single-song discovery and acquisition, with zero automatic requests."""
from __future__ import annotations

import base64
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import music_rest as rest
import music_subsonic as sub

A="11111111-1111-4111-8111-111111111111"
B="22222222-2222-4222-8222-222222222222"
C="33333333-3333-4333-8333-333333333333"
HOST="http://127.0.0.1:8688"
TOKEN="approved-companion-session-for-tests"

def decode(src):
    return [[base64.b64decode(v).decode("utf-8") for v in line.split("\t")]
            for line in src.splitlines()]

class SongDiscoveryTests(unittest.TestCase):
    def test_album_tracklist_emits_only_requestable_musicbrainz_recordings(self):
        result={"title":"Blue Sky Noise","artist_name":"Circa Survive",
                "tracks":[{"title":"Get Out","recording_id":A},
                          {"title":"Invalid","recording_id":"unknown"},
                          {"title":"Imaginary","recording_id":B}]}
        rows=decode(rest._album_tracks_rows(result,C))
        self.assertEqual([r[0] for r in rows],
                         ["catalog_album","catalog_track","catalog_track"])
        self.assertEqual(rows[1][:4],["catalog_track",A,"Get Out","Circa Survive"])
        self.assertEqual(rows[1][4],"dn-album:"+C)
        self.assertEqual(rows[1][5],"Blue Sky Noise")

    def test_recording_search_is_one_bounded_public_lookup(self):
        records={"recordings":[
            {"id":A,"title":"Pursuit of Happiness",
             "artist-credit":[{"name":"Kid Cudi","joinphrase":""}],
             "releases":[{"release-group":{"id":C,
                        "title":"Man on the Moon: The End of Day"}}]},
            {"id":"bogus","title":"Fake",
             "artist-credit":[{"name":"Nobody"}]}
        ]}
        class Response:
            def __enter__(self):return self
            def __exit__(self,*unused):pass
            def read(self,n):
                import json
                return json.dumps(records).encode("utf-8")
        class Opener:
            def open(self,req,timeout):
                self.url=req.full_url
                self.headers=req.headers
                self.timeout=timeout
                return Response()
        opener=Opener()
        with patch.object(rest,"build_opener",return_value=opener),\
             patch.object(rest,"get_session",side_effect=AssertionError(
                 "Public song searches must not read bearer secrets")):
            rows=decode(rest._song_search_rows("Pursuit of Happiness"))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0][:4],["catalog_track",A,
                                     "Pursuit of Happiness","Kid Cudi"])
        self.assertEqual(rows[0][4],"dn-album:"+C)
        parsed=urlsplit(opener.url)
        self.assertEqual(parsed.netloc,"musicbrainz.org")
        self.assertEqual(parsed.scheme,"https")
        self.assertEqual(parsed.path,"/ws/2/recording/")
        self.assertEqual(parse_qs(parsed.query)["limit"],["15"])
        self.assertNotIn(TOKEN,opener.url)
        self.assertLessEqual(opener.timeout,9)

    def test_track_request_is_exact_id_scoped_and_verified(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*unused):pass
            def read(self,n):return b'{"status":"queued","task_id":"test"}'
        class Opener:
            def open(self,req,timeout):
                self.req=req
                return Response()
        opener=Opener()
        metadata={"artist":"Kid Cudi","title":"Pursuit of Happiness",
                  "album":"Man on the Moon: The End of Day","rg":C}
        with patch.object(rest,"build_opener",return_value=opener):
            response=rest.request(HOST,"track_request",token=TOKEN,value=A,
                                  track=metadata)
        self.assertEqual(response["status"],"queued")
        self.assertEqual(opener.req.get_method(),"POST")
        self.assertEqual(urlsplit(opener.req.full_url).path,
                         "/api/v1/tracks/"+A+"/request")
        self.assertEqual(opener.req.headers.get("Authorization"),"Bearer "+TOKEN)
        self.assertNotIn(TOKEN,opener.req.full_url)
        import json
        body=json.loads(opener.req.data)
        self.assertEqual(body["track_title"],"Pursuit of Happiness")
        self.assertEqual(body["release_group_mbid"],C)

    def test_invalid_track_request_fails_closed(self):
        for mbid in ("bad","",A+"?x=1",None):
            with self.subTest(mbid=mbid),self.assertRaises(rest.MusicRESTError):
                rest.request(HOST,"track_request",token=TOKEN,value=mbid,
                             track={"title":"a","artist":"b"})
        with self.assertRaises(rest.MusicRESTError):
            rest.request(HOST,"track_request",token=TOKEN,value=A,
                         track={"artist":"Kid Cudi","title":"Pursuit","rg":"bad"})

    def test_client_includes_find_songs_and_request_button_but_no_automatic_acquisition(self):
        source=(ROOT/"src/ui_music.c").read_text()
        self.assertIn('gtk_button_new_with_label("Find Songs")',source)
        self.assertIn('query_start(view,"song_search",query,',source)
        self.assertIn('query_start(view,"album_tracks",id,',source)
        self.assertIn('gtk_button_new_with_label("Add Song")',source)
        self.assertIn('G_CALLBACK(music_request_track)',source)
        self.assertIn('argv[n++]="track_request";',source)
        # Requests occur only inside an actual clicked handler.
        first=source.index("static void music_request_track(")
        next_=source.index("static gboolean music_status_timeout(",first)
        self.assertIn('G_CALLBACK(music_request_track)',source[next_:])

if __name__ == "__main__":
    unittest.main()
