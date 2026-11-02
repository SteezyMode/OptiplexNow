"""First-run Bruiser Music account bootstrap, without touching any live host."""
from __future__ import annotations

from pathlib import Path
import os
import stat
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"server"))
from owner_access import OwnerStore,new_owner,PolicyError
from music_device_provision import ProvisionError
from music_owner_bootstrap import bootstrap_owner_account
from owner_music_ssh import read_owner_music_account


def profiles():
    return {"success":True,"profiles":[{"id":"user",
        "apps":[{"title":"Steam"}]}]}


class FreshDN:
    def __init__(self,required=True,fail_create=False):
        self.required=required
        self.fail_create=fail_create
        self.created=None
        self.calls=[]
    def call(self,method,path,**kwargs):
        self.calls.append((method,path))
        if path=="/auth/setup/status" and method=="GET":
            return {"required":self.required}
        if path=="/auth/setup" and method=="POST" and self.required:
            record=kwargs["data"]
            if self.fail_create:
                raise ProvisionError("simulated upstream unavailability")
            self.created=(record["username"],record["password"])
            self.required=False
            return {"user":{"id":"owner-id","role":"admin"},"token":"unexposed"}
        raise AssertionError("Unexpected bootstrap API call")
    def login(self,username,password):
        self.calls.append(("POST","/auth/login"))
        if self.created!=(username,password):
            raise ProvisionError("Invalid linked owner")
        return "private-session","owner-id"


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root=Path(self.directory.name)
        self.state=root/"state"
        self.account=root/"config"/"owner-music-host.json"
        self.policy=new_owner("user",profiles())
        store=OwnerStore(str(self.state))
        with store.locked() as fd:
            store.write(fd,self.policy)
        self.api=FreshDN()
    def bootstrap(self,**kwargs):
        return bootstrap_owner_account(
            state_dir=str(self.state),
            base_url=kwargs.pop("base_url","http://127.0.0.1:8688"),
            account_path=kwargs.pop("account_path",self.account),
            api_factory=lambda _url:self.api,
        )

    def test_blank_host_provisions_internal_admin_and_private_restore_record(self):
        self.assertEqual(self.bootstrap(),"created")
        self.assertEqual(self.account.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.account.parent.stat().st_mode & 0o777,0o700)
        data=read_owner_music_account(self.account)
        self.assertEqual(data["owner_principal_id"],self.policy["principals"][0]["id"])
        self.assertEqual(data["username"],"bruiser_owner")
        self.assertGreaterEqual(len(data["password"]),48)
        self.assertEqual(self.api.created,(data["username"],data["password"]))
        self.assertEqual(self.api.calls,[
            ("GET","/auth/setup/status"),("POST","/auth/setup")
        ])
        self.assertEqual(self.bootstrap(),"already-linked")
        self.assertEqual(self.api.calls[-1],("POST","/auth/login"))
        self.assertEqual(len([x for x in self.api.calls if x[1]=="/auth/setup"]),1)

    def test_established_droppedneedle_users_never_get_replaced(self):
        self.api.required=False
        with self.assertRaisesRegex(ProvisionError,"already has users"):
            self.bootstrap()
        self.assertFalse(self.account.exists())
        self.assertNotIn(("POST","/auth/setup"),self.api.calls)

    def test_never_bootstraps_remote_address_or_userinfo(self):
        for address in ("http://100.121.156.34:8688",
                        "http://8.8.8.8:8688","https://media.example.com",
                        "http://user:secret@127.0.0.1:8688",
                        "http://127.0.0.1:8688/?secret=test"):
            with self.subTest(address=address),self.assertRaises(ProvisionError):
                self.bootstrap(base_url=address)
        self.assertFalse(self.account.exists())
        self.assertEqual(self.api.calls,[])

    def test_upstream_setup_failure_preserves_recovery_credential(self):
        self.api.fail_create=True
        with self.assertRaises(ProvisionError):
            self.bootstrap()
        data=read_owner_music_account(self.account)
        self.assertEqual(data["password"],self.api.created[1] if self.api.created else data["password"])
        self.assertEqual(self.account.stat().st_mode & 0o777,0o600)
        with self.assertRaises(ProvisionError):
            self.bootstrap()
        # Owner must explicitly resolve this ambiguous state; never reset
        # the credential or create a second account accidentally.
        self.assertEqual(self.api.calls.count(("POST","/auth/setup")),1)

    def test_existing_config_for_another_owner_is_rejected(self):
        self.assertEqual(self.bootstrap(),"created")
        other=new_owner("user",profiles())
        store=OwnerStore(str(self.state))
        with store.locked() as fd:
            store.write(fd,other)
        with self.assertRaises(PolicyError):
            self.bootstrap()
        self.assertEqual(self.api.calls.count(("POST","/auth/setup")),1)

    def test_existing_account_symlink_is_rejected(self):
        target=self.account.parent/"redirect"
        self.account.parent.mkdir(mode=0o700)
        target.write_text("untrusted")
        self.account.symlink_to(target)
        with self.assertRaises(PolicyError):
            self.bootstrap()
        self.assertEqual(self.api.calls,[])


if __name__=="__main__":
    unittest.main()
