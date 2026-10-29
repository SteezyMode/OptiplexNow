"""Offline bounded queue tests; no Docker or network."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"server"))
from download_queue import inspect_queue
from download_inventory import InventoryError

VPN="a"*64
QBIT="b"*64
def records(mode="container:"+VPN, healthy="healthy"):
    return [
        {"Id":VPN,"Name":"/music-vpn","Config":{"Image":"qmcgaw/gluetun:v3.41","Env":[]},"HostConfig":{"NetworkMode":"bridge"},"State":{"Health":{"Status":healthy}}},
        {"Id":QBIT,"Name":"/qbittorrent-vpn","Config":{"Image":"lscr.io/linuxserver/qbittorrent:5.1.4","Env":["WEBUI_PORT=8085"]},"HostConfig":{"NetworkMode":mode},"State":{}},
    ]

def fake_runner(recs, payload=b"[]", code=0):
    def run(cmd, **kwargs):
        if cmd[:2]==["docker","ps"]:
            return subprocess.CompletedProcess(cmd,0,"\n".join(x["Id"] for x in recs),"")
        if cmd[:2]==["docker","inspect"]:
            return subprocess.CompletedProcess(cmd,0,json.dumps(recs),"")
        assert cmd[:3]==["docker","exec",VPN]
        assert cmd[-1]=="http://127.0.0.1:8085/api/v2/torrents/info"
        return subprocess.CompletedProcess(cmd,code,payload,b"")
    return run

class QueueTests(unittest.TestCase):
    def test_sanitized_queue(self):
        data=[{"name":"Example title","state":"downloading","progress":0.25,
               "save_path":"/private/path","hash":"a"*40,"dlspeed":150,
               "eta":180,"num_seeds":7}]
        self.assertEqual(inspect_queue(runner=fake_runner(records(),json.dumps(data).encode())),{
            "service":"qbittorrent","queue":[{"name":"Example title","state":"downloading",
                                             "progress_percent":25.0,
                                             "torrent_hash":"a"*40,
                                             "download_bps":150,"eta_seconds":180,
                                             "seeders":7}],"truncated":False,"webui_port":8085})
    def test_no_vpn_binding(self):
        with self.assertRaises(InventoryError):
            inspect_queue(runner=fake_runner(records("bridge")))
    def test_unhealthy_gateway(self):
        with self.assertRaises(InventoryError):
            inspect_queue(runner=fake_runner(records(healthy="unhealthy")))
    def test_bounded_and_malformed(self):
        for payload in (b"x"*65537,b"not-json",b"{}",json.dumps([{}]).encode()):
            with self.subTest(payload=payload[:20]),self.assertRaises(InventoryError):
                inspect_queue(runner=fake_runner(records(),payload))
    def test_error_is_not_queue(self):
        with self.assertRaises(InventoryError):
            inspect_queue(runner=fake_runner(records(),b"Forbidden",1))

if __name__=="__main__":
    unittest.main()
