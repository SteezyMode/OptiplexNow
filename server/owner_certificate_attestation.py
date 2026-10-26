"""Request-bound Moonlight certificate proof for owner enrollment.

All proof writes are owner-controlled, tied to the verified requesting
network peer, and isolated from normal Moonlight/Wolf configurations.
Only a successful final *owner* confirmation can grant restricted SSH access.
"""
import json
import os
from pathlib import Path
import re
import stat
import time

from owner_access import OwnerStore, PolicyError
from moonlight_cert_identity import verify_binding, _paired_host_certs
from owner_enrollment import (_stage_dir, _read_request_file, _fingerprint,
                              REQUEST_ID, TTL, _valid_source_ip)

MAX_PROOF = 11000


def _directory(state_dir):
    root = Path(state_dir)
    path = root / "certificate-proofs"
    if path.is_symlink():
        raise PolicyError("Unsafe certificate proof state")
    path.mkdir(mode=0o700, exist_ok=True)
    meta = path.stat()
    if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid()
            or stat.S_IMODE(meta.st_mode) != 0o700):
        raise PolicyError("Unsafe certificate proof permissions")
    return path


def _proof_path(state_dir, request_id):
    if not isinstance(request_id, str) or REQUEST_ID.fullmatch(request_id) is None:
        raise PolicyError("Invalid certificate proof request")
    return _directory(state_dir) / request_id


def _read_proof(state_dir, request_id):
    path = _proof_path(state_dir, request_id)
    if path.is_symlink() or not path.is_file():
        raise PolicyError("Certificate proof not recorded")
    meta = path.stat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
            or stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_nlink != 1
            or meta.st_size > MAX_PROOF):
        raise PolicyError("Unsafe certificate proof file")
    try:
        data = json.loads(path.read_text("ascii"))
    except (UnicodeError, ValueError) as exc:
        raise PolicyError("Invalid certificate proof") from exc
    if (not isinstance(data, dict)
            or set(data) != {"certificate_pem", "signature_b64", "source_ip"}):
        raise PolicyError("Invalid certificate proof fields")
    return data


def _load_request(state_dir, request_id, *, now=None):
    if not isinstance(request_id, str) or REQUEST_ID.fullmatch(request_id) is None:
        raise PolicyError("Invalid proof request reference")
    current = int(time.time() if now is None else now)
    entry = _read_request_file(_stage_dir(state_dir) / request_id)
    if entry["request_id"] != request_id or entry["created"] + TTL <= current:
        raise PolicyError("Expired certificate proof request")
    return entry


def resolve_attested_client(state_dir, request_id, entry, *, wolf_config, wolf_api):
    """Recheck signed proof inside the same owner lock as final SSH commit."""
    data = _read_proof(state_dir, request_id)
    if (not _valid_source_ip(entry["source_ip"])
            or data["source_ip"] != entry["source_ip"]):
        raise PolicyError("Certificate proof changed network origin")
    return verify_binding(
        wolf_config=wolf_config, wolf_api=wolf_api,
        certificate_pem=data["certificate_pem"],
        signature_b64=data["signature_b64"],
        request_id=request_id, code=entry["code"],
        fingerprint=_fingerprint(entry["public_key"]))


def record_proof(state_dir, request_id, *, observed_source,
                 certificate_pem, signature_b64, wolf_config,
                 wolf_api, now=None):
    if not _valid_source_ip(observed_source):
        raise PolicyError("Untrusted certificate proof transport")
    if not wolf_config:
        raise PolicyError("Certificate proof feature not configured")
    store = OwnerStore(str(state_dir))
    with store.locked():
        entry = _load_request(state_dir, request_id, now=now)
        if entry["source_ip"] != observed_source:
            raise PolicyError("Proof source differs from the staged SSH key")
        client_id = verify_binding(
            wolf_config=wolf_config, wolf_api=wolf_api,
            certificate_pem=certificate_pem,
            signature_b64=signature_b64, request_id=request_id,
            code=entry["code"], fingerprint=_fingerprint(entry["public_key"]))
        path = _proof_path(state_dir, request_id)
        # One proof per enrollment: retries must use a new request, not
        # replace evidence with a different Moonlight certificate.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        data = json.dumps({
            "certificate_pem": certificate_pem,
            "signature_b64": signature_b64,
            "source_ip": observed_source
        }, separators=(",", ":")).encode("ascii")
        if len(data) > MAX_PROOF:
            raise PolicyError("Certificate proof too large")
        fd = os.open(path, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return client_id


def witnessed_candidate(state_dir, request_id, *, wolf_config, wolf_api,
                        now=None):
    if not wolf_config:
        raise PolicyError("Certificate proof not configured")
    store = OwnerStore(str(state_dir))
    with store.locked():
        entry = _load_request(state_dir, request_id, now=now)
        return resolve_attested_client(state_dir, request_id, entry,
                                       wolf_config=wolf_config, wolf_api=wolf_api)


def consumed(state_dir, request_id):
    path = _proof_path(state_dir, request_id)
    if path.exists():
        path.unlink()
