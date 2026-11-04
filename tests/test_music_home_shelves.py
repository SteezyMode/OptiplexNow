"""Regression tests for Spotify-style Bruiser Home and restart-safe Discover."""
from __future__ import annotations

import base64
import json
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import music_subsonic as sub
import music_rest as rest

A="11111111-1111-4111-8111-111111111111"
B="22222222-2222-4222-8222-222222222222"
C="33333333-3333-4333-8333-333333333333"
D="44444444-4444-4444-8444-444444444444"
E="55555555-5555-4555-8555-555555555555"
BASE="http://127.0.0.1:8688"
TOKEN="approved-device-test-bearer"


def decoded(rows):
    return [[base64.b64decode(field,validate=True).decode()
             for field in line.split("\t")]
            for line in rows.splitlines() if line]


class HomeShelfTests(unittest.TestCase):
    def fixture(self):
        return {
            "recent":[{"id":"mine1","name":"Recent One","artist":"Local A",
                       "coverArt":"local1"},
                      {"id":"mine2","name":"Recent Two","artist":"Local B"}],
            "starred":{"album":[{"id":"mine3","name":"Favorite",
                                 "artist":"Local C"}]},
            "added":[{"id":"mine1","name":"Already on shortcuts"},
                     {"id":"new1","name":"New addition","artist":"Local D"}],
            "playlists":[{"id":"playlist1","name":"My Playlist"}],
            "discover":{
                "top_picks":{"type":"albums","title":"For You","items":[
                    {"album":{"mbid":A,"name":"Unowned A",
                              "artist_name":"Artist A"}}]},
                "fresh_releases":{"type":"albums","items":[
                    {"mbid":B,"name":"Recent Release",
                     "artist_name":"Artist B"}]},
                "artists_you_might_like":{"type":"artists","items":[
                    {"mbid":C,"name":"New Artist"}]},
            },
        }

    def test_home_has_clickable_shortcuts_real_recommendations_and_library_shelves(self):
        rows=decoded(sub._home_rows(self.fixture()))
        titles=[line[2] for line in rows if line[0]=="section"]
        self.assertEqual(titles,["Jump Back In","Made for You","Fresh Releases",
                                 "Artists to Discover","Your Playlists","Recently Added"])
        self.assertEqual([x[1] for x in rows if x[0]=="album"],
                         ["mine1","mine2","mine3","new1"])
        self.assertEqual([x[1] for x in rows if x[0]=="catalog_album"],[A,B])
        self.assertEqual([x[1] for x in rows if x[0]=="catalog_artist"],[C])
        self.assertEqual([x[1] for x in rows if x[0]=="playlist"],["playlist1"])
        self.assertTrue(all(len(row) in (5,7) for row in rows))

    def test_home_omits_empty_shelves_and_never_fabricates_recommendations(self):
        rows=decoded(sub._home_rows({"recent":[{"id":"x","name":"Mine"}]}))
        self.assertEqual([line[2] for line in rows if line[0]=="section"],
                         ["Jump Back In"])
        self.assertFalse(any(line[0].startswith("catalog_") for line in rows))

    def test_home_uses_persisted_approved_device_suggestions(self):
        data=self.fixture()
        historical=rest._discover_rows(data["discover"])
        data["discover"]={}
        data["discover_rows"]=historical
        rows=decoded(sub._home_rows(data))
        self.assertIn(A,[x[1] for x in rows])

    def test_gtk_home_separate_scroll_and_bounded_artwork_loading(self):
        source=(ROOT/"src/ui_music.c").read_text()
        self.assertIn('gtk_widget_set_name(view->home_scroll,"music-home-shelves-scroll")',source)
        self.assertIn("view->home_shelf_cards=lane;",source)
        self.assertIn("GTK_POLICY_AUTOMATIC,GTK_POLICY_NEVER",source)
        self.assertIn("GtkWidget *viewport=view->home_active?view->home_scroll",source)
        self.assertIn('char *heading=view->home_active || partial?',source)
        self.assertIn("view->discover_retry_count<8",source)
        self.assertIn("view->navigation_serial==retry->serial",source)


class DiscoverLastGoodTests(unittest.TestCase):
    def fixture(self):
        return {"top_picks":{"type":"albums","items":[{"album":{
            "name":"Actual Suggestion","artist_name":"Real Artist","mbid":D}}]}}

    def test_cache_retains_real_suggestions_during_authorized_warmup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"discover.json"
            with patch.object(rest,"_discover_cache_path",return_value=path):
                original=rest.retained_discover_rows(BASE,TOKEN,self.fixture())
                self.assertTrue(original.strip())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
                stale=rest.retained_discover_rows(BASE,TOKEN,{"refreshing":True})
                self.assertEqual(stale,original)
                self.assertIn(D,[r[1] for r in decoded(stale)])

    def test_old_negative_or_expired_cache_does_not_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"discover.json"
            with patch.object(rest,"_discover_cache_path",return_value=path):
                rest.retained_discover_rows(BASE,TOKEN,self.fixture())
                content=json.loads(path.read_text())
                content["saved_at"]=time.time()-rest.DISCOVER_CACHE_TTL-1
                path.write_text(json.dumps(content))
                self.assertEqual(rest._last_discover_rows(BASE,TOKEN),"")
                path.unlink()
                self.assertEqual(rest.retained_discover_rows(BASE,TOKEN,
                                                             {"refreshing":True}),"")

    def test_different_host_and_bearer_get_distinct_cache_paths(self):
        self.assertNotEqual(rest._discover_cache_path(BASE,TOKEN),
                            rest._discover_cache_path(BASE,TOKEN+"else"))
        self.assertNotEqual(rest._discover_cache_path(BASE,TOKEN),
                            rest._discover_cache_path("http://127.0.0.1:9000",TOKEN))

    def test_missing_discover_refresh_is_authorized_and_throttled(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as root:
            marker=Path(root)/"discover.json"
            sent=Mock(return_value={"status":"ok"})
            with patch.object(rest,"_discover_cache_path",return_value=marker), \
                 patch.object(rest,"request",sent):
                self.assertTrue(rest.trigger_empty_discover_refresh(
                    BASE,TOKEN,{"refreshing":False}))
                self.assertFalse(rest.trigger_empty_discover_refresh(
                    BASE,TOKEN,{"refreshing":False}))
                sent.assert_called_once_with(BASE,"discover_refresh",
                                             token=TOKEN,timeout_seconds=8)
                self.assertEqual(marker.with_suffix(".refresh").stat().st_mode & 0o777,0o600)

    def test_nonempty_and_in_progress_discover_never_trigger_refresh(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as root:
            sent=Mock(return_value={"status":"ok"})
            with patch.object(rest,"_discover_cache_path",return_value=Path(root)/"discover.json"), \
                 patch.object(rest,"request",sent):
                self.assertFalse(rest.trigger_empty_discover_refresh(
                    BASE,TOKEN,{"refreshing":True}))
                self.assertFalse(rest.trigger_empty_discover_refresh(
                    BASE,TOKEN,{"top_picks":{"type":"albums","items":[
                        {"album":{"mbid":A,"name":"Album","artist_name":"Artist"}}
                    ]}}))
                sent.assert_not_called()

    def test_client_discover_cache_is_suggestions_only(self):
        source=(ROOT/"src/music_subsonic.py").read_text()
        self.assertIn("retained_discover_rows",source)
        self.assertIn('"__refreshing"',source)
        self.assertIn('"discover_rows"',source)


if __name__=="__main__":
    unittest.main()
