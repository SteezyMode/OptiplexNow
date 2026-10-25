"""Read-only Wolf certificate identity verification for owner-device enrollment.

This module does NOT enroll or authorize a device. It checks a detached
signature against the actual paired client certificate stored in the host's
trusted Wolf TOML configuration. It never requests or transfers a client
private key. Intended for the next opt-in certificate-binding endpoint.

Wolf client IDs are derived from the exact stored certificate byte string by
its 64-bit libstdc++ build; custom app_state_folder values do not affect IDs.
Unsupported Wolf hash algorithms must fail closed rather than guess.
"""
import base64
import hashlib
import os
from pathlib import Path
import re
import stat
import tomllib

from owner_access import PolicyError, paired_client_ids

MAX_TOML = 4 * 1024 * 1024
MAX_CERT = 8192
MAX_SIGNATURE = 1024
IDENT = re.compile(r"[0-9]{1,20}\Z")
REQUEST = re.compile(r"[0-9a-f]{32}\Z")
CODE = re.compile(r"[0-9]{6}\Z")
FINGERPRINT = re.compile(r"[0-9a-f]{20}\Z")


def message(request_id, code, fingerprint):
    if (not isinstance(request_id, str) or not REQUEST.fullmatch(request_id)
            or not isinstance(code, str) or not CODE.fullmatch(code)
            or not isinstance(fingerprint, str)
            or not FINGERPRINT.fullmatch(fingerprint)):
        raise PolicyError("Malformed owner identity challenge")
    return ("OptiPlex NOW owner-device proof v1\n" + request_id +
            "\n" + code + "\n" + fingerprint + "\n").encode("ascii")


def _cert(cert_bytes):
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        value = x509.load_pem_x509_certificate(cert_bytes)
        return value.public_bytes(serialization.Encoding.DER), value
    except (ValueError, TypeError) as exc:
        raise PolicyError("Invalid paired Moonlight certificate") from exc


def wolf_certificate_client_id(raw_cert):
    """Wolf's x86-64 libstdc++ std::hash<std::string> for paired cert PEM.

    This uses GCC's MurmurHash64A _Hash_bytes(seed=0xc70f6907).
    Do NOT substitute app_state_folder: Wolf lets users customize it.
    Fail closed if the host's Wolf build does not use this hash scheme.
    """
    if not isinstance(raw_cert, bytes):
        raise PolicyError("Invalid Wolf certificate representation")
    mask = (1 << 64) - 1
    m, r = 0xc6a4a7935bd1e995, 47
    h = (0xc70f6907 ^ (len(raw_cert) * m)) & mask
    end = len(raw_cert) & ~7
    for offset in range(0, end, 8):
        key = int.from_bytes(raw_cert[offset:offset + 8], "little")
        key = key * m & mask
        key ^= key >> r
        key = key * m & mask
        h ^= key
        h = h * m & mask
    rest = raw_cert[end:]
    if rest:
        for i, byte in enumerate(rest):
            h ^= byte << (8 * i)
        h = h * m & mask
    h ^= h >> r
    h = h * m & mask
    return str(h ^ (h >> r))


def _paired_host_certs(config_file):
    """Read only trusted Wolf TOML; independently derive Wolf client IDs."""
    config = Path(config_file)
    if not config.is_absolute() or config.is_symlink() or config.parent.is_symlink():
        raise PolicyError("Untrusted Wolf config path")
    meta = config.stat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid not in (0, os.geteuid())
            or meta.st_nlink != 1 or meta.st_mode & 0o022
            or not 0 < meta.st_size <= MAX_TOML):
        raise PolicyError("Untrusted Wolf config file")
    with config.open("rb") as file:
        raw = file.read(MAX_TOML + 1)
    if len(raw) > MAX_TOML:
        raise PolicyError("Wolf config exceeds permitted size")
    try:
        parsed = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise PolicyError("Malformed Wolf config") from exc
    entries = parsed.get("paired_clients")
    if not isinstance(entries, list) or len(entries) > 512:
        raise PolicyError("Invalid Wolf paired registry")
    matches = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PolicyError("Malformed paired Wolf client")
        pem = entry.get("client_cert")
        if not isinstance(pem, str) or len(pem.encode("utf-8")) > MAX_CERT:
            raise PolicyError("Invalid paired certificate")
        raw_cert = pem.encode("utf-8")
        client_id = wolf_certificate_client_id(raw_cert)
        der, _ = _cert(raw_cert)
        if client_id in matches and matches[client_id] != der:
            raise PolicyError("Conflicting Wolf certificate registry")
        matches[client_id] = der
    return matches


def verify_binding(*, wolf_config, wolf_api, client_id, certificate_pem,
                   signature_b64, request_id, code, fingerprint):
    """Prove local private-key possession and Wolf certificate membership.

    No authorization side effects. The requesting connection and pending
    key must be checked separately by the enrollment service.
    """
    if (not isinstance(client_id, str) or not IDENT.fullmatch(client_id)
            or not isinstance(certificate_pem, str)
            or not 1 <= len(certificate_pem.encode("utf-8")) <= MAX_CERT
            or not isinstance(signature_b64, str)
            or len(signature_b64) > 1500):
        raise PolicyError("Invalid certificate identity proof")
    data = message(request_id, code, fingerprint)
    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise PolicyError("Invalid Moonlight proof encoding") from exc
    if not 1 <= len(signature) <= MAX_SIGNATURE:
        raise PolicyError("Invalid Moonlight signature size")
    claimed_der, certificate = _cert(certificate_pem.encode("ascii"))
    known = _paired_host_certs(wolf_config)
    if client_id not in known or known[client_id] != claimed_der:
        raise PolicyError("Moonlight certificate does not match Wolf paired client ID")
    if client_id not in paired_client_ids(wolf_api("GET", "/api/v1/clients")):
        raise PolicyError("Wolf client no longer paired")
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.exceptions import InvalidSignature
        key = certificate.public_key()
        # Moonlight Qt identity manager currently generates RSA-2048; other
        # key types are not silently accepted until explicitly reviewed.
        if not isinstance(key, rsa.RSAPublicKey):
            raise PolicyError("Unsupported Moonlight certificate key type")
        key.verify(signature, data, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise PolicyError("Moonlight identity challenge signature mismatch") from exc
    return client_id
