"""Temp-filesystem, no-Docker tests for owner-selected real media destinations."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import parse_qs

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"server"))
from download_destinations import DestinationError, roots, browse, add_magnet
from download_inventory import InventoryError

VPN="a"*64
QBIT="b"*64
MAGNET="magnet:?xt=urn:btih:"+"f"*40

class FakeDocker:
    def __init__(self,media,*,writable=True,healthy=True):
        self.commands=[]
        self.media=media
        self.can_write=writable
        self.records=[
          {"Id":VPN,"Name":"/music-vpn",
           "Config":{"Image":"qmcgaw/gluetun:v3.41","Env":[]},
           "HostConfig":{"NetworkMode":"bridge"},
           "State":{"Health":{"Status":"healthy" if healthy else "unhealthy"}}},
          {"Id":QBIT,"Name":"/qbittorrent-vpn",
           "Config":{"Image":"lscr.io/linuxserver/qbittorrent:5.1.4",
                     "Env":["WEBUI_PORT=8085"]},
           "HostConfig":{"NetworkMode":"container:"+VPN},
           "Mounts":[
             {"Source":str(media),"Destination":"/library/bigdisk",
              "Type":"bind","RW":True},
             {"Source":str(media),"Destination":"/config",
              "Type":"bind","RW":True},
             {"Source":"/etc","Destination":"/library/system",
              "Type":"bind","RW":True},
             {"Source":str(media),"Destination":"/library/readonly",
              "Type":"bind","RW":False},
           ],"State":{}},
        ]
    def __call__(self,cmd,**kwargs):
        self.commands.append(cmd)
        if cmd[:2]==["docker","ps"]:
            return subprocess.CompletedProcess(cmd,0,
                    "\n".join(item["Id"] for item in self.records),"")
        if cmd[:2]==["docker","inspect"]:
            import json
            return subprocess.CompletedProcess(cmd,0,
                                               json.dumps(self.records),"")
        if cmd[:4]==["docker","exec","-u","abc"]:
            self_check=cmd[-1]
            self_result=0 if self.can_write else 1
            assert cmd[4]==QBIT and cmd[5:8]==["sh","-c",'test -w "$1"']
            assert cmd[-2].startswith("now")
            assert self_check.startswith("/library/bigdisk")
            return subprocess.CompletedProcess(cmd,self_result,b"",b"")
        assert cmd[:3]==["docker","exec",VPN]
        assert cmd[-1]=="http://127.0.0.1:8085/api/v2/torrents/add"
        data=[part for part in cmd if part.startswith("--post-data=")]
        assert len(data)==1
        fields=parse_qs(data[0].partition("=")[2])
        assert fields["autoTMM"]==["false"]
        assert fields["savepath"]==["/library/bigdisk/Movies/Horror"]
        assert fields["urls"]==[MAGNET]
        return subprocess.CompletedProcess(cmd,0,b"Ok.",b"")

class DestinationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media=Path(self.temp.name)/"Video"
        (self.media/"Movies"/"Horror").mkdir(parents=True)
        (self.media/"Movies"/"Action ").mkdir()
        (self.media/"Television").mkdir()
        (self.media/"Movies"/"outside-link").symlink_to(self.media/"Television",
                                                        target_is_directory=True)
        self.fake=FakeDocker(self.media)

    def test_roots_only_approved_media_bind_not_config_system_or_readonly(self):
        self.assertEqual(roots(runner=self.fake),{
            "roots":[{"id":"bigdisk","label":"Bigdisk"}]})

    def test_browse_preserves_trailing_space_genre_and_ignores_symlinks(self):
        result=browse("bigdisk","Movies",runner=self.fake)
        self.assertEqual(result["folders"],["Action ","Horror"])
        self.assertEqual(result["relative"],"Movies")

    def test_add_magnet_explicit_target_and_not_default_downloads(self):
        result=add_magnet("bigdisk","Movies/Horror",MAGNET,runner=self.fake)
        self.assertEqual(result,{"status":"submitted"})
        self.assertEqual(self.fake.commands[-2][:4],
                         ["docker","exec","-u","abc"])
        self.assertTrue(self.fake.commands[-1][-1].endswith("/torrents/add"))
        self.assertFalse(any("torrent_files" in str(c) for c in self.fake.commands))
        self.assertFalse(any("rm -rf" in str(c) for c in self.fake.commands))

    def test_bad_input_no_add(self):
        for root,path,magnet in [
            ("unknown","Movies/Horror",MAGNET),
            ("bigdisk","../Horror",MAGNET),
            ("bigdisk","Movies//Horror",MAGNET),
            ("bigdisk","/Movies/Horror",MAGNET),
            ("bigdisk","Movies/Horror","https://example.org"),
            ("bigdisk","Movies/outside-link",MAGNET),
            ("bigdisk","Movies/Missing",MAGNET),
        ]:
            self.fake.commands.clear()
            with self.subTest(root=root,path=path),self.assertRaises(DestinationError):
                add_magnet(root,path,magnet,runner=self.fake)
            self.assertFalse(any(c[-1].endswith("/torrents/add")
                                 for c in self.fake.commands))

    def test_no_write_denies_add(self):
        self.fake.can_write=False
        with self.assertRaisesRegex(DestinationError,"cannot write"):
            add_magnet("bigdisk","Movies/Horror",MAGNET,runner=self.fake)
        self.assertFalse(any(c[-1].endswith("/torrents/add")
                             for c in self.fake.commands))

    def test_unsafe_topology_denies_all(self):
        self.fake.records[0]["State"]["Health"]["Status"]="unhealthy"
        with self.assertRaises(InventoryError):
            roots(runner=self.fake)
        with self.assertRaises(InventoryError):
            add_magnet("bigdisk","Movies/Horror",MAGNET,runner=self.fake)

if __name__=="__main__":
    unittest.main()
