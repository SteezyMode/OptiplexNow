#!/usr/bin/env python3
"""Generate (never install) a restricted SSH authorized_keys owner Games entry.

An operator explicitly identifies the enrolled Wolf client AND the public
key transferred from that client, compares their ownership independently,
and installs the resulting forced-command entry in authorized_keys. This
script cannot add SSH access or approve a Wolf device by itself.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from owner_access import OwnerStore, PolicyError, _valid_client_id, resolve_games
from wolf_docker_adapter import WolfDockerAPI

BASE64 = re.compile(r"[A-Za-z0-9+/]+={0,2}\Z")
CMD_PATH = re.compile(r"/[A-Za-z0-9_/.-]+\Z")


def validated_ed25519_public(text):
    if not isinstance(text, str) or len(text) > 1500:
        raise PolicyError("Invalid Games public key")
    parts = text.strip().split()
    if len(parts) < 2 or parts[0] != "ssh-ed25519" or not BASE64.fullmatch(parts[1]):
        raise PolicyError("Only an Ed25519 Games public key is supported")
    try:
        body = base64.b64decode(parts[1], validate=True)
        n = struct.unpack("!I", body[:4])[0]
        name = body[4:4+n]
        pos = 4+n
        size = struct.unpack("!I", body[pos:pos+4])[0]
        key = body[pos+4:]
    except (ValueError, struct.error):
        raise PolicyError("Malformed Ed25519 Games public key") from None
    if n != 11 or name != b"ssh-ed25519" or size != 32 or len(key) != 32:
        raise PolicyError("Malformed Ed25519 Games public key")
    return "ssh-ed25519 " + parts[1]


def authorized_line(public_key, verified_client_id, script_path):
    if not _valid_client_id(verified_client_id):
        raise PolicyError("Unknown owner Games client")
    script = str(script_path)
    if not CMD_PATH.fullmatch(script) or ".." in Path(script).parts:
        raise PolicyError("Invalid forced Games helper path")
    key = validated_ed25519_public(public_key)
    return (f'restrict,command="/usr/bin/python3 {script} '
            f'--client-id {verified_client_id}" {key}')


def prepare_entry(public_key, *, client_id, store, wolf_api, approved=False,
                  script_path=None):
    if approved is not True:
        raise PolicyError("Independent key/device owner approval required")
    script_path = (ROOT / "server/owner_games_ssh.py").resolve() if script_path is None else script_path
    if not Path(script_path).is_file():
        raise PolicyError("The installed Games host helper is unavailable")
    with store.locked() as fd:
        policy = store.read(fd)
        if policy is None:
            raise PolicyError("Owner Games policy is not initialized")
        resolve_games(policy, client_id,
                      wolf_api("GET", "/api/v1/clients"))
    return authorized_line(public_key, client_id, script_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key-file", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--confirm-key-device-binding", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not Path(args.state_dir).is_absolute():
            raise PolicyError("Absolute owner state directory required")
        keypath = Path(args.public_key_file)
        if not keypath.is_file() or keypath.is_symlink() or keypath.stat().st_size > 1500:
            raise PolicyError("Games public key file is not a regular short file")
        line = prepare_entry(
            keypath.read_text(encoding="ascii"),
            client_id=args.client_id, store=OwnerStore(args.state_dir),
            wolf_api=WolfDockerAPI(), approved=args.confirm_key_device_binding)
        print(line)
        return 0
    except (PolicyError, OSError, ValueError, UnicodeError):
        print('{"success":false,"status":"enrollment_denied"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
