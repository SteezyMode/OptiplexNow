"""Host-owned Music device revocation metadata, never access tokens.

Use only under the same OwnerStore.locked() directory lock as the signed NOW
owner policy. A durable record is required BEFORE a newly issued per-device
credential can leave the restricted SSH response.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import stat

from owner_access import PolicyError

NAME = "owner-music-grants.json"
VERSION = 1
MAX_SIZE = 64 * 1024
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
CLIENT = re.compile(r"[0-9]{1,20}\Z")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


def _valid_record(record):
    return (
        isinstance(record, dict)
        and set(record) == {
            "client_id", "host_id", "dn_user_id",
            "app_password_id", "companion_session_id"
        }
        and isinstance(record["client_id"], str)
        and CLIENT.fullmatch(record["client_id"]) is not None
        and isinstance(record["host_id"], str)
        and UUID.fullmatch(record["host_id"]) is not None
        and all(isinstance(record[key], str) and
                ID.fullmatch(record[key]) is not None
                for key in ("dn_user_id", "app_password_id", "companion_session_id"))
    )


def validate(records):
    if not isinstance(records, dict) or set(records) != {"version", "grants"}:
        raise PolicyError("Invalid Music grant ledger")
    if type(records["version"]) is not int or records["version"] != VERSION:
        raise PolicyError("Invalid Music grant ledger version")
    grants=records["grants"]
    if not isinstance(grants, list) or len(grants) > 512:
        raise PolicyError("Invalid Music grant inventory")
    ids=set()
    for record in grants:
        if not _valid_record(record) or record["client_id"] in ids:
            raise PolicyError("Invalid or duplicate Music device record")
        ids.add(record["client_id"])
    return records


def read_locked(directory_fd):
    try:
        fd=os.open(NAME, os.O_RDONLY | NOFOLLOW, dir_fd=directory_fd)
    except FileNotFoundError:
        return {"version":VERSION,"grants":[]}
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or info.st_size > MAX_SIZE):
            raise PolicyError("Unsafe Music grant ledger")
        content=os.read(fd, MAX_SIZE + 1)
    finally:
        os.close(fd)
    try:
        return validate(json.loads(content))
    except (ValueError, UnicodeError) as exc:
        raise PolicyError("Invalid Music grant ledger") from exc


def write_locked(directory_fd, records):
    validate(records)
    raw=json.dumps(records, sort_keys=True,
                   separators=(",",":")).encode("utf-8")
    if len(raw) > MAX_SIZE:
        raise PolicyError("Music grant ledger exceeds size limit")
    tmp=".music-grants-" + secrets.token_hex(12)
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|NOFOLLOW,
               0o600,dir_fd=directory_fd)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp,NAME,src_dir_fd=directory_fd,dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(tmp,dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def record_issued_locked(directory_fd, record, *, expected_host_id):
    """Atomic exact-device uniqueness check. Fails closed on reissue attempts."""
    if not _valid_record(record) or record["host_id"] != expected_host_id:
        raise PolicyError("Invalid Music device revocation record")
    entries=read_locked(directory_fd)
    if any(item["client_id"] == record["client_id"] for item in entries["grants"]):
        raise PolicyError("Music grant already has active device keys; revoke before reissuing")
    entries["grants"].append(record)
    write_locked(directory_fd, entries)


def get_device_locked(directory_fd, client_id):
    if not isinstance(client_id,str) or not CLIENT.fullmatch(client_id):
        raise PolicyError("Invalid Music client identifier")
    entries=read_locked(directory_fd)
    for record in entries["grants"]:
        if record["client_id"] == client_id:
            return dict(record)
    return None


def remove_device_locked(directory_fd, client_id):
    if not isinstance(client_id,str) or not CLIENT.fullmatch(client_id):
        raise PolicyError("Invalid Music client identifier")
    entries=read_locked(directory_fd)
    kept=[x for x in entries["grants"] if x["client_id"] != client_id]
    if len(kept) == len(entries["grants"]):
        raise PolicyError("No Music device credential exists")
    entries["grants"]=kept
    write_locked(directory_fd,entries)
