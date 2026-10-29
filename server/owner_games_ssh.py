#!/usr/bin/env python3
"""Restricted, per-SSH-key Games command, not a generic remote shell.

ONLY install as an OpenSSH authorized_keys forced command with "restrict" and
a host-operator-pinned --client-id. The host account running it needs narrowly
reviewed Wolf access; using an existing Docker-admin account is a *temporary*
owner-only reference-host bridge, not a multi-user isolation model.

This module does not provision keys, enable a listener, or change host state
unless the explicitly approved 'start'/'stop' action is received. The caller
must independently confirm the public key belongs to the same Moonlight client
ID when installing the authorized_keys line.
"""
import argparse
import json
import os
from pathlib import Path
import re
import select
import stat
import subprocess
import sys
import time

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from owner_access import OwnerStore, PolicyError, _valid_client_id
from owner_games_request import handle_owner_games_request
from wolf_docker_adapter import WolfDockerAPI

CONFIG_PATH = Path.home() / ".config/optiplex-now/owner-games-host.json"
MAX_INPUT = 2048  # Bounded owner requests, including approved magnet URLs; no shell
MAX_CONFIG = 2048
VIDEO_CAPS = frozenset(("video/x-raw", "video/x-raw(memory:CUDAMemory)"))
STEAM_NAME = re.compile(r"^(steam|steamwebhelper|wineserver|wine|proton|pressure-vessel|re2(\.exe)?$)", re.I)
STEAM_CONTAINER = re.compile(r"(WolfSteam|(^|[-_])Steam([-_]|$))", re.I)


def _read_private_config(path=CONFIG_PATH):
    """Only a local owner can select the workspace, video caps and enablement."""
    directory = Path(path).parent
    if directory.is_symlink() or not directory.is_dir():
        raise PolicyError("Owner Games configuration directory is unsafe")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or info.st_size > MAX_CONFIG):
            raise PolicyError("Owner Games configuration permissions are unsafe")
        raw = os.read(fd, MAX_CONFIG + 1)
    finally:
        os.close(fd)
    if len(raw) > MAX_CONFIG:
        raise PolicyError("Owner Games configuration is oversized")
    try:
        config = json.loads(raw)
    except (UnicodeDecodeError, ValueError):
        raise PolicyError("Owner Games configuration is malformed") from None
    if (not isinstance(config, dict) or
            set(config) != {"version", "state_dir", "video_caps", "enabled",
                            "legacy_links_reviewed"}
            or type(config["version"]) is not int or config["version"] != 1
            or type(config["enabled"]) is not bool
            or type(config["legacy_links_reviewed"]) is not bool
            or not isinstance(config["video_caps"], str)
            or config["video_caps"] not in VIDEO_CAPS
            or not isinstance(config["state_dir"], str)
            or not config["state_dir"].startswith("/")
            or not 1 <= len(config["state_dir"]) <= 1024):
        raise PolicyError("Invalid host Games configuration")
    return config


def _request_line(stdin_fd=0, deadline_seconds=6, *, clock=time.monotonic):
    """Read a single bounded JSON line without indefinitely waiting for EOF."""
    end = clock() + deadline_seconds
    data = bytearray()
    while b"\n" not in data:
        remaining = end - clock()
        if remaining <= 0:
            raise PolicyError("Games request timed out")
        readable, _, _ = select.select([stdin_fd], [], [], remaining)
        if not readable:
            raise PolicyError("Games request timed out")
        chunk = os.read(stdin_fd, MAX_INPUT + 1 - len(data))
        if not chunk:
            raise PolicyError("Games request ended unexpectedly")
        data.extend(chunk)
        if len(data) > MAX_INPUT:
            raise PolicyError("Games request exceeds limit")
    first, _, extra = bytes(data).partition(b"\n")
    if extra:
        raise PolicyError("Multiple commands are not permitted")
    try:
        return json.loads(first.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise PolicyError("Invalid Games request") from None


def _capture(argv, *, timeout):
    result = subprocess.run(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    if (result.returncode != 0 or not isinstance(result.stdout, bytes)
            or len(result.stdout) > 65536):
        raise PolicyError("Cannot verify other active Steam writers")
    return result.stdout.decode("utf-8", errors="replace")


def host_writer_preflight():
    """Fail closed on other Steam processes or Wolf Steam containers.

    This cannot prevent a separately privileged Wolf UI/direct Steam actor from
    racing us after inspection. Hosts with legacy linked Steam folders remain
    an owner-only alpha configuration until upstream admission is restricted.
    """
    ps = _capture(["ps", "-eo", "comm="], timeout=5)
    if any(STEAM_NAME.search(line) for line in ps.splitlines()):
        return False
    names = _capture(["docker", "ps", "--format", "{{.Names}}"], timeout=7)
    if any(STEAM_CONTAINER.search(name) for name in names.splitlines()):
        return False
    return True


def execute(*, verified_client_id, environ=None, read_request=_request_line,
            read_config=_read_private_config, wolf_api_factory=WolfDockerAPI,
            writer_check=host_writer_preflight):
    env = os.environ if environ is None else environ
    # An actual forced-key SSH session has a server-owned SSH_CONNECTION and
    # no remote command. Reject arbitrary SSH exec and forwarding attempts.
    # This check supplements authorized_keys "restrict,command=...", NOT
    # an authentication mechanism by itself.
    if not env.get("SSH_CONNECTION") or env.get("SSH_ORIGINAL_COMMAND", ""):
        raise PolicyError("Restricted owner Games SSH session required")
    if not _valid_client_id(verified_client_id):
        raise PolicyError("No verified Games device binding")
    request = read_request()
    config = read_config()
    def emit(snapshot):
        # Each JSON line is bounded and contains only sanitized search fields.
        print(json.dumps(snapshot, ensure_ascii=True, separators=(",", ":")),
              flush=True)
    kwargs={}
    if isinstance(request, dict) and request.get("stream") is True:
        kwargs["search_emitter"]=emit
    return handle_owner_games_request(
        request, verified_client_id=verified_client_id,
        store=OwnerStore(config["state_dir"]), wolf_api=wolf_api_factory(),
        host_video_caps=config["video_caps"],
        host_approved=(config["enabled"] is True and
                       config["legacy_links_reviewed"] is True),
        host_writer_check=writer_check, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", required=True)
    args = parser.parse_args(argv)
    try:
        result = execute(verified_client_id=args.client_id)
        if result is not None:
            print(json.dumps(result, sort_keys=True))
        return 0
    except (PolicyError, OSError, ValueError, subprocess.TimeoutExpired):
        # Errors can reveal host usernames, Steam state, private PINs, runner
        # definitions or SSH internals. Never send raw upstream errors.
        print('{"success":false,"status":"denied"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
