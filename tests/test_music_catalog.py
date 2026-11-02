"""Bruiser Music native search requires a *separate* DroppedNeedle REST session.

No OpenSubsonic streaming key or slskd key may be forwarded to this route.
"""
from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import music_subsonic as music


class FakeCatalog(BaseHTTPRequestHandler):
    observed = []
    result = {
        "artists": [{"type": "artist", "musicbrainz_id": "artist-id",
                     "title": "Band", "in_library": False, "requested": False}],
        "albums": [{"type": "album", "musicbrainz_id": "album-id",
                    "title": "New Album", "artist": "Band", "in_library": False,
                    "requested": False},
                   {"type": "album", "musicbrainz_id": "owned-id",
                    "title": "Owned Album", "artist": "Band", "in_library": True}],
    }
    def log_message(self, *unused):
        pass
    def do_GET(self):
        parsed = urlsplit(self.path)
        type(self).observed.append((parsed.path,parse_qs(parsed.query),
                                    dict(self.headers.items())))
        if parsed.path != "/api/v1/search":
            self.send_response(404); self.end_headers();return
        if self.headers.get("Authorization") != "Bearer REST-companion-token-12345":
            self.send_response(401); self.end_headers();return
        raw = json.dumps(self.result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class MusicCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv=ThreadingHTTPServer(("127.0.0.1",0),FakeCatalog)
        cls.thread=threading.Thread(target=cls.srv.serve_forever,daemon=True)
        cls.thread.start()
        cls.base="http://127.0.0.1:%s"%cls.srv.server_port
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=2)

    def test_catalog_cli_never_reads_playback_credentials(self):
        import io
        class NoCredentialStdin:
            @property
            def buffer(self):
                raise AssertionError("Catalog search must not read app-password stdin")
        out=io.StringIO()
        with patch.object(music,"catalog_search",return_value=FakeCatalog.result), \
             patch.object(music.sys,"stdin",NoCredentialStdin()), \
             patch.object(music.sys,"stdout",out):
            rc=music.main([self.base,"catalog","dream pop","--format=rows"])
        self.assertEqual(rc,0)
        self.assertGreaterEqual(len(out.getvalue().splitlines()),2)

    def test_search_uses_exact_upstream_route_and_no_secret(self):
        FakeCatalog.observed.clear()
        with patch("music_rest.get_session",return_value="REST-companion-token-12345"):
            found=music.catalog_search(self.base,"new album")
        self.assertEqual(found["albums"][0]["title"],"New Album")
        path,params,headers=FakeCatalog.observed[-1]
        self.assertEqual(path,"/api/v1/search")
        self.assertEqual(params["q"],["new album"])
        self.assertEqual(params["limit_albums"],["25"])
        self.assertEqual(params["limit_artists"],["10"])
        self.assertNotIn("apiKey",str((path,params,headers)))
        self.assertEqual(headers.get("Authorization"),"Bearer REST-companion-token-12345")
        self.assertNotIn("Cookie",headers)

    def test_library_and_missing_catalog_results_have_distinct_types(self):
        rows=music._rows("search",{
            "results":{"song":[{"id":"song1","title":"Playable"}]},
            "catalog":FakeCatalog.result,
        }).splitlines()
        decoded=[[base64.b64decode(field).decode() for field in row.split("\t")]
                 for row in rows]
        self.assertEqual(len(decoded),3)
        self.assertEqual(decoded[0][0],"song")
        self.assertEqual(decoded[1][0],"catalog_artist")
        self.assertEqual(decoded[2][0],"catalog_album")
        self.assertNotIn("Owned Album",str(decoded))
        self.assertIn("Not in library",decoded[2][3])

    def test_discovery_network_failure_never_forwards_app_credentials(self):
        import io
        # Both transport and handler refuse credential-bearing public HTTP
        with self.assertRaises(music.MusicTransportError):
            music.catalog_search("http://example.com","song")
        with self.assertRaises(music.MusicTransportError):
            music.catalog_search(self.base + "/?apiKey=secret","song")
        with self.assertRaises(music.MusicTransportError):
            music.catalog_search(self.base,"x"*201)
        with patch.object(music,"catalog_search",side_effect=music.MusicTransportError("offline")):
            # This is a deliberate contract: the existing library is still
            # available if the external discovery backend is unreachable.
            data={"results":{"album":[{"id":"album1","name":"Saved"}]},
                  "catalog":{}}
            self.assertEqual(len(music._rows("search",data).splitlines()),1)


if __name__ == "__main__":
    unittest.main()
