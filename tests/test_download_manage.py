"""No-network exact-torrent tests. Deleting downloaded files is forbidden."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"server"))
import download_manage as mod
from download_inventory import InventoryError

HASH="a"*40
GATEWAY="b"*64

class ManageTests(unittest.TestCase):
    def test_only_exact_hash_and_never_delete_files(self):
        for action,api in mod.OPERATIONS.items():
            with self.subTest(action=action):
                calls=[]
                def runner(argv,**kw):
                    calls.append(argv)
                    if "torrents/info?" in argv[-1]:
                        return subprocess.CompletedProcess(
                            argv,0,('['+'{"hash":"'+HASH+'"}'+']').encode(),b"")
                    self.assertEqual(argv[-1],
                        f"http://127.0.0.1:8085/api/v2/torrents/{api}")
                    payload=next(part for part in argv if part.startswith("--post-data="))
                    self.assertIn("hashes="+HASH,payload)
                    if action=="remove":
                        self.assertIn("deleteFiles=false",payload)
                    else:
                        self.assertNotIn("deleteFiles",payload)
                    self.assertIn("Referer: http://127.0.0.1:8085/",argv)
                    return subprocess.CompletedProcess(argv,0,b"",b"")
                with patch.object(mod,"locate_verified_downloader",
                                  return_value=(GATEWAY,8085)):
                    self.assertEqual(mod.manage_torrent(action,HASH,runner=runner),
                                     {"status":"submitted","operation":action})
                self.assertEqual(len(calls),2)
    def test_bad_selector_never_reaches_backend(self):
        for value in ("all","",None,"b"*39,"z"*40,"a"*40+";rm -rf /"):
            with self.subTest(value=value),self.assertRaises(InventoryError):
                mod.manage_torrent("remove",value,runner=lambda *a,**kw:
                                   self.fail("No Docker or network"))
        with self.assertRaises(InventoryError):
            mod.manage_torrent("deleteFiles",HASH)
    def test_nonexistent_hash_never_mutates(self):
        commands=[]
        def runner(argv,**kwargs):
            commands.append(argv)
            return subprocess.CompletedProcess(argv,0,b"[]",b"")
        with patch.object(mod,"locate_verified_downloader",
                          return_value=(GATEWAY,8085)):
            with self.assertRaisesRegex(InventoryError,"no longer exists"):
                mod.manage_torrent("remove",HASH,runner=runner)
        self.assertEqual(len(commands),1)
    def test_failed_post_never_claims_success(self):
        def runner(argv,**kwargs):
            if "torrents/info?" in argv[-1]:
                return subprocess.CompletedProcess(argv,0,
                    ('[{"hash":"'+HASH+'"}]').encode(),b"")
            return subprocess.CompletedProcess(argv,8,b"",b"")
        with patch.object(mod,"locate_verified_downloader",
                          return_value=(GATEWAY,8085)):
            with self.assertRaisesRegex(InventoryError,"operation failed"):
                mod.manage_torrent("pause",HASH,runner=runner)

if __name__=="__main__":
    unittest.main()
