#!/usr/bin/env python3
"""Owner-only alpha enrollment request / explicit local approval.

Clients may stage a public-key request over the *existing* owner's ordinary
SSH session. Staging grants nothing. The owner must compare the request code
on the client, independently identify its Wolf paired client ID, and confirm
that binding in a trusted local host UI. A remote/client-supplied ID is NEVER
an authority. This is NOT a multi-user or untrusted-member SSH service.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from owner_access import OwnerStore, PolicyError, approve_device, paired_client_ids
from owner_games_enroll import authorized_line, validated_ed25519_public
from wolf_docker_adapter import WolfDockerAPI

MAX_REQUEST = 2048
MAX_AUTH = 1024 * 1024
MAX_PENDING = 16
TTL = 600
REQUEST_ID = re.compile(r"[0-9a-f]{32}\Z")
CODE = re.compile(r"[0-9]{6}\Z")


def _read_private_config():
    """Read only the owner-managed host policy location; do not import broker runtime."""
    path = Path.home() / ".config/optiplex-now/owner-games-host.json"
    if path.is_symlink() or not path.is_file():
        raise PolicyError("Owner host is not configured")
    meta = path.stat()
    if (meta.st_uid != os.geteuid() or stat.S_IMODE(meta.st_mode) != 0o600
            or meta.st_size > 2048 or meta.st_nlink != 1):
        raise PolicyError("Owner host configuration is unsafe")
    data = json.loads(path.read_text("utf-8"))
    if (not isinstance(data, dict) or
            set(data) != {"version", "state_dir", "video_caps", "enabled",
                          "legacy_links_reviewed"} or
            data["version"] != 1 or
            not isinstance(data["state_dir"], str) or
            not Path(data["state_dir"]).is_absolute()):
        raise PolicyError("Invalid owner host configuration")
    return data


def existing_broker_path(auth_text):
    """Reuse only one reviewed, already-installed restricted host broker."""
    found = set()
    for line in auth_text.splitlines():
        matched = re.fullmatch(
            r'restrict,command="/usr/bin/python3 (/[A-Za-z0-9_./-]+/owner_games_ssh[.]py) --client-id [0-9]{1,20}" ssh-ed25519 [A-Za-z0-9+/=]+',
            line.strip())
        if matched:
            found.add(matched.group(1))
    if len(found) != 1:
        raise PolicyError("One existing owner-restricted broker required")
    path = Path(found.pop())
    if path.is_symlink() or not path.is_file():
        raise PolicyError("Owner broker is unavailable")
    info = path.stat()
    if (info.st_uid not in (0, os.geteuid())
            or info.st_mode & 0o022 or info.st_nlink != 1):
        raise PolicyError("Owner broker is not trusted")
    return path


def _stage_dir(state_dir):
    state = Path(state_dir)
    if not state.is_absolute() or state.is_symlink():
        raise PolicyError("Unsafe owner state")
    directory = state / "pending-enrollment"
    if directory.is_symlink():
        raise PolicyError("Unsafe pending state")
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise PolicyError("Unsafe pending permissions")
    return directory


def _read_request_file(path):
    if path.is_symlink() or not path.is_file():
        raise PolicyError("Unsafe enrollment request")
    meta = path.stat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
            or stat.S_IMODE(meta.st_mode) != 0o600 or meta.st_nlink != 1
            or meta.st_size > MAX_REQUEST):
        raise PolicyError("Unsafe enrollment request permissions")
    obj = json.loads(path.read_text("ascii"))
    if not isinstance(obj, dict) or set(obj) != {
            "request_id", "code", "created", "public_key"}:
        raise PolicyError("Invalid enrollment request")
    if (not REQUEST_ID.fullmatch(obj["request_id"])
            or not CODE.fullmatch(obj["code"])
            or type(obj["created"]) is not int):
        raise PolicyError("Invalid enrollment request identity")
    obj["public_key"] = validated_ed25519_public(obj["public_key"])
    return obj


def _fingerprint(public_key):
    # Display-only identifier: not a substitute for confirming Wolf identity.
    return hashlib.sha256(public_key.encode("ascii")).hexdigest()[:20]


def stage_request(state_dir, public_key, *, now=None):
    public = validated_ed25519_public(public_key)
    current = int(time.time() if now is None else now)
    with OwnerStore(str(state_dir)).locked():
        directory = _stage_dir(state_dir)
        active = []
        for path in directory.iterdir():
            if not REQUEST_ID.fullmatch(path.name):
                raise PolicyError("Unexpected owner enrollment file")
            entry = _read_request_file(path)
            if entry["created"] + TTL > current:
                active.append(entry)
                if entry["public_key"] == public:
                    return { "success": True, "status": "pending",
                             "request_id": entry["request_id"],
                             "code": entry["code"],
                             "fingerprint": _fingerprint(public) }
        if len(active) >= MAX_PENDING:
            raise PolicyError("Too many pending owner enrollment requests")
        request_id = secrets.token_hex(16)
        code = f"{secrets.randbelow(1000000):06d}"
        obj = {"request_id": request_id, "code": code,
               "created": current, "public_key": public}
        path = directory / request_id
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            json.dump(obj, stream, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        return {"success": True, "status": "pending", "request_id": request_id,
                "code": code, "fingerprint": _fingerprint(public)}


def pending_requests(state_dir, *, now=None):
    current = int(time.time() if now is None else now)
    with OwnerStore(str(state_dir)).locked():
        directory = _stage_dir(state_dir)
        entries = []
        for path in directory.iterdir():
            if not REQUEST_ID.fullmatch(path.name):
                raise PolicyError("Unexpected owner enrollment file")
            entry = _read_request_file(path)
            if entry["created"] + TTL > current:
                entries.append({
                    "request_id": entry["request_id"], "code": entry["code"],
                    "fingerprint": _fingerprint(entry["public_key"]),
                    "seconds_remaining": entry["created"] + TTL - current})
        return sorted(entries, key=lambda x: x["request_id"])


def approve_request(state_dir, request_id, code, client_id, *,
                    confirmed=False, auth_path=None, broker_path=None,
                    wolf_api=None, now=None):
    if not confirmed:
        raise PolicyError("Local owner approval is required")
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise PolicyError("Invalid request")
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise PolicyError("Invalid code")
    current = int(time.time() if now is None else now)
    auth = Path(auth_path or Path.home() / ".ssh/authorized_keys")
    api = wolf_api or WolfDockerAPI()

    with OwnerStore(str(state_dir)).locked() as fd:
        path = _stage_dir(state_dir) / request_id
        entry = _read_request_file(path)
        if (entry["request_id"] != request_id or entry["code"] != code
                or entry["created"] + TTL <= current):
            raise PolicyError("Request expired or verification code mismatch")
        # Only the local owner selects and verifies this ID. A key/code,
        # Tailscale address, and request filename cannot provide Wolf rights.
        clients = api("GET", "/api/v1/clients")
        if client_id not in paired_client_ids(clients):
            raise PolicyError("Selected Wolf device is not paired")
        store = OwnerStore(str(state_dir))
        policy = store.read(fd)
        if policy is None:
            raise PolicyError("Owner policy not initialized")
        grants = [d for d in policy["devices"] if d["client_id"] == client_id]
        if grants and grants[0]["revoked"]:
            raise PolicyError("Revoked device needs separate owner review")
        if not grants:
            approve_device(policy, client_id, clients)
        if auth.is_symlink() or not auth.is_file() or auth.parent.is_symlink():
            raise PolicyError("Unsafe authorized_keys location")
        meta = auth.stat()
        if (meta.st_uid != os.geteuid() or not stat.S_ISREG(meta.st_mode)
                or meta.st_nlink != 1 or meta.st_size > MAX_AUTH
                or stat.S_IMODE(meta.st_mode) & 0o022):
            raise PolicyError("Unsafe authorized_keys permissions")
        old = auth.read_bytes()
        broker = Path(broker_path) if broker_path else existing_broker_path(old.decode("ascii"))
        if not broker.is_file() or broker.is_symlink():
            raise PolicyError("Restricted broker not installed")
        line = authorized_line(entry["public_key"], client_id, broker)
        key = entry["public_key"].split(" ", 1)[1].encode("ascii")
        if key in old:
            raise PolicyError("Key already installed; inspect its privileges")
        changed = old + (b"" if not old or old.endswith(b"\n") else b"\n") + line.encode("ascii") + b"\n"
        # Existing authorized keys are backed up BEFORE altering permissions.
        backup_dir = Path(state_dir) / "enrollment-backups"
        if backup_dir.is_symlink():
            raise PolicyError("Unsafe backup directory")
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        if (backup_dir.stat().st_uid != os.geteuid()
                or stat.S_IMODE(backup_dir.stat().st_mode) != 0o700):
            raise PolicyError("Unsafe backup permissions")
        backup = backup_dir / ("authorized_keys-" + request_id)
        with backup.open("xb") as stream:
            stream.write(old)
            stream.flush()
            os.fsync(stream.fileno())
        backup.chmod(0o600)
        tmp = auth.parent / (".now-owner-" + request_id)
        try:
            newfd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, stat.S_IMODE(meta.st_mode))
            with os.fdopen(newfd, "wb") as stream:
                stream.write(changed)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, auth)
            # A forced key with NO owner policy grant cannot start Games.
            # Only grant after the restricted authorized_keys line is installed.
            try:
                store.write(fd, policy)
            except Exception:
                # Do not silently leave a newly usable authorization on failure.
                auth.write_bytes(old)
                auth.chmod(stat.S_IMODE(meta.st_mode))
                raise
            path.unlink()
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
    return {"success": True, "status": "approved",
            "client_id": client_id, "fingerprint": _fingerprint(entry["public_key"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("request", "pending", "approve"))
    parser.add_argument("--request-id")
    parser.add_argument("--code")
    parser.add_argument("--client-id")
    parser.add_argument("--confirm-verified-device", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = _read_private_config()
        state = config["state_dir"]
        if args.action == "request":
            raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
            if len(raw) > MAX_REQUEST:
                raise PolicyError("Enrollment request too large")
            data = json.loads(raw)
            if not isinstance(data, dict) or set(data) != {"version", "public_key"} or type(data["version"]) is not int or data["version"] != 1:
                raise PolicyError("Invalid enrollment request protocol")
            reply = stage_request(state, data["public_key"])
        elif args.action == "pending":
            reply = {"success": True, "requests": pending_requests(state)}
        else:
            reply = approve_request(
                state, args.request_id, args.code, args.client_id,
                confirmed=args.confirm_verified_device)
        print(json.dumps(reply, separators=(",", ":"), sort_keys=True))
        return 0
    except (PolicyError, OSError, ValueError, TypeError, KeyError, UnicodeError,
            json.JSONDecodeError):
        print('{"success":false,"status":"denied"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
