#!/usr/bin/env python3
"""Connect Music using an EXISTING, approved NOW device's restricted SSH key.

No user enters DroppedNeedle credentials. A host-owner-linked Music account
and an explicit owner Music grant are required on the host. A signed-in
Tailnet or a Wolf-paired device alone is NEVER enough.

The host issues two independently revocable capabilities through the
existing pinned forced-command SSH channel. The client verifies the keys
against its configured Music host and commits them to the OS Secret Service.
No secret is included in argv, environment, logs or normal stdout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import os
import subprocess
import sys
from urllib.parse import urlencode

from music_subsonic import endpoint_for, query, MusicTransportError
from music_keyring import vault, secret_api as playback_secret_api
from music_rest import save_session, clear_session, secret_api as rest_secret_api

KEY_DIR = Path.home()/".local/share/optiplex-now/games-client"
MAX_REPLY = 8192
MUSIC_TIMEOUT = 65


class EnrollmentError(Exception):
    """Non-secret error; messages are safe in GTK and diagnostics."""


def _validated_target(host, user):
    from importlib.util import module_from_spec, spec_from_loader
    from importlib.machinery import SourceFileLoader
    file = Path(__file__).with_name("owner-games-client.py")
    loader = SourceFileLoader("bruiser_games_target", str(file))
    spec = spec_from_loader(loader.name, loader)
    mod = module_from_spec(spec)
    loader.exec_module(mod)
    return mod.validated_target(host, user)


def request(host: str, user: str, *, key_dir=KEY_DIR,
            runner=subprocess.run):
    """Only the exact music_access action reaches the host.

    This helper MUST NOT create a restricted SSH key on its own; enrollment
    is an existing separate owner-confirmation flow.
    """
    host, user = _validated_target(host, user)
    directory = Path(key_dir)
    if directory.is_symlink() or not directory.is_dir():
        raise EnrollmentError("Approve this device in Bruiser before using Music.")
    private = directory / "id_ed25519"
    if private.is_symlink() or not private.is_file():
        raise EnrollmentError("Bruiser device enrollment is incomplete.")
    info = private.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
        raise EnrollmentError("Bruiser device key is not private.")
    argv = [
        "ssh", "-F", "/dev/null", "-i", str(private),
        "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=6",
        "-o", "ConnectionAttempts=1", "-o", "ClearAllForwardings=yes",
        "-T", "-l", user, "--", host,
    ]
    data = b'{"version":1,"action":"music_access"}\n'
    try:
        proc = runner(argv, input=data, stdout=subprocess.PIPE,
                      stderr=subprocess.DEVNULL, timeout=MUSIC_TIMEOUT,
                      check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise EnrollmentError("Music authorization unavailable; verify owner approval.") from None
    if proc.returncode != 0 or not isinstance(proc.stdout, bytes) or len(proc.stdout)>MAX_REPLY:
        raise EnrollmentError("Music authorization unavailable; approve Music on this device.")
    try:
        reply = json.loads(proc.stdout)
    except (UnicodeError, ValueError):
        raise EnrollmentError("Invalid Music device approval response.") from None
    if (not isinstance(reply, dict) or set(reply)!={
            "success", "service", "credentials"}
            or reply["success"] is not True or reply["service"]!="music"
            or not isinstance(reply["credentials"],dict)
            or set(reply["credentials"])!={"app_password","rest_token"}):
        raise EnrollmentError("Invalid Music device approval response.")
    credentials=reply["credentials"]
    for key in ("app_password", "rest_token"):
        value=credentials[key]
        if not isinstance(value,str) or not 16<=len(value)<=2048 or any(
            ord(c)<33 or ord(c)>126 for c in value):
            raise EnrollmentError("Invalid issued Music credentials.")
    return credentials


def enroll(host, user, music_url, *, acquire=request,
           playback_store=vault, rest_store=save_session):
    """End-to-end provisioning, fail closed until keyrings and server verify."""
    endpoint_for(music_url,"ping")
    # Check BOTH native keyring providers before creating upstream tokens;
    # a locked keyring must not mint an unrecordable issued credential.
    playback_secret_api()
    rest_secret_api()
    credentials = acquire(host, user)
    # Verify playback identity before accepting the account into the vault.
    query(music_url,"ping",{"apiKey":credentials["app_password"]})
    form=urlencode({"api_key":credentials["app_password"],"username":""})
    try:
        rest_store(music_url, credentials["rest_token"])
        playback_store("store", music_url, form)
    except Exception:
        # No partially trusted local session left on either side. The host
        # still has revoke IDs; owner may revoke/reissue after a failed setup.
        try: clear_session(music_url)
        except Exception: pass
        try: vault("clear",music_url)
        except Exception: pass
        raise EnrollmentError(
            "Music access was issued but device keyring could not save it. "
            "Revoke the device's Music grant before retrying.") from None
    return "connected"


def main(argv=None):
    parser=argparse.ArgumentParser(description="Bruiser approved-device Music setup")
    parser.add_argument("host")
    parser.add_argument("user")
    parser.add_argument("music_url")
    args=parser.parse_args(argv)
    try:
        enroll(args.host,args.user,args.music_url)
        print("connected")
        return 0
    except Exception:
        # Upstream URLs, usernames or secrets are never printed to GTK.
        print("unavailable")
        return 1


if __name__=="__main__":
    sys.exit(main())
