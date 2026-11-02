"""Read-only artwork audit regression tests: no metadata writes or uploads."""
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from music_art_audit import _auth, audit, cover_status, save_report


class CoverAuditTests(unittest.TestCase):
    def test_auth_uses_device_vault(self):
        with patch("music_art_audit.vault",
                   return_value="api_key=secret&username=") as mocked:
            self.assertEqual(_auth("http://100.121.156.34:8688"),
                             {"apiKey": "secret"})
            mocked.assert_called_once_with(
                "lookup", "http://100.121.156.34:8688")

    def test_artwork_statuses_distinguish_real_and_transient(self):
        class Response:
            status = 200
            headers = {"Content-Type": "image/png"}
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self, n): return b"PNG"
        with patch("music_art_audit._post",return_value=Response()):
            self.assertEqual(cover_status("http://host",{}, "abc"),"available")
        self.assertEqual(cover_status("http://host",{}, ""),"missing_cover_id")

    def test_report_is_bounded_and_categorizes_missing_metadata(self):
        calls=[]
        def get_albums(server, method, auth, params):
            calls.append(params)
            if int(params["offset"])>0:
                return {"albumList2":{"album":[]}}
            return {"albumList2":{"album":[
                {"id":"a1","name":"First","artist":"Band","coverArt":"c1"},
                {"id":"a2","name":"Second","artist":""}]}}
        with patch("music_art_audit.query",side_effect=get_albums), \
             patch("music_art_audit.cover_status",
                   side_effect=["available","placeholder"]):
            report=audit("http://host",{},max_albums=10,delay=0)
        self.assertEqual(report["albums_scanned"],2)
        self.assertEqual(report["cover_status"],{"available":1,"placeholder":1})
        self.assertTrue(report["records"][1]["missing_artist"])
        self.assertTrue(report["read_only"])
        self.assertEqual(calls[0]["offset"],"0")

    def test_report_file_stays_private(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"report.json"
            save_report(path,{"albums_scanned":0,"records":[]})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            self.assertIn("albums_scanned",path.read_text())


if __name__ == "__main__":
    unittest.main()
