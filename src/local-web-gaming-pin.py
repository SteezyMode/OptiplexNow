#!/usr/bin/env python3
"""Issue a MoonlightWeb browser access PIN on the LOCAL owner machine only.

Intentionally not a network listener, SSH tunnel, root broker or remote admin
endpoint. Uses the upstream non-revoking --new-pin CLI through the local
Docker socket only, with the caller's existing Docker authorization.
The PIN goes only to the GUI's stdout pipe; no stderr, logging, URL or argv.
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys

SOCKET = "/var/run/docker.sock"
STATUS = "NOW_OWNER_STATUS="
PIN_LINE = re.compile(r"(?<![0-9])([0-9]{6})(?![0-9])")


def parse_pin(output: str) -> str | None:
    # Upstream prints either a standalone code or a labelled access PIN.
    if not isinstance(output, str) or len(output) > 4096:
        return None
    for line in output.splitlines():
        cleaned = line.strip()
        if PIN_LINE.fullmatch(cleaned):
            return cleaned
        if not re.search(r"\b(?:access\s+)?pin\b", cleaned, re.I):
            continue
        found = PIN_LINE.findall(cleaned)
        if len(found) == 1:
            return found[0]
    return None


def issue_pin(*, which=shutil.which, runner=subprocess.run,
              socket_path=SOCKET) -> tuple[int, str]:
    # Do not honor DOCKER_HOST, DOCKER_CONTEXT, or remote Docker credentials.
    # CLI --host explicitly pins every invocation to this local UNIX socket.
    if not os.path.exists(socket_path):
        return 1, "not_local_server"
    import stat
    if not stat.S_ISSOCK(os.stat(socket_path).st_mode):
        return 1, "not_local_server"
    docker = which("docker")
    if not docker:
        return 1, "docker_missing"
    base = [docker, "--host", f"unix://{socket_path}"]
    try:
        inspect = runner(
            base + ["inspect", "--type", "container",
                    "--format", "{{.State.Running}}", "moonlightweb"],
            capture_output=True, text=True, timeout=5, check=False)
        if inspect.returncode != 0:
            msg = (inspect.stderr or "").lower()
            if "permission denied" in msg:
                return 1, "docker_permission_denied"
            return 1, "moonlightweb_not_found"
        if inspect.stdout.strip() != "true":
            return 1, "moonlightweb_not_running"
        new = runner(base + ["exec", "moonlightweb", "moonlightweb", "--new-pin"],
                     capture_output=True, text=True, timeout=12, check=False)
        if new.returncode != 0:
            return 1, "pin_issuance_failed"
        pin = parse_pin(new.stdout)
        if not pin:
            return 1, "pin_output_unrecognized"
        return 0, f"pin:{pin}"
    except subprocess.TimeoutExpired:
        return 1, "docker_timeout"
    except (OSError, ValueError):
        return 1, "docker_unavailable"


def main() -> int:
    try:
        rc, state = issue_pin()
    except Exception:
        # No tracebacks or unfiltered upstream data in desktop application logs.
        rc, state = 1, "docker_unavailable"
    print(STATUS + state, flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
