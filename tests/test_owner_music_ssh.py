"""Restricted owner Music SSH handling, host-local revoke, no live account."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"server")]
from owner_access import OwnerStore, PolicyError, new_owner, approve_device, grant_music
from owner_music_ssh import (
    read_owner_music_account, issue_ssh_music_access, revoke_owner_music_device,
)
from music_device_ledger import record_issued_locked, get_device_locked
from music_device_provision import ProvisionError

HOST_ID=None
CLIENT="1001"

def profiles():
    return {"success":True,"profiles":[{"id":"user","apps":[{"title":"Steam"}]}]}

def pairs():
    return {"success":True,"clients":[
        {"client_id":CLIENT,"app_state_folder":"owner-folder"}]}


class StubAPI:
    calls=[]
    fail=False
    def __init__(self,url):
        self.calls.append(("new",url))
    def login(self,username,password):
        self.calls.append(("login",username))
        return "temporary-host-session","dn-owner"
    def revoke(self,standard,*,app_id=None,session_id=None):
        self.calls.append(("revoke",app_id,session_id))
        if self.fail:
            raise ProvisionError("Offline Music provider")


class OwnerMusicHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state=str(Path(self.tmp.name)/"owner")
        self.store=OwnerStore(self.state)
        self.policy=new_owner("user",profiles())
        with self.store.locked() as fd:
            self.store.write(fd,self.policy)
        self.config={"state_dir":self.state}
        self.account={
            "base_url":"http://127.0.0.1:12345",
            "owner_principal_id":self.policy["principals"][0]["id"],
            "username":"music-owner","password":"kept-only-on-host"
        }
        StubAPI.calls.clear()
        StubAPI.fail=False

    def set_grants(self):
        with self.store.locked() as fd:
            policy=self.store.read(fd)
            approve_device(policy,CLIENT,pairs())
            grant_music(policy,CLIENT,pairs(),owner_confirmed=True)
            self.store.write(fd,policy)

    def seed_issued(self):
        with self.store.locked() as fd:
            record_issued_locked(fd,{
                "client_id":CLIENT,
                "host_id":self.policy["host_id"],
                "dn_user_id":"dn-owner",
                "app_password_id":"app-1",
                "companion_session_id":"session-1",
            },expected_host_id=self.policy["host_id"])

    def test_no_account_access_before_explicit_music_grant(self):
        fake_provision=Mock()
        reader=Mock(return_value=self.account)
        action={"version":1,"action":"music_access"}
        with self.assertRaises(PolicyError):
            issue_ssh_music_access(
                request=action,verified_client_id=CLIENT,
                config=self.config,wolf_api=lambda *a:pairs(),
                host_approved=True,account_reader=reader,
                provision=fake_provision)
        reader.assert_not_called()
        fake_provision.assert_not_called()
        with self.store.locked() as fd:
            data=self.store.read(fd)
            approve_device(data,CLIENT,pairs())
            self.store.write(fd,data)
        with self.assertRaises(PolicyError):
            issue_ssh_music_access(
                request=action,verified_client_id=CLIENT,
                config=self.config,wolf_api=lambda *a:pairs(),
                host_approved=True,account_reader=reader,
                provision=fake_provision)
        reader.assert_not_called()

    def test_host_writes_revoke_mapping_before_sharing_client_secrets(self):
        self.set_grants()
        def issue(policy,client,paired,*,host_account,record_grants):
            record_grants({
                "client_id":client,
                "host_id":policy["host_id"],
                "dn_user_id":"dn-owner",
                "app_password_id":"app-1",
                "companion_session_id":"session-1",
            })
            return {"app_password":"client-app-secret","rest_token":"client-rest"}
        result=issue_ssh_music_access(
            request={"version":1,"action":"music_access"},
            verified_client_id=CLIENT,config=self.config,
            wolf_api=lambda *a:pairs(),host_approved=True,
            account_reader=lambda:self.account,provision=issue)
        self.assertEqual(result["credentials"],
                         {"app_password":"client-app-secret",
                          "rest_token":"client-rest"})
        with self.store.locked() as fd:
            item=get_device_locked(fd,CLIENT)
        self.assertEqual(item["app_password_id"],"app-1")
        self.assertNotIn("client-rest",json.dumps(item))
        self.assertNotIn("client-app-secret",json.dumps(item))

    def test_revoke_provider_first_then_remove_music_policy_and_ids(self):
        self.set_grants();self.seed_issued()
        with self.assertRaisesRegex(PolicyError,"confirmation"):
            revoke_owner_music_device(
                client_id=CLIENT,state_dir=self.state,
                account_reader=lambda:self.account,api_factory=StubAPI)
        self.assertFalse(StubAPI.calls)
        response=revoke_owner_music_device(
            client_id=CLIENT,state_dir=self.state,confirmed=True,
            account_reader=lambda:self.account,api_factory=StubAPI)
        self.assertEqual(response["status"],"music_revoked")
        self.assertIn(("revoke","app-1","session-1"),StubAPI.calls)
        with self.store.locked() as fd:
            self.assertIsNone(get_device_locked(fd,CLIENT))
            data=self.store.read(fd)
        self.assertEqual(data["devices"][0]["services"],["games"])
        self.assertFalse(data["devices"][0]["revoked"])

    def test_upstream_failure_retains_revoke_record_for_retry(self):
        self.set_grants();self.seed_issued()
        StubAPI.fail=True
        with self.assertRaises(ProvisionError):
            revoke_owner_music_device(
                client_id=CLIENT,state_dir=self.state,confirmed=True,
                account_reader=lambda:self.account,api_factory=StubAPI)
        with self.store.locked() as fd:
            self.assertIsNotNone(get_device_locked(fd,CLIENT))
            self.assertEqual(self.store.read(fd)["devices"][0]["services"],
                             ["games","music"])

    def test_no_client_chosen_parameters_or_false_host_gate(self):
        self.set_grants()
        for request in (
            {"version":1,"action":"music_access","client_id":CLIENT},
            {"version":1,"action":"music_access","host":"other"},
            {"version":1,"action":"music_access","token":"fake"},
            {"version":1,"action":"music_access","password":"fake"},
        ):
            with self.subTest(request=request),self.assertRaises(PolicyError):
                issue_ssh_music_access(
                    request=request,verified_client_id=CLIENT,
                    config=self.config,wolf_api=lambda *a:pairs(),
                    host_approved=True,account_reader=lambda:self.account)
        with self.assertRaises(PolicyError):
            issue_ssh_music_access(
                request={"version":1,"action":"music_access"},
                verified_client_id=CLIENT,config=self.config,
                wolf_api=lambda *a:pairs(),host_approved=False,
                account_reader=lambda:self.account)

    def test_host_account_file_must_be_0600_and_not_symlink(self):
        folder=Path(self.tmp.name)/"config"
        folder.mkdir(mode=0o700)
        path=folder/"music.json"
        path.write_text(json.dumps({"version":1,**self.account}))
        path.chmod(0o600)
        self.assertEqual(read_owner_music_account(path)["username"],"music-owner")
        path.chmod(0o644)
        with self.assertRaises(PolicyError):
            read_owner_music_account(path)
        path.unlink()
        path.symlink_to(folder/"missing")
        with self.assertRaises(OSError):
            read_owner_music_account(path)

if __name__=="__main__":
    unittest.main()
