"""Host music provisioning tests: no real Docker, account, or private credential."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"server"))
from owner_access import new_owner, approve_device, grant_music, revoke_device, PolicyError
from music_device_provision import (
    DroppedNeedleAPI, ProvisionError, issue_approved_music_access
)

def wolf_profile():
    return {"success":True,"profiles":[{"id":"user","apps":[{"title":"Steam"}]}]}

def paired():
    return {"success":True,"clients":[
        {"client_id":"1001","app_state_folder":"folder1001"},
        {"client_id":"1002","app_state_folder":"folder1002"}
    ]}

OWNER_PASSWORD="private-owner-password-for-testing"
MASTER="standard-server-session-test-token"
PLAYBACK="per-device-test-app-password"
COMPANION="per-device-test-rest-session"
APP_ID="app1"
SESSION_ID="session1"

class FakeDN(BaseHTTPRequestHandler):
    observed=[]
    records=[]
    def log_message(self,*unused):pass
    def do_POST(self):self.action()
    def do_GET(self):self.action()
    def do_DELETE(self):self.action()
    def action(self):
        path=self.path
        length=int(self.headers.get("Content-Length",0))
        data=self.rfile.read(length) if length else b""
        bearer=self.headers.get("Authorization")
        type(self).observed.append((self.command,path,bearer,data))
        if path=="/api/v1/auth/login":
            ok=self.command=="POST" and json.loads(data)=={
                "username":"music-owner","password":OWNER_PASSWORD}
            result={"token":MASTER,"user":{"id":"owner-of-music"}}
        elif path=="/api/v1/connect-apps/app-passwords":
            ok=self.command=="POST" and bearer=="Bearer "+MASTER
            result={"secret":PLAYBACK,"app_password":{"id":APP_ID}}
        elif path=="/api/v1/auth/device-sessions":
            ok=self.command=="POST" and bearer=="Bearer "+MASTER
            name=json.loads(data).get("device_name","")
            type(self).records=[{"id":SESSION_ID,
                "session_kind":"companion",
                "user_agent":"DroppedNeedle companion · "+name}]
            result={"token":COMPANION,"user":{"id":"owner-of-music"}}
        elif path=="/api/v1/auth/sessions":
            ok=self.command=="GET" and bearer=="Bearer "+MASTER
            result={"sessions":list(self.records)}
        elif path in ("/api/v1/auth/sessions/"+SESSION_ID,
                      "/api/v1/connect-apps/app-passwords/"+APP_ID):
            ok=self.command=="DELETE" and bearer=="Bearer "+MASTER
            result={}
        else:
            ok=False;result={}
        if not ok:
            self.send_response(403);self.end_headers();return
        raw=json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class ProvisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),FakeDN)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base="http://127.0.0.1:%d"%cls.server.server_port
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
    def setUp(self):
        FakeDN.observed.clear()
        FakeDN.records.clear()
        self.policy=new_owner("user",wolf_profile())
        self.host_account={
            "base_url":self.base,
            "owner_principal_id":self.policy["principals"][0]["id"],
            "username":"music-owner","password":OWNER_PASSWORD
        }
        self.recorded=[]

    def provision(self):
        return issue_approved_music_access(
            self.policy,"1001",paired(),host_account=self.host_account,
            record_grants=self.recorded.append)

    def test_refuses_pairing_and_games_only_without_music_consent(self):
        for phase in (0,1,2):
            with self.subTest(phase=phase),self.assertRaises(PolicyError):
                self.provision()
            if phase==0:
                approve_device(self.policy,"1001",paired())
            if phase==1:
                # Rejected: a Games grant is not an implicit Music grant.
                pass
            if phase==2:
                pass
        self.assertEqual(FakeDN.observed,[])

    def test_issue_returns_only_per_device_keys_and_persists_revoke_ids(self):
        approve_device(self.policy,"1001",paired())
        grant_music(self.policy,"1001",paired(),owner_confirmed=True)
        reply=self.provision()
        self.assertEqual(reply,{"app_password":PLAYBACK,
                               "rest_token":COMPANION})
        self.assertEqual(len(self.recorded),1)
        self.assertEqual(self.recorded[0]["app_password_id"],APP_ID)
        self.assertEqual(self.recorded[0]["companion_session_id"],SESSION_ID)
        self.assertEqual(self.recorded[0]["client_id"],"1001")
        self.assertNotIn(OWNER_PASSWORD,str((reply,self.recorded)))
        self.assertNotIn(MASTER,str((reply,self.recorded)))
        paths=[r[1] for r in FakeDN.observed]
        self.assertEqual(paths,[
            "/api/v1/auth/login",
            "/api/v1/connect-apps/app-passwords",
            "/api/v1/auth/device-sessions",
            "/api/v1/auth/sessions"
        ])
        self.assertEqual(FakeDN.observed[1][2],"Bearer "+MASTER)
        self.assertNotIn(OWNER_PASSWORD," ".join(paths))

    def test_revoked_or_wrong_owner_never_calls_music_account(self):
        approve_device(self.policy,"1001",paired())
        grant_music(self.policy,"1001",paired(),owner_confirmed=True)
        revoke_device(self.policy,"1001")
        with self.assertRaises(PolicyError):self.provision()
        self.assertFalse(FakeDN.observed)
        approve_device(self.policy,"1001",paired())
        grant_music(self.policy,"1001",paired(),owner_confirmed=True)
        self.host_account["owner_principal_id"]="wrong-owner"
        with self.assertRaisesRegex(ProvisionError,"Host owner"):
            self.provision()
        self.assertFalse(FakeDN.observed)

    def test_ledger_failure_revokes_both_newly_created_grants(self):
        approve_device(self.policy,"1001",paired())
        grant_music(self.policy,"1001",paired(),owner_confirmed=True)
        def fail_write(_):
            raise OSError("simulated full disk")
        with self.assertRaises(OSError):
            issue_approved_music_access(
                self.policy,"1001",paired(),host_account=self.host_account,
                record_grants=fail_write)
        paths=[r[1] for r in FakeDN.observed]
        self.assertIn("/api/v1/auth/sessions/"+SESSION_ID,paths)
        self.assertIn("/api/v1/connect-apps/app-passwords/"+APP_ID,paths)
        self.assertEqual(self.recorded,[])

    def test_only_configured_private_host_and_fixed_api_routes_allowed(self):
        for invalid in ("http://8.8.8.8","http://public.example.test",
                        "http://user:pass@127.0.0.1",
                        "https://example.com/?session=bad"):
            with self.subTest(url=invalid),self.assertRaises(ProvisionError):
                DroppedNeedleAPI(invalid)
        client=DroppedNeedleAPI(self.base)
        with self.assertRaises(ProvisionError):
            client.call("POST","/other/service",data={})
        with self.assertRaises(ProvisionError):
            client.call("GET","/auth/sessions/../../owner")
        with self.assertRaises(ProvisionError):
            client.call("POST","/auth/login",data={"extra":"x"*5000})
        self.assertFalse(FakeDN.observed)


if __name__=="__main__":
    unittest.main()
