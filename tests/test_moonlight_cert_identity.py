"""Offline certificate proof checks: no host network, private key transfer, Wolf edits."""
import base64
import configparser
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "server")]
from moonlight_cert_identity import message, verify_binding, wolf_certificate_client_id
from owner_access import PolicyError

spec = importlib.util.spec_from_file_location(
    "moonlight_identity_proof", ROOT / "src/moonlight-identity-proof.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def credentials():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Moonlight Client")])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(private.public_key()).serial_number(1234567)
            .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
            .sign(private, hashes.SHA256()))
    return (cert.public_bytes(serialization.Encoding.PEM).decode(),
            private.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()).decode())


class CertificateBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.clientconf = root / "Moonlight.conf"
        self.wolfconf = root / "wolf.toml"
        self.cert, self.key = credentials()
        self.request = "a"*32
        self.code = "123456"
        self.fingerprint = "b"*20
        self.client_id = wolf_certificate_client_id(self.cert.encode("utf-8"))
        self.wolf = lambda method, path: {"success": True, "clients": [
            {"client_id": self.client_id, "app_state_folder": self.client_id}]}
        self.clientconf.write_text(
            "[General]\ncertificate=@ByteArray(" +
            self.cert.replace("\n", r"\n") +
            ")\nkey=@ByteArray(" + self.key.replace("\n", r"\n") + ")\n")
        self.clientconf.chmod(0o600)
        self.set_wolf_config(self.client_id, self.cert)

    def set_wolf_config(self, client_id, cert):
        import json
        self.wolfconf.write_text("paired_clients = [{client_cert=" +
                                 json.dumps(cert) +
                                 ", app_state_folder=" + json.dumps(client_id) + "}]\n")
        self.wolfconf.chmod(0o600)

    def sign(self):
        return client.sign_for_request(self.clientconf,
                   message(self.request, self.code, self.fingerprint))

    def verify(self, proof=None, **kwargs):
        v = dict(wolf_config=self.wolfconf, wolf_api=self.wolf,
                 client_id=self.client_id, request_id=self.request,
                 code=self.code, fingerprint=self.fingerprint)
        v.update(self.sign() if proof is None else proof)
        v.update(kwargs)
        return verify_binding(**v)

    def test_wolf_libstdcpp_hash_matches_real_gcc_test_vectors(self):
        vectors = {
            b"hello": "2762169579135187400",
            b"": "6142509188972423790",
            b"-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n":
                "2397079258150423612",
        }
        for raw, expected in vectors.items():
            with self.subTest(raw=raw):
                self.assertEqual(wolf_certificate_client_id(raw), expected)

    def test_valid_proof_never_returns_or_writes_private_key(self):
        proof = self.sign()
        self.assertNotIn("PRIVATE KEY", str(proof))
        self.assertEqual(self.verify(proof), self.client_id)
        self.assertEqual(self.clientconf.stat().st_mode & 0o777, 0o600)

    def test_request_code_fingerprint_signature_are_all_bound(self):
        for data in (dict(code="654321"), dict(request_id="c"*32),
                     dict(fingerprint="d"*20)):
            with self.subTest(data=data), self.assertRaises(PolicyError):
                self.verify(**data)

    def test_other_paired_certificate_cannot_impersonate_a_client(self):
        other_cert, _ = credentials()
        self.set_wolf_config(self.client_id, other_cert)
        with self.assertRaisesRegex(PolicyError, "does not match"):
            self.verify()
        # app_state_folder is not the identity: a custom storage
        # folder cannot change the cert-derived Wolf ID.
        self.set_wolf_config("123456789", self.cert)
        self.assertEqual(self.verify(), self.client_id)
        self.set_wolf_config(self.client_id, self.cert)
        self.wolf = lambda *_: {"success": True, "clients": []}
        with self.assertRaises(PolicyError):
            self.verify()

    def test_bad_private_key_and_untrusted_wolf_config_denied(self):
        other_cert, other_key = credentials()
        self.clientconf.write_text(
            "[General]\ncertificate=@ByteArray(" +
            self.cert.replace("\n", r"\n") + ")\nkey=@ByteArray(" +
            other_key.replace("\n", r"\n") + ")\n")
        with self.assertRaises(ValueError):
            self.sign()
        self.clientconf.write_text("malformed settings\n")
        with self.assertRaises(configparser.Error):
            self.sign()
        self.set_wolf_config(self.client_id, self.cert)
        self.wolfconf.chmod(0o666)
        with self.assertRaises(PolicyError):
            self.verify(proof={"certificate_pem": self.cert, "signature_b64": "AA=="})

    def test_bad_signature_or_format_rejected(self):
        proof = self.sign()
        proof["signature_b64"] = base64.b64encode(b"forged").decode()
        with self.assertRaises(PolicyError):
            self.verify(proof)
        with self.assertRaises(PolicyError):
            message("wrong", self.code, self.fingerprint)


if __name__ == "__main__":
    unittest.main()
