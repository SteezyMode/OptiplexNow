"""Approved NOW Music client provision tests: no live host, music or accounts."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import music_device_client as client

APP="private-app-password-not-real"
REST="private-rest-session-not-real"


class MusicDeviceClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.key_dir=root/"games-client"
        self.key_dir.mkdir(mode=0o700)
        self.key=self.key_dir/"id_ed25519"
        self.key.write_text("fixture-private-key")
        self.key.chmod(0o600)

    def test_reuses_exact_enrolled_ssh_key_and_no_admin_account(self):
        calls=[]
        def runner(argv,**kw):
            calls.append((argv,kw))
            result={"success":True,"service":"music",
                    "credentials":{"app_password":APP,"rest_token":REST}}
            return subprocess.CompletedProcess(argv,0,
                                               stdout=json.dumps(result).encode())
        result=client.request("100.121.156.34","optiplex",
                              key_dir=self.key_dir,runner=runner)
        self.assertEqual(result,{"app_password":APP,"rest_token":REST})
        argv,kw=calls[0]
        self.assertIn(str(self.key),argv)
        self.assertIn("StrictHostKeyChecking=yes",argv)
        self.assertIn("BatchMode=yes",argv)
        self.assertIn("ClearAllForwardings=yes",argv)
        self.assertEqual(kw["input"],b'{"version":1,"action":"music_access"}\n')
        self.assertNotIn(APP," ".join(argv))
        self.assertNotIn(REST," ".join(argv))
        self.assertNotIn("password"," ".join(argv))

    def test_requires_prior_owner_enrollment_and_private_ssh_key(self):
        with self.assertRaises(client.EnrollmentError):
            client.request("127.0.0.1","owner",
                           key_dir=Path(self.tmp.name)/"absent")
        self.key.chmod(0o644)
        with self.assertRaisesRegex(client.EnrollmentError,"not private"):
            client.request("127.0.0.1","owner",key_dir=self.key_dir)
        self.key.unlink()
        self.key.symlink_to(Path(self.tmp.name)/"other")
        with self.assertRaises(client.EnrollmentError):
            client.request("127.0.0.1","owner",key_dir=self.key_dir)

    def test_rejects_injected_reply_and_no_credential_disclosure(self):
        for response in (
            {},
            {"success":True,"service":"music","credentials":{}},
            {"success":True,"service":"music","credentials":{
                "app_password":APP,"rest_token":REST,"master":"bad"}},
            {"success":True,"service":"music","credentials":{
                "app_password":"short","rest_token":REST}},
            {"success":True,"service":"games","credentials":{
                "app_password":APP,"rest_token":REST}},
        ):
            with self.subTest(reply=response):
                def runner(argv,**kw):
                    return subprocess.CompletedProcess(
                        argv,0,stdout=json.dumps(response).encode())
                with self.assertRaises(client.EnrollmentError):
                    client.request("127.0.0.1","owner",
                                   key_dir=self.key_dir,runner=runner)

    def test_successful_enrollment_verifies_then_keyrings(self):
        events=[]
        def acquire(host,user):
            events.append("acquire")
            return {"app_password":APP,"rest_token":REST}
        def save_rest(url,token):
            events.append(("rest",token))
        def save_app(action,url,form):
            events.append(("app",action,form))
        with patch.object(client,"playback_secret_api",side_effect=lambda:events.append("vault1")), \
             patch.object(client,"rest_secret_api",side_effect=lambda:events.append("vault2")), \
             patch.object(client,"query",side_effect=lambda *a,**k:events.append(("verify",a[1]))):
            self.assertEqual(client.enroll("127.0.0.1","owner",
               "http://127.0.0.1:8688",acquire=acquire,
               playback_store=save_app,rest_store=save_rest),"connected")
        self.assertEqual(events[:4],["vault1","vault2","acquire",("verify","ping")])
        self.assertEqual(events[4],("rest",REST))
        self.assertEqual(events[5][1],"store")
        self.assertIn("api_key=",events[5][2])
        self.assertNotIn(REST,events[5][2])

    def test_keyring_absence_aborts_before_minting_any_new_credentials(self):
        acquire=Mock()
        with patch.object(client,"playback_secret_api",side_effect=ValueError("locked")):
            with self.assertRaises(ValueError):
                client.enroll("127.0.0.1","owner",
                    "http://127.0.0.1:8688",acquire=acquire)
        acquire.assert_not_called()


if __name__=="__main__":
    unittest.main()
