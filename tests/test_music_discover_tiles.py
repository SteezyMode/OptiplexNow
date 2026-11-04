"""Discover: user-driven, clickable tiles and scoped external catalog images.

No music acquisition happens during recommendation generation or browsing.
Offline-only; mock the network and the secret-bearing REST transport.
"""
from __future__ import annotations

import base64
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import music_rest as rest
import music_subsonic as sub

A="11111111-1111-4111-8111-111111111111"
B="22222222-2222-4222-8222-222222222222"
C="33333333-3333-4333-8333-333333333333"
BASE="http://127.0.0.1:8688"
TOKEN="authorized-bearer-secret-example"

def decode(rows):
    return [[base64.b64decode(item).decode("utf-8")
             for item in line.split("\t")]
            for line in rows.strip().splitlines()] if rows.strip() else []

class DiscoverTileTests(unittest.TestCase):
    def test_personal_seed_titles_change_with_real_likes(self):
        data={"because_you_listen_to":[
            {"seed_artist":"Circa Survive","section":{"title":"Generic","type":"artists",
                "items":[{"name":"Artist A","mbid":A,"in_library":False}]}},
            {"seed_artist":"Low","section":{"title":"Generic","type":"artists",
                "items":[{"name":"Artist B","mbid":B,"in_library":False}]}},
        ]}
        rows=decode(rest._discover_rows(data))
        sections=[x for x in rows if x[0]=="section"]
        self.assertEqual([x[2] for x in sections],
            ["Because You Listen to Circa Survive","Because You Listen to Low"])
        self.assertEqual([x[1] for x in rows if x[0]=="catalog_artist"],[A,B])

    def test_personalized_genre_mix_and_radio_picks_are_not_starved(self):
        data={
            "because_you_listen_to":[
                {"seed_artist":"Artist "+str(i),
                 "section":{"type":"artists","items":[
                     {"name":"Artist "+str(i),
                      "mbid":"00000000-0000-4000-8000-"+f"{i+1:012d}"}]}}
                for i in range(8)],
            "daily_mixes":[{"title":"Daily Mix 1 - Hip-Hop","type":"albums",
                "items":[{"name":"New beat","mbid":C,"artist_name":"Producer"}]}],
            "radio_sections":[{"title":"Radio: Circa Survive","type":"albums",
                "items":[{"name":"New album","mbid":A,"artist_name":"Similar band"}]}],
            "globally_trending":{"title":"Charts","type":"artists",
                "items":[{"name":"Famous","mbid":B}]},
        }
        data_rows=decode(rest._discover_rows(data))
        labels=[r[2] for r in data_rows if r[0]=="section"]
        self.assertIn("Daily Mix 1 - Hip-Hop",labels)
        self.assertIn("Artist Picks: Circa Survive",labels)
        self.assertIn("Charts",labels)
        self.assertLess(labels.index("Daily Mix 1 - Hip-Hop"),
                        labels.index("Charts"))
        self.assertFalse(any(x.startswith("Radio: ") for x in labels))
        self.assertEqual(sum(x.startswith("Because You Listen") for x in labels),2)

    def test_2011_album_is_missing_essential_not_fresh_release(self):
        # The 2011 Dance Gavin Dance album was surfaced under Fresh Releases
        # because the old GTK classifier silently mixed three source shelves.
        old={"name":"Downtown Battle Mountain II","artist_name":"Dance Gavin Dance",
             "mbid":A,"in_library":False}
        recent={"name":"Actual new release","artist_name":"New Artist",
                "mbid":B,"in_library":False}
        sections={"missing_essentials":{
                     "title":"Missing Essentials","type":"albums","items":[old]},
                  "fresh_releases":{
                     "title":"Fresh Releases For You","type":"albums","items":[recent]}}
        parsed=decode(rest._discover_rows(sections))
        ids={row[1]:row[2] for row in parsed if row[0]=="catalog_album"}
        self.assertEqual(ids[A],"Downtown Battle Mountain II")
        self.assertEqual(ids[B],"Actual new release")
        c=(ROOT/"src/ui_music.c").read_text(encoding="utf-8")
        start=c.index("static int music_discover_group_for(")
        end=c.index("static const char *music_discover_title(",start)
        routing=c[start:end]
        self.assertIn('if(!g_strcmp0(key,"fresh_releases"))return DISC_FRESH;',routing)
        self.assertIn('if(!g_strcmp0(key,"missing_essentials"))return DISC_FOR_YOU;',routing)
        self.assertIn('if(!g_strcmp0(key,"anniversaries"))return DISC_EXPLORE;',routing)
        self.assertEqual(routing.count("return DISC_FRESH;"),1)

    def test_empty_mix_is_not_populated_with_fake_content(self):
        data={"daily_mixes":[{"title":"Hip-Hop Mix","type":"albums","items":[]}]}
        self.assertEqual(rest._discover_rows(data),"")
    
    def test_external_catalog_rows_have_scoped_image_identifiers(self):
        raw={"albums":[{"title":"Outside album","musicbrainz_id":A,
                         "artist":"Outside artist","in_library":False},
                        {"title":"Already own","musicbrainz_id":B,
                         "artist":"Owned","in_library":True}],
             "artists":[{"title":"Outside artist","musicbrainz_id":C,
                          "in_library":False}]}
        rows=decode(rest._rows(raw))
        self.assertEqual([x[0] for x in rows],["catalog_artist","catalog_album"])
        self.assertEqual([x[4] for x in rows],["dn-artist:"+C,"dn-album:"+A])
        from_subsonic=decode(sub._rows("catalog",{"catalog":raw}))
        self.assertEqual([x[4] for x in from_subsonic],
                         ["dn-artist:"+C,"dn-album:"+A])
        self.assertNotIn(B,[x[1] for x in rows])

    def test_catalog_cover_never_accepts_arbitrary_url_or_uuid(self):
        for bad in ("http://evil.test", "album:not-an-mbid",
                    "track:"+A, "artist:"+A+"?token=no",None):
            with self.subTest(bad=bad),self.assertRaises(rest.MusicRESTError):
                rest.cover_bytes(BASE,bad,token=TOKEN)

    def test_catalog_cover_uses_authenticated_fixed_source_and_bounds(self):
        class Response:
            status=200
            headers={"Content-Type":"image/png","Content-Length":"4"}
            def __enter__(self): return self
            def __exit__(self,*args):pass
            def read(self,n): return b"PNG!"
        class Opener:
            url=None
            bearer=None
            def open(self,req,timeout):
                self.url=req.full_url
                self.bearer=req.headers.get("Authorization")
                return Response()
        opener=Opener()
        with patch.object(rest,"build_opener",return_value=opener):
            data=rest.cover_bytes(BASE,"album:"+A,token=TOKEN)
        self.assertEqual(data,b"PNG!")
        self.assertEqual(opener.url,
            BASE+"/api/v1/covers/release-group/"+A+"?size=250")
        self.assertEqual(opener.bearer,"Bearer "+TOKEN)
        self.assertNotIn(TOKEN,opener.url)

    def test_svg_placeholder_is_not_a_real_cover(self):
        class Response:
            status=200
            headers={"Content-Type":"image/svg+xml"}
            def __enter__(self): return self
            def __exit__(self,*args):pass
        class Opener:
            def open(self,req,timeout):return Response()
        with patch.object(rest,"build_opener",return_value=Opener()):
            with self.assertRaises(rest.MusicRESTError):
                rest.cover_bytes(BASE,"album:"+A,token=TOKEN)

    def test_gtk_has_clickable_personal_tiles_and_back(self):
        ui=(ROOT/"src/ui_music.c").read_text(encoding="utf-8")
        for text in ('"Because You Listen to "','"because_you_listen_"',
                     '"daily_mixes_"','"music-discover-tile"',
                     'G_CALLBACK(music_discover_tile_clicked)',
                     'G_CALLBACK(music_discover_back_clicked)',
                     'music_discover_show_category(view,group)',
                     'music_discover_show_landing(view)',
                     '"music-discover-add"',
                     '"music-discover-explore"'):
            with self.subTest(text=text):
                self.assertIn(text,ui if text!='"Because You Listen to "' else
                              (ROOT/"src/music_rest.py").read_text())
        self.assertIn('view->discover_shelves->len<DISC_MAX_DYNAMIC',ui)
        self.assertIn('!count)continue;',ui)
        self.assertIn('"cover",cover_arg,NULL',ui)
        self.assertIn('g_strdup("")',ui)

if __name__=="__main__":
    unittest.main()
