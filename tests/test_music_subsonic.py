"""Real localhost HTTP contract tests for the optional OpenSubsonic transport.

A fake server verifies credentials travel only in POST bodies, not URLs,
and that response failures/redirects do not leak app passwords.
No running music host or browser is required.
"""
import contextlib
import importlib.util
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

PATH = Path(__file__).resolve().parents[1] / "src" / "music_subsonic.py"
spec = importlib.util.spec_from_file_location("music_subsonic", PATH)
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)


class MockHandler(BaseHTTPRequestHandler):
    requests = []
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"))
        self.server.requests.append((self.path, fields))
        if self.path.endswith("/redirect"):
            self.send_response(307)
            self.send_header("Location", "http://127.0.0.1:9/subsonic/rest/ping")
            self.end_headers()
            return
        if self.path.endswith("/stream"):
            payload = b"ID3" + b"music-fixture-" * 3
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
        elif self.path.endswith("/getCoverArt"):
            payload = b"\x89PNG\r\n\x1a\n" + b"fixture"
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
        elif self.path.endswith("/stream_error"):
            payload = b'{"subsonic-response":{"status":"failed","error":{"code":40}}}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            method = self.path.rsplit("/", 1)[-1]
            if method == "getAlbumList2":
                item = {"albumList2": {"album": [{"id": "a1", "name": "Album 1"}]}}
            elif method == "getAlbum":
                item = {"album": {"id": "a1", "song": [{"id": "t1"}]}}
            elif method == "getPlaylists":
                item = {"playlists": {"playlist": [{"id": "p1"}]}}
            elif method == "getStarred2":
                item = {"starred2": {"album": [{"id": "a2", "name": "Liked Album"}],
                                      "song": [{"id": "t9", "title": "Liked Song"}]}}
            else:
                item = {}
            payload = json.dumps({"subsonic-response": {"status": "ok", "version": "1.16.1", **item}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class MusicSubsonicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
        cls.server.requests = []
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.server.requests.clear()
        self.auth = {"apiKey": "secret-should-never-be-in-url"}

    def test_private_http_and_https_require_clean_origin(self):
        self.assertEqual(music.endpoint_for("http://100.121.156.34:8688", "ping"),
                         "http://100.121.156.34:8688/subsonic/rest/ping")
        self.assertEqual(music.endpoint_for("https://music.example.test/base", "ping"),
                         "https://music.example.test/base/subsonic/rest/ping")
        for base in ("http://8.8.8.8", "http://music.example.test", "ftp://127.0.0.1",
                     "http://user:password@127.0.0.1:8688", 
                     "https://example.test/?apiKey=secret",
                     "https://example.test/#fragment",
                     "https://example.test/../escape"):
            with self.subTest(base=base), self.assertRaises(music.MusicTransportError):
                music.endpoint_for(base, "ping")
        with self.assertRaises(music.MusicTransportError):
            music.endpoint_for("https://example.test", "ping/danger")

    def test_auth_is_post_only_and_not_in_url(self):
        albums = music.query(self.base, "getAlbumList2", self.auth,
                             {"type": "alphabeticalByName", "size": "100"})
        self.assertEqual(albums["albumList2"]["album"][0]["name"], "Album 1")
        path, fields = self.server.requests[-1]
        self.assertEqual(path, "/subsonic/rest/getAlbumList2")
        self.assertEqual(fields["apiKey"], ["secret-should-never-be-in-url"])
        self.assertNotIn("u", fields, "Upstream forbids username plus apiKey")
        self.assertEqual(fields["c"], [music.CLIENT])
        self.assertEqual(fields["f"], ["json"])
        self.assertNotIn("secret", path)

    def test_playlist_and_album_method_contract(self):
        album = music.query(self.base, "getAlbum", self.auth, {"id": "a1"})
        self.assertEqual(album["album"]["song"][0]["id"], "t1")
        playlists = music.query(self.base, "getPlaylists", self.auth)
        self.assertEqual(playlists["playlists"]["playlist"][0]["id"], "p1")
        self.assertEqual(self.server.requests[-1][0], "/subsonic/rest/getPlaylists")

    def test_redirect_never_forwards_auth(self):
        with self.assertRaises(music.MusicTransportError) as caught:
            music.query(self.base, "redirect", self.auth)
        self.assertIn("redirect", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))
        self.assertEqual(len(self.server.requests), 1)

    def test_bad_subsonic_result_is_not_reported_as_success(self):
        class BadResponse:
            def read(self, size):
                return b'{"subsonic-response":{"status":"failed","error":{"code":40,"message":"apiKey=secret"}}}'
            def __enter__(self): return self
            def __exit__(self, *args): pass
        original = music._post
        try:
            music._post = lambda *args, **kwargs: BadResponse()
            with self.assertRaises(music.MusicTransportError) as caught:
                music.query(self.base, "ping", self.auth)
        finally:
            music._post = original
        self.assertIn("authorization", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))

    def test_stream_writes_only_binary_audio(self):
        class Stdout:
            def __init__(self):
                self.buffer = io.BytesIO()
        original = music.sys.stdout
        target = Stdout()
        try:
            music.sys.stdout = target
            music.stream(self.base, self.auth, "t1")
        finally:
            music.sys.stdout = original
        self.assertTrue(target.buffer.getvalue().startswith(b"ID3"))
        self.assertEqual(self.server.requests[-1][1]["id"], ["t1"])

    def test_cover_art_uses_authenticated_post_and_bounded_raster(self):
        class Out:
            def __init__(self):
                self.buffer = io.BytesIO()
        original = music.sys.stdout
        target = Out()
        try:
            music.sys.stdout = target
            music.cover_art(self.base, self.auth, "a1")
        finally:
            music.sys.stdout = original
        self.assertTrue(target.buffer.getvalue().startswith(b"\x89PNG"))
        path, fields = self.server.requests[-1]
        self.assertEqual(path, "/subsonic/rest/getCoverArt")
        self.assertEqual(fields["apiKey"], ["secret-should-never-be-in-url"])
        self.assertEqual(fields["size"], ["220"])
        self.assertEqual(fields["id"], ["a1"])
        self.assertNotIn("secret-should-never-be-in-url", path)

    def test_cover_art_rejects_svg_html_and_oversized_images(self):
        from unittest import mock
        class Response:
            def __init__(self, mime, payload):
                self.headers = {"Content-Type": mime}
                self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *unused): return None
            def read(self, amount): return self.payload[:amount]
        class Output:
            def __init__(self): self.buffer=io.BytesIO()
        for mime, payload in (
            ("image/svg+xml", b"<svg></svg>"),
            ("text/html", b"<h1>private error</h1>"),
            ("image/png", b"A" * (music.MAX_COVER + 1)),
            ("image/jpeg", b""),
        ):
            with self.subTest(mime=mime, length=len(payload)):
                out=Output()
                with mock.patch.object(music, "_post",
                                       return_value=Response(mime, payload)), \
                     mock.patch.object(music.sys, "stdout", out), \
                     self.assertRaises(music.MusicTransportError):
                    music.cover_art(self.base, self.auth, "album1")
                self.assertEqual(out.buffer.getvalue(), b"")

    def test_base64_rows_cannot_inject_newlines_or_tabs(self):
        from base64 import b64decode
        text = music._rows("albums", {"albums": [
            {"id": "a1", "name": "Album\nwith\tcontrols", "artist": "歌手"},
            {"id": "a2", "name": "Another Album", "artist": "Band"},
        ]})
        lines = text.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(b64decode(lines[0].split("\t")[2]).decode(),
                         "Album\nwith\tcontrols")
        self.assertEqual(b64decode(lines[0].split("\t")[3]).decode(), "歌手")
        self.assertEqual(b64decode(lines[1].split("\t")[0]), b"album")
        self.assertEqual(b64decode(lines[0].split("\t")[4]), b"a1")

    def test_album_paging_is_explicit_and_bounded(self):
        from unittest import mock
        calls = []
        def fake_query(base, method, auth, params=None):
            calls.append(dict(params))
            return {"albumList2": {"album": [{"id": "a1", "name": "Album"}]}}
        for argument, expected in ((None, "0"), ("0", "0"), ("200", "200"),
                                    ("400", "400")):
            with self.subTest(offset=argument):
                out = io.StringIO()
                cmd = [self.base, "albums"] + ([argument] if argument else [])
                with mock.patch.object(music, "query", side_effect=fake_query), \
                     mock.patch.object(music, "_auth_from_stdin", return_value=self.auth), \
                     mock.patch.object(music.sys, "stdout", out):
                    self.assertEqual(music.main(cmd), 0)
                self.assertEqual(calls[-1]["offset"], expected)
                self.assertEqual(calls[-1]["size"], "200")
        for bad in ("-200", "1", "201", "1000001", "NaN", "2e2"):
            with self.subTest(invalid=bad):
                with mock.patch.object(music, "_auth_from_stdin", return_value=self.auth), \
                     mock.patch.object(music.sys, "stderr", io.StringIO()):
                    self.assertEqual(music.main([self.base, "albums", bad]), 2)

    def test_home_with_no_history_falls_back_to_real_library_additions(self):
        from unittest import mock
        calls = []
        def fake_query(base, method, auth, params=None):
            self.assertEqual(method, "getAlbumList2")
            calls.append(params["type"])
            if params["type"] == "recent":
                return {"albumList2": {"album": []}}
            return {"albumList2": {"album": [{"id": "a7", "name": "New addition"}]}}
        output = io.StringIO()
        with mock.patch.object(music, "query", side_effect=fake_query), \
             mock.patch.object(music, "_auth_from_stdin", return_value=self.auth), \
             mock.patch.object(music.sys, "stdout", output):
            code = music.main([self.base, "home"])
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["recent", "newest"])
        self.assertEqual(json.loads(output.getvalue())["albums"][0]["id"], "a7")

    def test_real_recent_new_and_liked_endpoint_contracts(self):
        for kind in ("recent", "newest", "alphabeticalByName"):
            with self.subTest(kind=kind):
                music.query(self.base, "getAlbumList2", self.auth,
                            {"type": kind, "size": "100", "offset": "0"})
                path, fields = self.server.requests[-1]
                self.assertEqual(path, "/subsonic/rest/getAlbumList2")
                self.assertEqual(fields["type"], [kind])
        liked = music.query(self.base, "getStarred2", self.auth)
        rows = music._rows("liked", {"starred": liked["starred2"]}).splitlines()
        self.assertEqual(len(rows), 2)
        from base64 import b64decode
        self.assertEqual(b64decode(rows[0].split("\t")[0]), b"album")
        self.assertEqual(b64decode(rows[1].split("\t")[0]), b"song")

    def test_readonly_row_shapes(self):
        cases = {
            "artists": {"indexes": [{"artist": [{"id": "artist1", "name": "Singer"}]}]},
            "playlists": {"playlists": [{"id": "p1", "name": "Favorite"}]},
            "album": {"album": {"song": [{"id": "t1", "title": "Song"}]}},
            "playlist": {"playlist": {"entry": [{"id": "t1", "title": "Song"}]}},
            "artist": {"artist": {"album": [{"id": "a1", "name": "Album"}]}},
            "search": {"results": {"album": [{"id": "a1", "name": "Album"}]}},
        }
        for operation, result in cases.items():
            with self.subTest(operation=operation):
                self.assertEqual(len(music._rows(operation, result).splitlines()), 1)

    def test_all_songs_paging_and_shuffled_collection(self):
        from unittest import mock
        calls = []
        def fake_query(base, method, auth, params=None):
            calls.append((method, params))
            if method == "search3":
                return {"searchResult3": {"song": [
                    {"id": "t01", "title": "Alpha", "artist": "Act",
                     "album": "First", "coverArt": "cover01"}]}}
            if method == "getRandomSongs":
                return {"randomSongs": {"song": [
                    {"id": "t42", "title": "Random"}]}}
            raise AssertionError("unexpected endpoint")
        with mock.patch.object(music, "query", side_effect=fake_query), \
             mock.patch.object(music, "_auth_from_stdin", return_value=self.auth), \
             mock.patch.object(music.sys, "stdout", io.StringIO()):
            self.assertEqual(music.main([self.base, "songs", "200"]), 0)
            self.assertEqual(music.main([self.base, "random_songs"]), 0)
        self.assertEqual(calls[0],("search3",{
            "query": "", "artistCount": "0", "albumCount": "0",
            "songCount": "200", "songOffset": "200"}))
        self.assertEqual(calls[1],("getRandomSongs",{"size":"200"}))
        for bad in ("-1","201","1000001","x"):
            with mock.patch.object(music,"_auth_from_stdin",return_value=self.auth), \
                 mock.patch.object(music.sys,"stderr",io.StringIO()):
                self.assertEqual(music.main([self.base,"songs",bad]),2)

    def test_song_metadata_rows_include_album_and_liked_state(self):
        import base64
        line=music._rows("songs",{"songs":[{
            "id":"track:abc","title":"曲名","artist":"演奏者",
            "album":"First Album","coverArt":"album:xyz","starred":"2026-01-01"}]}).strip()
        parts=[base64.b64decode(p).decode("utf-8") for p in line.split("\t")]
        self.assertEqual(len(parts),7)
        self.assertEqual(parts[5],"First Album")
        self.assertEqual(parts[6],"1")
        self.assertEqual(parts[2],"曲名")

    def test_like_and_playlist_actions_use_authenticated_subsonic(self):
        from unittest import mock
        calls=[]
        def fake_query(base, method, auth, params=None):
            calls.append((method,params))
            if method=="getPlaylists":
                return {"playlists":{"playlist":[{"id":"p1","name":"Roadtrip"}]}}
            return {}
        with mock.patch.object(music,"query",side_effect=fake_query), \
             mock.patch.object(music,"_auth_from_stdin",return_value=self.auth), \
             mock.patch.object(music.sys,"stdout",io.StringIO()):
            self.assertEqual(music.main([self.base,"like","track:123"]),0)
            self.assertEqual(music.main([self.base,"unlike","track:123"]),0)
            self.assertEqual(music.main([self.base,"playlist_options"]),0)
            self.assertEqual(music.main([self.base,"playlist_add","playlist:1|track:123"]),0)
            self.assertEqual(music.main([self.base,"playlist_create","Roadtrip|track:123"]),0)
        self.assertEqual(calls,[
            ("star",{"id":"track:123"}),
            ("unstar",{"id":"track:123"}),
            ("getPlaylists",None),
            ("updatePlaylist",{"playlistId":"playlist:1","songIdToAdd":"track:123"}),
            ("createPlaylist",{"name":"Roadtrip","songId":"track:123"}),
        ])

    def test_form_stdin_is_supported_without_exposing_secrets_in_argv(self):
        class Stdin:
            buffer = io.BytesIO(b"api_key=app%2Bsecret&username=listener")
        original = music.sys.stdin
        try:
            music.sys.stdin = Stdin()
            result = music._auth_from_stdin("form")
        finally:
            music.sys.stdin = original
        self.assertEqual(result, {"apiKey": "app+secret"})

    def test_app_password_only_arrives_via_stdin(self):
        class Stdin:
            buffer = io.BytesIO(b'{"api_key":"app-test-key","username":"listener"}')
        original = music.sys.stdin
        try:
            music.sys.stdin = Stdin()
            result = music._auth_from_stdin()
        finally:
            music.sys.stdin = original
        self.assertEqual(result, {"apiKey": "app-test-key"})


if __name__ == "__main__":
    unittest.main()
