"""Offline tests of the self-contained, installable API Bay Nova engine."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "server/search_plugins/bruiser_apibay.py"
HASH = "f" * 40


class FakeResponse:
    def __init__(self, data, url="https://apibay.org/q.php"):
        self.body = json.dumps(data).encode("utf-8") if not isinstance(data, bytes) else data
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def geturl(self):
        return self.url

    def read(self, count):
        return self.body[:count]


class ApiBayTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        printer = types.ModuleType("novaprinter")
        printer.prettyPrinter = self.rows.append
        self.modules = patch.dict(sys.modules, {"novaprinter": printer})
        self.modules.__enter__()
        self.addCleanup(self.modules.__exit__, None, None, None)
        spec = importlib.util.spec_from_file_location("bruiser_apibay_test", FILE)
        self.plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.plugin)
        self.engine = self.plugin.bruiser_apibay()

    def run_query(self, query, payload, url="https://apibay.org/q.php", category="all"):
        calls = []
        def fake_open(request, timeout):
            calls.append((request.full_url, timeout))
            return FakeResponse(payload, url)
        with patch.object(self.plugin, "urlopen", side_effect=fake_open):
            self.engine.search(query, category)
        return calls

    def test_query_is_decoded_only_once_and_one_request(self):
        hits = self.run_query("resident%20evil", [{
            "name": "Resident Evil", "info_hash": HASH,
            "size": 1024, "seeders": 12, "leechers": 6, "added": 1793232000,
        }])
        self.assertEqual(len(hits), 1)
        self.assertIn("q=resident+evil", hits[0][0])
        self.assertNotIn("%2520", hits[0][0])
        self.assertEqual(hits[0][1], 4)
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(self.rows[0]["size"], "1024 B")
        self.assertEqual(self.rows[0]["pub_date"], 1793232000)
        self.assertTrue(self.rows[0]["link"].startswith("magnet:?xt=urn:btih:" + HASH))
        self.assertLessEqual(len(self.rows[0]["link"]), 1024)

    def test_category_filters_use_actual_api_bay_metadata(self):
        item=lambda cat: {"name": f"Torrent category {cat}",
                          "info_hash": HASH, "category":str(cat)}
        for category,expected in (("movies",207),("tv",208),
                                  ("games",401),("music",101),
                                  ("software",301)):
            with self.subTest(category=category):
                self.rows.clear()
                self.run_query("resident evil",[item(207),item(208),
                    item(401),item(101),item(301)],category=category)
                self.assertEqual([x["name"] for x in self.rows],
                                 [f"Torrent category {expected}"])

    def test_all_ignores_category_for_video_backward_compatibility(self):
        self.run_query("resident evil",[
            {"name":"Example","info_hash":HASH,"category":"207"}
        ])
        self.assertEqual(len(self.rows),1)

    def test_bad_hash_or_webpage_cannot_be_returned(self):
        self.run_query("resident evil", [
            {"name": "HTML result", "info_hash": "https://example.org/page"},
            {"name": "Bad", "info_hash": "x"*40},
            {"name": "No results returned", "info_hash": "0"},
        ])
        self.assertEqual(self.rows, [])

    def test_invalid_queries_do_not_touch_network(self):
        with patch.object(self.plugin, "urlopen") as network:
            for term in ("a", None, "x"*97, "bad\nquery", "good\rquery"):
                self.engine.search(term)
            network.assert_not_called()

    def test_redirect_and_oversized_payload_fail_closed(self):
        for url in ("http://apibay.org/q.php",
                    "https://something.invalid/q.php"):
            self.run_query("resident evil", [{"name": "ok", "info_hash": HASH}], url=url)
            self.assertEqual(self.rows, [])
        self.run_query("resident evil", b" "*(1_048_577))
        self.assertEqual(self.rows, [])

    def test_bad_json_schema_and_missing_fields(self):
        for payload in (b"{broken", {"results": []}, None,
                        [{"name": "foo", "info_hash": None}],
                        [{"name": 2, "info_hash": HASH}]):
            with self.subTest(payload=str(payload)[:30]):
                self.rows.clear()
                self.run_query("resident evil", payload)
                self.assertEqual(self.rows, [])

    def test_one_hundred_maximum_and_unknown_metadata(self):
        self.run_query("resident evil", [
            {"name": f"Result {i}", "info_hash": HASH, "size": "none",
             "seeders": None, "leechers": None, "added": None}
            for i in range(125)
        ])
        self.assertEqual(len(self.rows), 100)
        self.assertEqual(self.rows[0]["size"], "-1 B")
        self.assertEqual(self.rows[0]["seeds"], "-1")

    def test_magnet_does_not_require_extra_site_lookups(self):
        self.run_query("south%20park%20s29e04", [
            {"name": "South Park S29E04", "info_hash": HASH}
        ])
        self.assertEqual(len(self.rows), 1)
        self.assertIn("urn:btih:", self.rows[0]["link"])
        self.assertEqual(self.rows[0]["engine_url"], "https://apibay.org")


if __name__ == "__main__":
    unittest.main()
