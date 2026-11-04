"""Favorite-aware discovery never changes DroppedNeedle's request/download state.

All tests run offline. Preferences are per-user OpenSubsonic starred entries;
upstream Discovery remains the sole candidate source.
"""
from __future__ import annotations
import base64
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import music_rest as rest
import music_subsonic as sub

A="11111111-1111-4111-8111-111111111111"
B="22222222-2222-4222-8222-222222222222"
C="33333333-3333-4333-8333-333333333333"
ARTIST="44444444-4444-4444-8444-444444444444"
BASE="http://127.0.0.1:8688"


def rows(data):
    return [[base64.b64decode(col).decode("utf-8") for col in line.split("\t")]
            for line in data.splitlines()]


def discovery():
    return {"fresh_releases":{"title":"New albums","type":"albums","items":[
        {"name":"First","mbid":A,"artist_name":"Different Artist","in_library":False},
        {"name":"Second","mbid":B,"artist_name":" STEREOLAB ","in_library":False},
        {"name":"Third","mbid":C,"artist_name":"Other Band","in_library":False},
    ]}}


class DiscoverFavoritesTests(unittest.TestCase):
    def test_liked_song_artist_reorders_existing_candidates_within_section(self):
        favorites=rest._favorite_artist_signals({"song":[
            {"id":"private-1","artist":"Stereolab","title":"Favorite"}]})
        self.assertIn("stereolab",favorites[0])
        original=rows(rest._discover_rows(discovery()))
        ranked=rows(rest._discover_rows(discovery(),favorite_artists=favorites))
        self.assertEqual([x[1] for x in original[1:]],[A,B,C])
        self.assertEqual([x[1] for x in ranked[1:]],[B,A,C])
        self.assertEqual(ranked[0],original[0])
        self.assertEqual(set(x[1] for x in ranked[1:]),{A,B,C})

    def test_missing_favorites_has_zero_effect(self):
        baseline=rest._discover_rows(discovery())
        self.assertEqual(baseline,rest._discover_rows(discovery(),favorite_artists=(set(),set())))
        self.assertEqual(baseline,rest._discover_rows(discovery(),favorite_artists=None))
        self.assertEqual(rest._favorite_artist_signals([]),(set(),set()))

    def test_exact_name_only_and_generic_names_are_not_personalization(self):
        favorites=rest._favorite_artist_signals({"song":[
            {"artist":"Stereo"},{"artist":"Various Artists"},{"artist":123}]})
        self.assertEqual(rest._discover_rows(discovery(),favorite_artists=favorites),
                         rest._discover_rows(discovery()))
        self.assertNotIn("various artists",favorites[0])

    def test_starred_artist_uses_artist_mbid_but_not_album_id(self):
        favorites=rest._favorite_artist_signals({"artist":[
            {"name":"Some Artist","musicBrainzId":ARTIST}]})
        discover={"artists_you_might_like":{"type":"artists","items":[
            {"name":"New Music","mbid":A},
            {"name":"Some Artist","mbid":ARTIST}]}}
        result=rows(rest._discover_rows(discover,favorite_artists=favorites))
        self.assertEqual([x[1] for x in result[1:]],[ARTIST,A])

    def test_unknown_fields_and_oversized_favorites_are_bounded(self):
        fake=[{"artist":"NOISE"}]*800
        names,mbids=rest._favorite_artist_signals({"song":fake,"artist":"not a list"})
        self.assertEqual(names,{"noise"})
        self.assertEqual(mbids,set())

    def test_discover_cli_reads_only_starred2_and_never_mutates(self):
        dataset=discovery()
        starred={"starred2":{"song":[{"id":"private-1","artist":"Stereolab"}]}}
        captured=io.StringIO()
        with patch.object(sub,"_auth_from_stdin",return_value={"apiKey":"one-user-app-pass"}) as auth, \\
             patch.object(rest,"get_session",return_value="existing-bearer") as get_session, \\
             patch.object(rest,"request",return_value=dataset) as request, \\
             patch.object(sub,"query",return_value=starred) as query, \\
             contextlib.redirect_stdout(captured):
            rc=sub.main([BASE,"discover","--format=rows","--auth-format=form"])
        self.assertEqual(rc,0)
        self.assertEqual([x[1] for x in rows(captured.getvalue())[1:]],[B,A,C])
        auth.assert_called_once_with("form",optional=True)
        query.assert_called_once_with(BASE,"getStarred2",{"apiKey":"one-user-app-pass"})
        get_session.assert_called_once_with(BASE)
        request.assert_called_once_with(BASE,"discover",token="existing-bearer")

    def test_no_app_password_is_normal_unpersonalized_discover(self):
        captured=io.StringIO()
        with patch.object(sub,"_auth_from_stdin",return_value=None), \\
             patch.object(rest,"get_session",return_value="existing-bearer"), \\
             patch.object(rest,"request",return_value=discovery()), \\
             patch.object(sub,"query") as query, \\
             contextlib.redirect_stdout(captured):
            rc=sub.main([BASE,"discover","--format=rows","--auth-format=form"])
        self.assertEqual(rc,0)
        self.assertEqual([x[1] for x in rows(captured.getvalue())[1:]],[A,B,C])
        query.assert_not_called()

    def test_starred_lookups_fail_open_without_leaking_auth(self):
        captured=io.StringIO()
        with patch.object(sub,"_auth_from_stdin",return_value={"apiKey":"secret"}), \\
             patch.object(rest,"get_session",return_value="existing-bearer"), \\
             patch.object(rest,"request",return_value=discovery()), \\
             patch.object(sub,"query",side_effect=sub.MusicTransportError("offline")), \\
             contextlib.redirect_stdout(captured):
            rc=sub.main([BASE,"discover","--format=rows","--auth-format=form"])
        self.assertEqual(rc,0)
        self.assertEqual([x[1] for x in rows(captured.getvalue())[1:]],[A,B,C])
        self.assertNotIn("secret",captured.getvalue())

    def test_catalog_and_discover_are_only_read_operations(self):
        ui=(Path(__file__).resolve().parents[1]/"src"/"ui_music.c").read_text()
        self.assertIn('const gboolean personalized_discover=!g_strcmp0(operation,"discover")',ui)
        self.assertIn('job->input=(catalog && !personalized_discover)?g_strdup("")',ui)
        subsource=(Path(__file__).resolve().parents[1]/"src"/"music_subsonic.py").read_text()
        section=subsource[subsource.index('if args.operation in ("catalog", "discover"):'):
                          subsource.index('auth = _auth_from_stdin(args.auth_format)')]
        self.assertIn('getStarred2',section)
        self.assertNotIn('playlist_add',section)
        self.assertNotIn('"like"',section)
        self.assertNotIn('"request"',section)


if __name__=="__main__":
    unittest.main()
