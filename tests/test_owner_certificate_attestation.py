"""End-to-end host owner certificate enrollment transaction (offline fakes).

No real Wolf, SSH host, Tailscale, key write, or browser is contacted.
"""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "server"), str(ROOT / "tests")]
from owner_access import OwnerStore, PolicyError
from owner_enrollment import stage_request, approve_request, _fingerprint
from owner_certificate_attestation import (record_proof, witnessed_candidate)
from moonlight_cert_identity import message, wolf_certificate_client_id
from test_moonlight_cert_identity import credentials
from test_owner_enrollment import public_key
from test_owner_lobby import fixtures


class SignedOwnerApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / "owner-state"
        self.store = OwnerStore(str(self.state))
        with self.store.locked() as fd:
            self.store.write(fd, fixtures()[0])
        self.cert, self.key = credentials()
        self.client_id = wolf_certificate_client_id(self.cert.encode("utf-8"))
        self.source = "100.72.15.27"
        self.now = 1700000000
        self.wolfconf = self.base / "wolf.toml"
        self.wolfconf.write_text(
            "paired_clients=[{client_cert=" + json.dumps(self.cert) +
            ', app_state_folder="custom-profile-storage"}]\n')
        self.wolfconf.chmod(0o600)
        self.wolf = lambda method, path: (
            {"success": True, "clients": [{
                "client_id": self.client_id, "app_state_folder": "custom-profile-storage"}]}
            if (method, path) == ("GET", "/api/v1/clients") else
            self.fail("Unexpected Wolf API operation: " + path))
        self.ssh = self.base / ".ssh"
        self.ssh.mkdir(mode=0o700)
        self.auth = self.ssh / "authorized_keys"
        self.original = "ssh-ed25519 AAAATEST unchanged-owner\n"
        self.auth.write_text(self.original)
        self.auth.chmod(0o600)
        self.broker = ROOT / "server/owner_games_ssh.py"
        self.pub = public_key(b"m")
        self.request = stage_request(
            self.state, self.pub, source_ip=self.source, now=self.now)

    def proof(self):
        key = serialization.load_pem_private_key(
            self.key.encode("ascii"), password=None)
        data = message(self.request["request_id"], self.request["code"],
                       _fingerprint(self.pub))
        return base64.b64encode(
            key.sign(data, padding.PKCS1v15(), hashes.SHA256())).decode("ascii")

    def attest(self, **kwargs):
        values = dict(
            observed_source=self.source, certificate_pem=self.cert,
            signature_b64=self.proof(), wolf_config=self.wolfconf,
            wolf_api=self.wolf, now=self.now)
        values.update(kwargs)
        return record_proof(self.state, self.request["request_id"], **values)

    def approve(self, ident=None, **kwargs):
        return approve_request(
            self.state, self.request["request_id"], self.request["code"],
            ident or self.client_id,
            confirmed=True, auth_path=self.auth, broker_path=self.broker,
            wolf_api=self.wolf, now=self.now, wolf_config=self.wolfconf, **kwargs)

    def grants(self):
        with self.store.locked() as fd:
            return self.store.read(fd)["devices"]

    def test_signed_proof_then_phone_review_then_atomic_owner_approval(self):
        self.assertEqual(self.attest(), self.client_id)
        self.assertEqual(witnessed_candidate(
            self.state, self.request["request_id"], wolf_config=self.wolfconf,
            wolf_api=self.wolf, now=self.now), self.client_id)
        self.assertEqual(self.auth.read_text(), self.original)
        self.assertEqual(self.approve()["status"], "approved")
        self.assertEqual(len(self.grants()), 2)
        self.assertIn("--client-id " + self.client_id, self.auth.read_text())
        self.assertIn(self.original, self.auth.read_text())
        # Replaying a committed request must not grant anything.
        with self.assertRaises(PolicyError):
            self.approve()

    def test_no_certificate_evidence_refuses_to_approve(self):
        with self.assertRaisesRegex(PolicyError, "not recorded"):
            self.approve()
        self.assertEqual(self.auth.read_text(), self.original)
        self.assertEqual(len(self.grants()), 1)

    def test_wrong_source_wrong_id_wrong_proof_no_grant(self):
        with self.assertRaisesRegex(PolicyError, "Proof source differs"):
            self.attest(observed_source="100.72.15.28")
        self.assertEqual(self.auth.read_text(), self.original)
        with self.assertRaisesRegex(PolicyError, "signature mismatch"):
            self.attest(signature_b64=base64.b64encode(
                b"x" * 256).decode("ascii"))
        self.assertEqual(self.attest(), self.client_id)
        with self.assertRaisesRegex(PolicyError, "Wolf identity differs"):
            self.approve("99999999")
        self.assertEqual(self.auth.read_text(), self.original)
        self.assertEqual(len(self.grants()), 1)

    def test_cross_network_proof_remains_valid_without_a_live_session(self):
        # Staging comes from Tailscale; Wolf may stream over 192.168 LAN.
        # Certificate identity rather than matching IPs is the authority.
        self.attest()
        self.assertEqual(self.approve()["status"], "approved")
        self.assertEqual(len(self.grants()), 2)

    def test_registry_certificate_revocation_blocks_final_commit(self):
        self.attest()
        other, _ = credentials()
        self.wolfconf.write_text("paired_clients=[{client_cert=" +
                                 json.dumps(other) + "}]\n")
        with self.assertRaises(PolicyError):
            self.approve()
        self.assertEqual(self.auth.read_text(), self.original)
        self.assertEqual(len(self.grants()), 1)


if __name__ == "__main__":
    unittest.main()
