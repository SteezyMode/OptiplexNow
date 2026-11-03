"""Hermetic tests for the API Bay Nova engine. No DNS/network required."""
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "server" / "search_plugins"
HASH = "f" * 40
# Stable capture sink: imported engine modules bind to prettyPrinter at import
# time; each fixture resets this one list instead of a stale per-test closure.
SHARED_PRINTED = []


class _FixtureModules:
    """Avoid polluting the repository's other unittest imports."""
    def __enter__(self):
        self.pkg = types.ModuleType("engines")
        self.pkg.__path__ = [str(ROOT)]
        self.printer = types.ModuleType("novaprinter")
        self.results = SHARED_PRINTED
        self.results.clear()
        self.printer.prettyPrinter = SHARED_PRINTED.append
        self.patch = patch.dict(sys.modules, {
            "engines": self.pkg,
            "novaprinter": self.printer,
        })
        self.patch.__enter__()
        self.common = importlib.import_module("engines._bruiser_source")
        self.apibay = importlib.import_module("engines.bruiser_apibay")
        return self

    def __exit__(self, *args):
        for key in ("engines._bruiser_source", "engines.bruiser_apibay"):
            sys.modules.pop(key, None)
        self.patch.__exit__(*args)


class Response:
    def __init__(self, address, body):
        self.address = address
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def geturl(self):
        return self.address

    def read(self, length):
        return self.body[:length]


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.fixture = _FixtureModules()
        self.fixture.__enter__()
        self.addCleanup(self.fixture.__exit__, None, None, None)
        self.common = self.fixture.common
        self.apibay = self.fixture.apibay
        self.results = self.fixture.results

    def load(self, engine, query, response):
        calls = []
        def fake_urlopen(request, timeout):
            calls.append((request.full_url, timeout))
            return Response(request.full_url, json.dumps(response).encode())
        with patch.object(self.common, "urlopen", side_effect=fake_urlopen):
            engine.search(query)
        return calls

    def test_apibay_encodes_once_and_emits_magnet_and_date(self):
        row = {
            "name": "South.Park.S29E04.1080p", "info_hash": HASH,
            "size": "444222", "seeders": "7", "leechers": "3",
            "added": "1793232000",
        }
        req = self.load(self.apibay.bruiser_apibay(),
                        "south%20park%20s29e04", [row])
        self.assertEqual(len(req), 1)
        self.assertIn("q=south+park+s29e04", req[0][0])
        self.assertNotIn("%2520", req[0][0])
        self.assertEqual(len(self.results), 1)
        self.assertTrue(self.results[0]["link"].startswith("magnet:?xt=urn:btih:"+HASH))
        self.assertEqual(self.results[0]["size"], "444222 B")
        self.assertEqual(self.results[0]["seeds"], "7")
        self.assertEqual(self.results[0]["pub_date"], 1793232000)
        self.assertLess(len(self.results[0]["link"]), 1024)

    def test_apibay_ignores_bad_hash_and_sentinel(self):
        rows = [{"name": "No results returned", "info_hash": "0"},
                {"name": "Bad", "info_hash": "magnet:?xt=foo"},
                {"name": "Bad\nname", "info_hash": "g" * 40}]
        self.load(self.apibay.bruiser_apibay(), "south park", rows)
        self.assertEqual(self.results, [])

    def test_common_http_bounds_and_redirects(self):
        with patch.object(self.common, "urlopen", return_value=Response(
                "http://apibay.org/q.php", b"{}")):
            self.assertIsNone(self.common.read_json("https://apibay.org/q.php"))
        with patch.object(self.common, "urlopen", return_value=Response(
                "https://unapproved.invalid/", b"{}")):
            self.assertIsNone(self.common.read_json("https://apibay.org/q.php"))
        with patch.object(self.common, "urlopen", return_value=Response(
                "https://apibay.org/q.php", b" " * (self.common.MAX_BODY_BYTES + 1))):
            self.assertIsNone(self.common.read_json("https://apibay.org/q.php"))

    def test_empty_invalid_and_bounded_queries_never_network(self):
        for eng in (self.apibay.bruiser_apibay(),):
            with patch.object(self.common, "urlopen") as network:
                eng.search("a")
                eng.search("test\ncommand")
                eng.search("x" * 97)
                eng.search(None)
                network.assert_not_called()
            self.assertEqual(self.results, [])

    def test_malformed_provider_is_quiet_and_never_calls_network(self):
        # Patch imported module symbol, not its original provider module.
        with patch.object(self.apibay, "read_json", return_value="bad") as lookup:
            self.apibay.bruiser_apibay().search("hello world")
            lookup.assert_called_once()
        self.assertEqual(self.results, [])

    def test_invalid_response_does_not_fabricate_results(self):
        for response in (None, {}, {"torrents": []},
                         [{"name": "Nothing", "info_hash": None}]):
            with self.subTest(response=response):
                self.results.clear()
                with patch.object(self.apibay, "read_json", return_value=response):
                    self.apibay.bruiser_apibay().search("hello world")
                self.assertEqual(self.results, [])


if __name__ == "__main__":
    unittest.main()
