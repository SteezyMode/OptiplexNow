"""No-network tests for safe, games-only Bitsearch Nova integration."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[1]/"server/search_plugins/bruiser_bitsearch.py"
H = "a"*40


class Response:
    def __init__(self, body, url="https://bitsearch.eu/api/v1/search"):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def geturl(self):
        return self.url

    def read(self, n):
        return self.body[:n]


class BitsearchTests(unittest.TestCase):
    def setUp(self):
        self.received=[]
        printer=types.ModuleType("novaprinter")
        printer.prettyPrinter=self.received.append
        p=patch.dict(sys.modules, {"novaprinter":printer})
        p.start()
        self.addCleanup(p.stop)
        spec=importlib.util.spec_from_file_location("bruiser_bitsearch_test",PLUGIN)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module=module
        self.engine=module.bruiser_bitsearch()

    def test_games_only_queries_one_endpoint_and_emits_valid_magnets(self):
        sent=[]
        def opener(request, timeout):
            sent.append((request.full_url, timeout))
            return Response({"success":True,"results":[
                {"title":"Resident Evil Requiem &amp; DLCs","infohash":H,
                 "size":5000,"seeders":2871,"leechers":199,
                 "createdAt":"2026-03-25T12:30:00.000Z"},
                {"title":"duplicate","infohash":H,"seeders":1},
                {"title":"No hash","infohash":None},
                {"title":"Website","infohash":"https://example.org/page"},
                {"title":"Zero hash","infohash":"0"*40},
            ]})
        with patch.object(self.module,"urlopen",side_effect=opener):
            self.engine.search("resident%20evil%20requiem","games")
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0][1],4)
        self.assertIn("category=6",sent[0][0])
        self.assertIn("subCategory=1",sent[0][0])
        self.assertIn("limit=100",sent[0][0])
        self.assertIn("q=resident+evil+requiem",sent[0][0])
        self.assertNotIn("%2520",sent[0][0])
        self.assertEqual(len(self.received),1)
        result=self.received[0]
        self.assertEqual(result["seeds"],"2871")
        self.assertEqual(result["size"],"5000 B")
        self.assertEqual(result["name"],"Resident Evil Requiem & DLCs")
        self.assertTrue(result["link"].startswith("magnet:?xt=urn:btih:"+H))
        self.assertLessEqual(len(result["link"]),1024)
        self.assertGreater(result["pub_date"],0)

    def test_all_and_video_categories_do_no_network(self):
        with patch.object(self.module,"urlopen") as network:
            for category in ("all","movies","tv","music","software",
                             "401",None,"",[]):
                self.engine.search("resident evil",category)
            network.assert_not_called()
        self.assertFalse(self.received)

    def test_invalid_queries_no_network(self):
        with patch.object(self.module,"urlopen") as network:
            for query in (None,"a","x"*97,"bad\nquery","bad\x00query"):
                self.engine.search(query,"games")
            network.assert_not_called()

    def test_redirect_or_oversize_are_rejected(self):
        for final in ("https://other.example/api/v1/search",
                      "http://bitsearch.eu/api/v1/search"):
            with patch.object(self.module,"urlopen",
                              return_value=Response({"success":True,"results":[
                                  {"title":"ok","infohash":H}]},url=final)):
                self.engine.search("resident evil","games")
        with patch.object(self.module,"urlopen",
                          return_value=Response(b" "*(1_048_577))):
            self.engine.search("resident evil","games")
        self.assertEqual(self.received,[])

    def test_wrong_schema_and_bad_dates_are_quiet(self):
        for data in (b"bad json",{"results":[]},{"success":True,"results":{}},
                     {"success":False,"results":[{"title":"foo","infohash":H}]}):
            with self.subTest(data=str(data)[:30]):
                with patch.object(self.module,"urlopen",return_value=Response(data)):
                    self.engine.search("resident evil","games")
                self.assertEqual(self.received,[])
        self.assertEqual(self.module._date("not a date"),-1)
        self.assertEqual(self.module._date("2026-03-25"),-1)
        self.assertEqual(self.module._integer(True),-1)


if __name__ == "__main__":
    unittest.main()
