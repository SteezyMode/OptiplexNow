"""Single-hash owner file inventory: bounded, sanitized, never local filesystem."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"server"))
import download_files as mod
from download_inventory import InventoryError
HASH="a"*40
GATEWAY="b"*64

class DownloadFilesTests(unittest.TestCase):
    def run_files(self, data):
        calls=[]
        def runner(argv,**kwargs):
            calls.append(argv)
            self.assertEqual(argv[:3],["docker","exec",GATEWAY])
            self.assertTrue(argv[-1].endswith("torrents/files?hash="+HASH))
            return subprocess.CompletedProcess(argv,0,json.dumps(data).encode(),b"")
        with patch.object(mod,"locate_verified_downloader",
                          return_value=(GATEWAY,8085)):
            result=mod.inspect_torrent_files(HASH,runner=runner)
        self.assertEqual(len(calls),1)
        return result

    def test_valid_list_and_no_private_paths(self):
        result=self.run_files([{"name":"Movie/Film.mkv","size":1024000,
                                "progress":0.25,"priority":1}])
        self.assertEqual(result,{"service":"qbittorrent","torrent_hash":HASH,
                         "truncated":False,"files":[
                          {"name":"Movie/Film.mkv","size":1024000,
                           "progress_percent":25.0,"priority":1}]})
        self.assertNotIn("save_path",str(result))
        self.assertNotIn("/media",str(result))

    def test_malicious_paths_and_metadata_fail_closed(self):
        data={"name":"Movie/Film.mkv","size":1,"progress":0.5,"priority":1}
        for update in ({"name":"../../etc/passwd"},{"name":"/etc/passwd"},
                       {"name":"Movie//Film"},{"name":"Movie\\evil"},
                       {"name":"Movie\tFilm"},{"size":-1},
                       {"progress":1.5},{"progress":float("nan")},
                       {"priority":8}):
            with self.subTest(update=update),self.assertRaises(InventoryError):
                self.run_files([{**data,**update}])

    def test_truncation_is_explicit(self):
        items=[{"name":f"Film/{i}.mkv","size":i,"progress":1.0,
                "priority":1} for i in range(123)]
        result=self.run_files(items)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["files"]),mod.MAX_FILES)

    def test_untrusted_hash_fails_before_any_backend(self):
        with patch.object(mod,"locate_verified_downloader") as backend:
            with self.assertRaises(InventoryError):
                mod.inspect_torrent_files("all")
            backend.assert_not_called()

if __name__=="__main__":
    unittest.main()
