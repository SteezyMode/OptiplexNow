"""Real artist discography navigation must use exact MusicBrainz artist IDs.

No broad string-search fallback and no playback app password on the REST route.
All requests mocked: no dependence on a live music server.
"""
from __future__ import annotations
import base64
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import music_rest as rest
import music_subsonic as sub

A="11111111-1111-4111-8111-111111111111"
B="22222222-2222-4222-8222-222222222222"
C="33333333-3333-4333-8333-333333333333"
HOST="http://127.0.0.1:8688"
TOKEN="existing-approved-music-bearer-token"

def rows(raw):
    return [[base64.b64decode(field).decode("utf-8")
             for field in line.split("\t")]
            for line in raw.splitlines()]


class ArtistDiscographyTests(unittest.TestCase):
    def test_source_provides_real_artist_release_actions(self):
        gtk=(ROOT/"src"/"ui_music.c").read_text()
        self.assertIn('query_start(view,"artist_releases",mbid,heading)',gtk)
        self.assertIn('g_object_set_data_full(G_OBJECT(explore),"music-artist-mbid"',gtk)
        self.assertIn('!g_strcmp0(job->operation,"artist_releases")',gtk)
        self.assertIn('!g_strcmp0(operation,"artist_releases")',gtk)
        self.assertNotIn('query_start(view,"catalog",artist,"Discover artist")',gtk)

    def test_release_groups_render_all_release_types_and_owned_status(self):
        data={
            "albums":[{"id":A,"title":"Downtown Battle Mountain II","year":2011,
                       "in_library":False},
                      {"id":B,"title":"Owned album","year":2018,"in_library":True}],
            "eps":[{"id":C,"title":"EP Release","first_release_date":"2023-04-05",
                    "requested":True}],
            "singles":[{"id":A,"title":"Duplicate release"}],
        }
        parsed=rows(rest._artist_releases_rows(data))
        self.assertEqual([r[1] for r in parsed],[A,B,C])
        self.assertEqual([r[0] for r in parsed],["catalog_album"]*3)
        self.assertEqual(parsed[0][2],"Downtown Battle Mountain II")
        self.assertEqual(parsed[0][3],"Album · 2011 · Not in library")
        self.assertEqual(parsed[1][3],"Album · 2018 · In library")
        self.assertEqual(parsed[2][3],"EP · 2023 · Requested")
        self.assertEqual(parsed[2][4],"dn-album:"+C)

    def test_search_artist_in_my_library_is_still_available(self):
        result={"artists":[{"title":"Circa Survive","musicbrainz_id":A,
                             "in_library":True}],
                "albums":[{"title":"Outside album","musicbrainz_id":B,
                           "artist":"Other","in_library":False}]}
        self.assertEqual([x[0] for x in rows(rest._rows(result))],
                         ["catalog_artist","catalog_album"])
        self.assertEqual([x[0] for x in rows(sub._rows("catalog",{"catalog":result}))],
                         ["catalog_artist","catalog_album"])

    def test_invalid_artist_ids_fail_before_any_network(self):
        for bad in ("", "Circa Survive", "https://example.com", A+"?limit=100",
                    "../../../../etc/passwd", A+":200", None):
            with self.subTest(bad=bad),self.assertRaises(rest.MusicRESTError):
                rest.request(HOST,"artist_releases",token=TOKEN,value=bad)

    def test_artist_route_is_authenticated_no_redirects_or_secrets_in_url(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*unused):pass
            def read(self,n):return b'{"albums":[],"eps":[],"singles":[]}'
        class Opener:
            url=None
            header=None
            def open(self,req,timeout):
                self.url=req.full_url
                self.header=req.headers.get("Authorization")
                self.timeout=timeout
                return Response()
        opener=Opener()
        with patch.object(rest,"build_opener",return_value=opener):
            result=rest.request(HOST,"artist_releases",token=TOKEN,value=A)
        self.assertEqual(result["albums"],[])
        parsed=urlsplit(opener.url)
        self.assertEqual(parsed.path,"/api/v1/artists/"+A+"/releases")
        self.assertEqual(parse_qs(parsed.query),{"limit":["200"],"offset":["0"]})
        self.assertEqual(opener.header,"Bearer "+TOKEN)
        self.assertNotIn(TOKEN,opener.url)

    def test_artist_discography_cli_does_not_read_playback_password(self):
        class ForbiddenStdin:
            @property
            def buffer(self):raise AssertionError("Must never read playback credentials")
        fake={"albums":[{"id":A,"title":"Fresh album","year":2026}]}
        with patch.object(sub,"_auth_from_stdin",side_effect=AssertionError(
                 "Must not read a playback credential")) as auth,\
             patch.object(rest,"get_session",return_value=TOKEN),\
             patch.object(rest,"request",return_value=fake) as call,\
             patch.object(sub.sys,"stdin",ForbiddenStdin()),\
             patch.object(sub.sys,"stdout",io.StringIO()) as output:
            rc=sub.main([HOST,"artist_releases",B,"--format=rows"])
            decoded=rows(output.getvalue())
        self.assertEqual(rc,0)
        self.assertEqual(decoded[0][0:3],["catalog_album",A,"Fresh album"])
        call.assert_called_once_with(HOST,"artist_releases",token=TOKEN,value=B)
        auth.assert_not_called()


if __name__=="__main__":
    unittest.main()
