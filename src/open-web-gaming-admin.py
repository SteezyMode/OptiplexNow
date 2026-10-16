#!/usr/bin/env python3
"""Open MoonlightWeb admin through a trusted SSH loopback tunnel.

Requires a previously authorized SSH key and a reachable server (normally Tailscale).
Never passes a MoonlightWeb credential to a URL or the command line.
"""
from __future__ import annotations

import hashlib
import re
import socket
import subprocess
import sys
from pathlib import Path


def tunnel_settings(host: str, user: str, home: Path) -> tuple[Path, int]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,248}", host):
        raise ValueError("Invalid server host")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}", user):
        raise ValueError("Invalid SSH username")
    fingerprint = hashlib.sha256(f"{user}@{host}".encode()).hexdigest()
    directory = home / ".cache" / "optiplex-now"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    return directory / f"admin-{fingerprint[:16]}.sock", 20000 + int(fingerprint[:8], 16) % 20000


def checked_run(argv: list[str], seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=seconds, check=False)


def open_admin(host: str, user: str, home: Path) -> int:
    control, port = tunnel_settings(host, user, home)
    check = ["ssh", "-S", str(control), "-O", "check", "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=3", "-l", user, host]
    try:
        existing = checked_run(check, 5).returncode == 0
        if not existing:
            forward = f"127.0.0.1:{port}:127.0.0.1:8443"
            command = ["ssh", "-f", "-N", "-M", "-S", str(control),
                       "-L", forward, "-o", "BatchMode=yes",
                       "-o", "StrictHostKeyChecking=accept-new",
                       "-o", "ExitOnForwardFailure=yes",
                       "-o", "ConnectTimeout=6",
                       "-o", "ServerAliveInterval=30",
                       "-o", "ServerAliveCountMax=3", "-l", user, host]
            result = checked_run(command, 12)
            if result.returncode != 0:
                print("Admin tunnel failed. Check Tailscale, SSH pairing and server address.", file=sys.stderr)
                if result.stderr:
                    print(result.stderr.strip()[:500], file=sys.stderr)
                return 1
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
        subprocess.Popen(["xdg-open", f"https://127.0.0.1:{port}/admin"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Unable to open admin tunnel: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: open-web-gaming-admin HOST SSH_USER", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(open_admin(sys.argv[1], sys.argv[2], Path.home()))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
