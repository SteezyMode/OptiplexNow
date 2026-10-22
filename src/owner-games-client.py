#!/usr/bin/env python3
"""NOW Games restricted SSH client, independent of regular administrator SSH.

Each client uses a separate Ed25519 key. The host owner must install the
matching public key with an explicit forced command and bind it to the same
enrolled Moonlight device. Never use the general administrative SSH key.
No remote command or Docker control can be supplied by the client.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

HOST_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z")
USER_RE = re.compile(r"[a-z_][a-z0-9_-]{0,31}\Z", re.I)
ACTIONS = frozenset(("status", "start", "stop", "reconcile"))
KEY_DIR = Path.home() / ".local/share/optiplex-now/games-client"
MAX_RESPONSE = 2048


def validated_target(host, user):
    if not isinstance(host, str) or not isinstance(user, str):
        raise ValueError("Invalid Games server")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not HOST_RE.fullmatch(host) or ".." in host:
            raise ValueError("Invalid Games server")
    if not USER_RE.fullmatch(user):
        raise ValueError("Invalid Games SSH user")
    return host, user


def _checked_key_dir(path):
    if path.is_symlink():
        raise ValueError("Games key folder is a symlink")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError("Games key folder has unsafe permissions")
    return path


def ensure_key(path=KEY_DIR, *, keygen=subprocess.run):
    folder = _checked_key_dir(Path(path))
    private, public = folder / "id_ed25519", folder / "id_ed25519.pub"
    if any(p.is_symlink() for p in (private, public)):
        raise ValueError("Games key cannot be a symlink")
    if not private.exists() and not public.exists():
        keygen(["ssh-keygen", "-q", "-t", "ed25519", "-N", "",
                "-f", str(private)], stdout=subprocess.DEVNULL,
               stderr=subprocess.DEVNULL, timeout=15, check=True)
    elif private.exists() != public.exists():
        raise ValueError("Partial Games key pair; refusing replacement")
    for filename, permission in ((private, 0o600), (public, 0o644)):
        st = filename.stat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != permission):
            raise ValueError("Games key file permissions are unsafe")
    return private, public


def invoke(host, user, action, *, key_dir=KEY_DIR, runner=subprocess.run):
    validated_target(host, user)
    if action not in ACTIONS:
        raise ValueError("Unsupported Games action")
    directory = Path(key_dir)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Owner Games device is not enrolled")
    private = directory / "id_ed25519"
    if private.is_symlink() or not private.is_file():
        raise ValueError("Missing restricted Games credential")
    st = private.stat()
    if (st.st_uid != os.geteuid() or st.st_nlink != 1
            or stat.S_IMODE(st.st_mode) != 0o600):
        raise ValueError("Unsafe restricted Games credential")
    argv = ["ssh", "-F", "/dev/null", "-i", str(private),
            "-o", "IdentitiesOnly=yes",
            "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=6", "-o", "ConnectionAttempts=1",
            "-o", "ClearAllForwardings=yes", "-T", "-l", user, "--", host]
    request = (json.dumps({"version": 1, "action": action},
                          separators=(",", ":")) + "\n").encode()
    p = runner(argv, input=request, stdout=subprocess.PIPE,
               stderr=subprocess.DEVNULL, check=False,
               timeout=55 if action == "start" else 25)
    if (p.returncode or not isinstance(p.stdout, bytes)
            or len(p.stdout) > MAX_RESPONSE):
        raise RuntimeError("Restricted Games request unavailable")
    try:
        reply = json.loads(p.stdout)
    except (UnicodeDecodeError, ValueError):
        raise RuntimeError("Invalid Games response") from None
    if (not isinstance(reply, dict) or
            reply.get("success") is not True or
            reply.get("status") not in ("needs_wolf_ui",
                                        "wolf_ui_connected", "busy",
                                        "in_use", "joined", "idle")):
        raise RuntimeError("Games request denied by host")
    # No key, Steam account data or raw Wolf API object is forwarded.
    return reply


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", action="store_true",
                        help="Emit only a finite validated status token for GTK")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("keygen", help="Create a restricted per-device Games key")
    for action in ACTIONS:
        cmd = sub.add_parser(action)
        cmd.add_argument("host")
        cmd.add_argument("user")
    args = parser.parse_args(argv)
    try:
        if args.action == "keygen":
            if args.ui:
                raise ValueError("UI output is not supported for key generation")
            _, public = ensure_key()
            print(public.read_text(encoding="ascii").strip())
        else:
            result = invoke(args.host, args.user, args.action)
            # The GTK bridge accepts only one of these six exact tokens.
            # Never write arbitrary SSH/Wolf output, PINs or error strings.
            if args.ui:
                print(result["status"])
            else:
                print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError):
        print("unavailable" if args.ui else
              '{"success":false,"status":"unavailable"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
