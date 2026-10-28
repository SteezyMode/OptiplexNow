#!/usr/bin/env python3
"""Owner-authorized Jellyfin discovery for NOW's Videos button.

Requests availability through the existing forced-command, per-device Games
credential. Does not accept an arbitrary media URL from the remote host.
The destination is the selected, trusted NOW host on fixed port 8096.
Jellyfin sign-in remains Jellyfin's own responsibility.
"""
import argparse
import http.client
import ipaddress
import json
from pathlib import Path
import re
import stat
import subprocess
import sys

KEY = Path.home() / ".local/share/optiplex-now/games-client/id_ed25519"
HOST_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z")
USER_RE = re.compile(r"[a-z_][a-z0-9_-]{0,31}\Z", re.I)


def valid_target(host, user):
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not HOST_RE.fullmatch(host) or ".." in host:
            raise ValueError("Invalid host")
    if not USER_RE.fullmatch(user):
        raise ValueError("Invalid user")


def discover(host, user, *, runner=subprocess.run, connector=http.client.HTTPConnection):
    valid_target(host, user)
    if KEY.is_symlink() or not KEY.is_file():
        raise ValueError("Unenrolled media device")
    mode = KEY.stat()
    if (mode.st_uid != __import__("os").geteuid() or mode.st_nlink != 1
            or stat.S_IMODE(mode.st_mode) != 0o600):
        raise ValueError("Unsafe device key")
    argv = ["ssh", "-F", "/dev/null", "-i", str(KEY),
            "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=6",
            "-o", "ConnectionAttempts=1", "-o", "ClearAllForwardings=yes",
            "-T", "-l", user, "--", host]
    response = runner(argv, input=b'{"version":1,"action":"media"}\n',
                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                      timeout=15, check=False)
    if response.returncode != 0 or len(response.stdout) > 1024:
        raise ValueError("Host media authorization failed")
    data = json.loads(response.stdout)
    if (not isinstance(data, dict) or data.get("success") is not True
            or data.get("service") != "jellyfin"
            or data.get("available") is not True):
        raise ValueError("No authorized Jellyfin available")
    # New hosts publish the public Jellyfin instance ID obtained from the
    # host's own local probe. Never trust a returned hostname, URL or token.
    # Older deployed beta hosts omit server_id; retain legacy 8096 access until
    # they can be upgraded, but do not claim identity binding for that path.
    expected_id = data.get("server_id")
    if expected_id is not None and (not isinstance(expected_id, str)
                                    or not re.fullmatch(
                                        r"[A-Za-z0-9_-]{1,128}", expected_id)):
        raise ValueError("Invalid authenticated Jellyfin identity")
    conn = connector(host, 8096, timeout=4)
    try:
        conn.request("GET", "/System/Info/Public", headers={"Accept":"application/json"})
        result = conn.getresponse()
        if result.status != 200:
            raise ValueError("Jellyfin is not reachable")
        body = result.read(8193)
        if len(body) > 8192:
            raise ValueError("Oversized Jellyfin response")
        info = json.loads(body)
        if (not isinstance(info, dict) or not isinstance(info.get("Id"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", info["Id"])):
            raise ValueError("Invalid Jellyfin response")
        if expected_id is not None and info["Id"] != expected_id:
            raise ValueError("Jellyfin server differs from authorized host")
    finally:
        conn.close()
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("host")
    p.add_argument("user")
    args = p.parse_args()
    try:
        discover(args.host, args.user)
    except (OSError, ValueError, subprocess.TimeoutExpired, KeyError,
            TypeError, json.JSONDecodeError):
        print("unavailable")
        return 1
    print("available")
    return 0


if __name__ == "__main__":
    sys.exit(main())
