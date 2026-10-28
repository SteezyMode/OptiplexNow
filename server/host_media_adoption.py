#!/usr/bin/env python3
"""Existing-Jellyfin owner GUI bridge: bounded local review and opt-in route.

Does not install Jellyfin, change running services, ask for Docker rights,
expose a network listener, or accept a new host address. An existing local
Jellyfin instance must answer NOW's fixed loopback probe. Config is created
exclusively and is never overwritten or deleted by this helper.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

from media_endpoint import (
    _local_urlopen, inspect_local_jellyfin, owner_approved_endpoint,
    validate_owner_endpoint_record,
)

OWNER_CONFIG = Path.home() / ".config/optiplex-now/media-public-endpoint.json"
SCHEMA = 1


def inspect(*, config_path=None, opener=_local_urlopen) -> dict:
    path = Path(config_path) if config_path is not None else OWNER_CONFIG
    try:
        saved = owner_approved_endpoint(path)
    except (OSError, ValueError):
        return {"schema_version": SCHEMA, "status": "unsafe_config",
                "changes_performed": False, "can_approve": False}
    # An existing invalid/unreadable file must never be treated as absent.
    service = inspect_local_jellyfin(opener=opener, endpoint_path=path)
    if not service.get("available") or not service.get("server_id"):
        return {"schema_version": SCHEMA, "status": "not_verified",
                "changes_performed": False, "can_approve": False}
    return {
        "schema_version": SCHEMA,
        "status": "already_configured" if saved is not None else "local_jellyfin_found",
        "changes_performed": False, "can_approve": saved is None,
        "server_name": service.get("name", "Jellyfin"),
        # Do not copy server ID or passwords into owner-facing diagnostics.
        "endpoint": saved,
        "note": "Local Jellyfin verified. Client reachability and playback not yet verified.",
    }


def approve_route(scheme: str, port: int, base_path: str, *,
                  config_path=None, opener=_local_urlopen) -> dict:
    """Owner-confirmed first write only. Never adopt, replace or migrate data."""
    if os.geteuid() == 0:
        raise ValueError("Media setup must run as the host owner, not root")
    record = {"version": 1, "scheme": scheme,
              "port": port, "base_path": base_path}
    validate_owner_endpoint_record(record)
    path = Path(config_path) if config_path is not None else OWNER_CONFIG
    status = inspect(config_path=path, opener=opener)
    if status["status"] != "local_jellyfin_found":
        raise ValueError("Existing local Jellyfin not verified or route already configured")
    # Only make a private user folder. Never overwrite any unrelated entry.
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    directory = path.parent.lstat()
    if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.geteuid() or (
            stat.S_IMODE(directory.st_mode) & 0o022):
        raise ValueError("Unsafe owner config directory")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW
    dir_fd = os.open(path.parent, flags)
    fd = None
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
        raw = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        offset = 0
        while offset < len(raw):
            n = os.write(fd, raw[offset:])
            if n <= 0:
                raise OSError("Short media route config write")
            offset += n
        os.fsync(fd)
        os.close(fd)
        fd = None
    except BaseException:
        if fd is not None:
            os.close(fd)
            # This helper alone created the O_EXCL entry. Remove a partial
            # write, never an existing file from before our attempt.
            os.unlink(path.name, dir_fd=dir_fd)
        raise
    finally:
        os.close(dir_fd)
    return {"schema_version": SCHEMA, "status": "route_created",
            "changes_performed": True,
            "note": "Only the host-owner routing file was created; client verification pending."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--inspect", action="store_true")
    actions.add_argument("--approve-existing", action="store_true")
    parser.add_argument("--scheme", choices=("http", "https"))
    parser.add_argument("--port", type=int)
    parser.add_argument("--base-path")
    parser.add_argument("--confirm-owner", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.inspect:
            if (args.scheme is not None or args.port is not None or
                    args.base_path is not None or args.confirm_owner):
                raise ValueError("Unexpected options on read-only review")
            result = inspect()
        else:
            if (args.scheme is None or args.port is None or
                    args.base_path is None or not args.confirm_owner):
                raise ValueError("Owner confirmation and complete route required")
            result = approve_route(args.scheme, args.port, args.base_path)
    except (OSError, ValueError):
        print(json.dumps({"schema_version": SCHEMA, "status": "refused",
                          "changes_performed": False, "can_approve": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
