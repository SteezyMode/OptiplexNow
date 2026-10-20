#!/usr/bin/env python3
"""Open the existing MoonlightWeb owner admin UI over a client-side SSH tunnel.

This is an advanced owner-only action, NOT a routine gaming pairing mechanism.
Emit fixed, non-sensitive machine-readable statuses so NOW's GTK GUI can
truthfully report failures. Never log SSH stderr, credentials or browser URLs.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

STATUS_PREFIX = "NOW_ADMIN_STATUS="


def report(status: str) -> None:
    # Only fixed codes, never tunnel destinations, tokens or stderr contents.
    print(STATUS_PREFIX + status, flush=True)


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
    return subprocess.run(argv, capture_output=True, text=True,
                          timeout=seconds, check=False)


def ssh_failure(stderr: str) -> str:
    # Do not pass arbitrary remote stderr back to the GUI.
    reason = (stderr or "").lower()
    if "permission denied" in reason or "host key verification failed" in reason:
        return "ssh_not_authorized"
    if "address already in use" in reason or "bind " in reason:
        return "local_port_unavailable"
    if "could not resolve hostname" in reason or "name or service not known" in reason:
        return "server_name_invalid"
    if ("connection refused" in reason or "no route to host" in reason
            or "connection timed out" in reason or "network is unreachable" in reason):
        return "server_unreachable"
    return "ssh_tunnel_failed"


def open_admin(host: str, user: str, home: Path) -> int:
    try:
        control, port = tunnel_settings(host, user, home)
    except ValueError:
        report("invalid_settings")
        return 2
    except OSError:
        report("local_configuration_error")
        return 1

    if not shutil.which("ssh"):
        report("ssh_not_installed")
        return 1

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
            response = checked_run(command, 12)
            if response.returncode != 0:
                report(ssh_failure(response.stderr))
                return 1
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                pass
        except OSError:
            report("admin_tunnel_unreachable")
            return 1

        opener = shutil.which("xdg-open")
        if not opener:
            report("browser_not_installed")
            return 1
        browser = subprocess.Popen(
            [opener, f"https://127.0.0.1:{port}/admin"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            result = browser.wait(timeout=2)
            if result != 0:
                report("browser_launch_failed")
                return 1
        except subprocess.TimeoutExpired:
            # Some launchers continue running as long as their browser stays open.
            pass
        # This is only a browser handoff, NOT evidence that the page loaded,
        # TLS was trusted, or a user completed authentication.
        report("browser_handoff_requested")
        return 0
    except subprocess.TimeoutExpired:
        report("ssh_tunnel_timeout")
        return 1
    except OSError:
        report("admin_launch_error")
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        report("invalid_settings")
        sys.exit(2)
    sys.exit(open_admin(sys.argv[1], sys.argv[2], Path.home()))
