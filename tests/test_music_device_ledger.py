"""Owner Music revocation ledger never stores secrets or weakens Games."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"server")]
from owner_access import OwnerStore, PolicyError, new_owner
from music_device_ledger import (
    read_locked, record_issued_locked, get_device_locked, remove_device_locked,
)

HOST="00000000-0000-4000-8000-000000000001"

def sample(client="1001"):
    return {
        "host_id":HOST,
        "client_id":client,
        "dn_user_id":"user123",
        "app_password_id":"app123",
        "companion_session_id":"session123",
    }


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=OwnerStore(str(Path(self.tmp.name)/"private"))

    def test_owner_only_roundtrip_contains_no_passwords(self):
        with self.store.locked() as fd:
            self.assertEqual(read_locked(fd)["grants"],[])
            record_issued_locked(fd,sample(),expected_host_id=HOST)
            item=get_device_locked(fd,"1001")
            self.assertEqual(item,sample())
            with self.assertRaisesRegex(PolicyError,"already"):
                record_issued_locked(fd,sample(),expected_host_id=HOST)
            record_issued_locked(fd,sample("1002"),expected_host_id=HOST)
            self.assertEqual(len(read_locked(fd)["grants"]),2)
            remove_device_locked(fd,"1001")
            self.assertIsNone(get_device_locked(fd,"1001"))
            self.assertIsNotNone(get_device_locked(fd,"1002"))
        path=Path(self.tmp.name)/"private"/"owner-music-grants.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        # Identifier keys are expected (app_password_id); actual values
        # and bearer secrets must never be present in the revocation ledger.
        self.assertNotIn("client-app-secret",path.read_text())
        self.assertNotIn("host-admin-password",path.read_text())
        self.assertNotIn("rest_token",path.read_text())
        self.assertNotIn("secret",path.read_text())

    def test_reject_unrecognized_record_fields_and_cross_host(self):
        with self.store.locked() as fd:
            data=sample()
            with self.assertRaises(PolicyError):
                record_issued_locked(fd,data,expected_host_id="wrong")
            data["rest_token"]="never-allowed"
            with self.assertRaises(PolicyError):
                record_issued_locked(fd,data,expected_host_id=HOST)
            self.assertEqual(read_locked(fd)["grants"],[])

    def test_refuse_loose_mode_and_symlink_ledger(self):
        with self.store.locked() as fd:
            record_issued_locked(fd,sample(),expected_host_id=HOST)
        path=Path(self.tmp.name)/"private"/"owner-music-grants.json"
        path.chmod(0o644)
        with self.store.locked() as fd:
            with self.assertRaisesRegex(PolicyError,"Unsafe"):
                read_locked(fd)
        path.unlink()
        path.symlink_to(Path(self.tmp.name)/"outside")
        with self.store.locked() as fd:
            with self.assertRaises(OSError):
                read_locked(fd)

    def test_refuse_duplicate_and_unknown_versions(self):
        with self.store.locked() as fd:
            record_issued_locked(fd,sample(),expected_host_id=HOST)
        path=Path(self.tmp.name)/"private"/"owner-music-grants.json"
        for raw in (
            {"version":2,"grants":[]},
            {"version":1,"grants":[sample(),sample()]},
            {"version":1,"grants":[{"client_id":"1"}]},
        ):
            path.write_text(json.dumps(raw),encoding="utf-8")
            path.chmod(0o600)
            with self.store.locked() as fd:
                with self.assertRaises(PolicyError):
                    read_locked(fd)

if __name__=="__main__":
    unittest.main()
