#!/usr/bin/env python3
"""Developer-only local owner enrollment proof, not a remote NOW client API.

Requires the host administrator/root. Does not launch Steam, pair or unpair
Moonlight, restart Wolf, change profiles or copy Steam credentials. A device
still requires upstream Wolf authorization to connect; this file cannot yet
prevent a directly paired client from selecting Wolf apps itself.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys

from owner_access import (
    OwnerStore, PolicyError, approve_device, new_owner, paired_client_ids,
    resolve_games,
)

STATE_DIRECTORY = "/var/lib/optiplex-now"


def _wolf_bridge():
    # Source tree uses .py; existing owner-host installs the same local
    # helper without a suffix. Never attempt to download or execute a
    # remote helper as part of enrollment.
    directory = Path(__file__).resolve().parent
    for name in ("wolf-pair-local.py", "wolf-pair-local"):
        path = directory / name
        if not path.is_file():
            continue
        loader = importlib.machinery.SourceFileLoader("now_local_wolf_bridge", str(path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    raise PolicyError("Local Wolf helper is not installed alongside owner policy")


def run(args, *, store=None, wolf_api=None):
    if os.geteuid() != 0:
        raise PolicyError("Owner policy changes require local host administrator")
    store = store or OwnerStore(STATE_DIRECTORY)
    if wolf_api is None:
        wolf_api = _wolf_bridge().call_api
    if args.action == "initialize":
        if not args.confirm_existing_owner:
            raise PolicyError("Explicit confirmation to adopt existing Steam required")
        profiles = wolf_api("GET", "/api/v1/profiles")
        new = new_owner(args.profile, profiles)
        with store.locked() as fd:
            if store.read(fd) is not None:
                raise PolicyError("Owner policy already initialized; refusing overwrite")
            store.write(fd, new)
        return {"success": True, "owner_initialized": True,
                "wolf_profile_id": new["workspaces"][0]["profile_id"],
                "devices_approved": 0}
    if args.action == "approve-device":
        if not args.confirm_owner_device:
            raise PolicyError("Explicit confirmation of owner's own device required")
        clients = wolf_api("GET", "/api/v1/clients")
        # Validate inventory before mutation and refuse unknown identities.
        if args.client_id not in paired_client_ids(clients):
            raise PolicyError("Device not found among Wolf paired clients")
        with store.locked() as fd:
            data = store.read(fd)
            if data is None:
                raise PolicyError("Initialize the owner policy before approving a device")
            approve_device(data, args.client_id, clients)
            store.write(fd, data)
        return {"success": True, "owner_device_approved": args.client_id,
                "note": "Local policy only; Wolf native app selection is not access-controlled by this file"}
    if args.action == "resolve-games":
        clients = wolf_api("GET", "/api/v1/clients")
        with store.locked() as fd:
            data = store.read(fd)
            if data is None:
                raise PolicyError("Owner policy not initialized")
            binding = resolve_games(data, args.client_id, clients)
        return {"success": True, "authorized": True, **binding,
                "note": "Read-only policy resolution; no Wolf session started"}
    raise PolicyError("Unsupported action")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("initialize", help="Explicitly adopt an existing named Steam profile")
    init.add_argument("--profile", required=True, help="Named Wolf Steam profile ID")
    init.add_argument("--confirm-existing-owner", action="store_true")
    approve = sub.add_parser("approve-device", help="Bind a paired Moonlight device to owner")
    approve.add_argument("--client-id", required=True)
    approve.add_argument("--confirm-owner-device", action="store_true")
    lookup = sub.add_parser("resolve-games", help="Resolve local owner Games permission, read-only")
    lookup.add_argument("--client-id", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args)))
    except (PolicyError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
