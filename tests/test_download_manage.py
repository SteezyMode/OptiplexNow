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
            if action == "remove_delete":
                continue
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
    def test_delete_files_requires_approved_subfolder_and_exact_hash(self):
        """Only an explicitly allowed torrent can send deleteFiles=true."""
        valid={"hash":HASH,"save_path":"/library/bigdisk/Movies/Horror",
               "content_path":"/library/bigdisk/Movies/Horror/Film/file.mkv"}
        def exercise(info, mounts=None):
            urls=[]
            def runner(argv,**kwargs):
                url=argv[-1]
                urls.append(url)
                if "torrents/info?" in url:
                    return subprocess.CompletedProcess(argv,0,
                                     __import__("json").dumps([info]).encode(),b"")
                self.assertEqual(url,
                     "http://127.0.0.1:8085/api/v2/torrents/delete")
                payload=next(part for part in argv if part.startswith("--post-data="))
                self.assertIn("hashes="+HASH,payload)
                self.assertIn("deleteFiles=true",payload)
                return subprocess.CompletedProcess(argv,0,b"",b"")
            with patch.object(mod,"locate_verified_downloader",
                              return_value=(GATEWAY,8085)),patch.object(
                              mod,"_mounts",return_value=("qbit",GATEWAY,8085,
                                  mounts if mounts is not None else
                                  {"bigdisk":{"source":"/media/BigDisk",
                                              "target":"/library/bigdisk"}})):
                result=mod.manage_torrent("remove_delete",HASH,runner=runner)
            return result,urls
        result,urls=exercise(valid)
        self.assertEqual(result,{"status":"submitted",
                                 "operation":"remove_delete"})
        self.assertEqual(len(urls),2)
        unsafe=(
            dict(valid,save_path="/etc",content_path="/etc/passwd"),
            dict(valid,save_path="/library/bigdisk",
                 content_path="/library/bigdisk/Movies/Horror/Film"),
            dict(valid,save_path="/library/bigdisk/Movies/../",
                 content_path="/library/bigdisk/Movies/../secret"),
            dict(valid,save_path="/library/bigdisk/Movies/Horror",
                 content_path="/library/bigdisk/Other/film.mkv"),
            dict(valid,save_path="/library/bigdisk/Movies/Horror",
                 content_path=""),
            dict(valid,save_path="/library/bigdisk/Movies/Horror",
                 content_path=None),
        )
        for info in unsafe:
            with self.subTest(info=info),self.assertRaises(InventoryError):
                exercise(info)

    def test_delete_data_rejects_gateway_binding_change(self):
        with patch.object(mod,"locate_verified_downloader",
                          return_value=(GATEWAY,8085)),patch.object(
                          mod,"_mounts",return_value=("qbit","different",8085,
                                                    {"bigdisk":{}})):
            def runner(argv,**kwargs):
                if "torrents/info?" in argv[-1]:
                    return subprocess.CompletedProcess(argv,0,
                      ('[{"hash":"'+HASH+'","save_path":"/library/bigdisk/Movies",'
                       '"content_path":"/library/bigdisk/Movies/file.mkv"}]').encode(),b"")
                self.fail("Never submit a delete request after host mismatch")
            with self.assertRaises(InventoryError):
                mod.manage_torrent("remove_delete",HASH,runner=runner)

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
    def test_http_success_with_failure_payload_is_not_success(self):
        def runner(argv,**kwargs):
            if "torrents/info?" in argv[-1]:
                return subprocess.CompletedProcess(argv,0,
                    ('[{"hash":"'+HASH+'"}]').encode(),b"")
            return subprocess.CompletedProcess(argv,0,b"Fails.",b"")
        with patch.object(mod,"locate_verified_downloader",
                          return_value=(GATEWAY,8085)):
            with self.assertRaisesRegex(InventoryError,"operation failed"):
                mod.manage_torrent("recheck",HASH,runner=runner)

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
