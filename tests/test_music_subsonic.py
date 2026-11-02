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
        self.auth = {"apiKey": "secret-should-never-be-in-url", "u": "listener"}

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

    def test_app_password_only_arrives_via_stdin(self):
        class Stdin:
            buffer = io.BytesIO(b'{"api_key":"app-test-key","username":"listener"}')
        original = music.sys.stdin
        try:
            music.sys.stdin = Stdin()
            result = music._auth_from_stdin()
        finally:
            music.sys.stdin = original
        self.assertEqual(result, {"apiKey": "app-test-key", "u": "listener"})


if __name__ == "__main__":
    unittest.main()
