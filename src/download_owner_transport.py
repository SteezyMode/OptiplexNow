"""Shared fixed SSH argument vector for owner-approved Downloads clients.

Only argv construction belongs here. Each caller must validate host/user/key,
the requested action and the bounded request/response independently.
Preserve the existing forced-command transport: no shell, no admin key,
no host-provided command, no relaxed host-key policy.
"""


def restricted_ssh_argv(host, user, key):
    """Return the exact v1.22.1 Downloads SSH argv (no subprocess execution).

    This is NOT an authorization or host validation function. All call sites
    must reject unapproved targets and missing device credentials first.
    """
    return [
        "ssh", "-F", "/dev/null", "-T", "-i", str(key),
        "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=6",
        f"{user}@{host}",
    ]

import json
import os
from pathlib import Path
import pwd
import socket
import stat
import subprocess

LOCAL_HELPER = "/usr/lib/optiplex-now/owner-bridge/server/owner_downloads_local.py"


def is_local_owner_target(host, user):
    """True only for the same logged-in owner and an assigned host IPv4."""
    if not isinstance(host, str) or not isinstance(user, str):
        return False
    try:
        if os.getuid() == 0 or pwd.getpwuid(os.getuid()).pw_name != user:
            return False
        config = Path.home() / ".config/optiplex-now/owner-games-host.json"
        helper = Path(LOCAL_HELPER)
        if (config.is_symlink() or not config.is_file()
                or not helper.is_file() or helper.is_symlink()):
            return False
        info = config.stat()
        if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
            return False
        interfaces = subprocess.run(
            ["ip", "-j", "-4", "addr", "show"], capture_output=True,
            text=True, timeout=3, check=True)
        ips = {"127.0.0.1"}
        for dev in json.loads(interfaces.stdout):
            for entry in dev.get("addr_info", []):
                if entry.get("family") == "inet":
                    ips.add(entry.get("local"))
        targets = {row[4][0] for row in socket.getaddrinfo(
            host, None, socket.AF_INET, socket.SOCK_STREAM)}
        return bool(targets) and targets.issubset(ips)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


def downloads_transport_argv(host, user, key):
    if is_local_owner_target(host, user):
        return ["/usr/bin/python3", LOCAL_HELPER]
    return restricted_ssh_argv(host, user, key)
