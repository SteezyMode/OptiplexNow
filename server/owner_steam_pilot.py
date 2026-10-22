#!/usr/bin/env python3
"""Host-local operator pilot: inspect, enroll, or explicitly launch Steam.

NOT installed or invoked by NOW Games. Does not authenticate remote devices,
replace Wolf UI, isolate native Wolf apps, or remove legacy Steam symlinks.
Use only from a trusted host admin shell; there is no server or SSH listener.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from owner_access import OwnerStore, PolicyError
from owner_host_pilot import (inspect_candidate, enroll_current_owner,
                              launch_enrolled_owner)
from wolf_docker_adapter import WolfDockerAPI


def run(args, *, api=None):
    api = api or WolfDockerAPI()
    if args.action == "inspect":
        result, _, _, _ = inspect_candidate(api, profile_id=args.profile)
        return result
    if not args.state_dir:
        raise PolicyError("State directory is mandatory for operator changes")
    if not Path(args.state_dir).is_absolute():
        raise PolicyError("Owner state directory must be an absolute path")
    store = OwnerStore(args.state_dir)
    if args.action == "enroll":
        return enroll_current_owner(
            api, store, profile_id=args.profile,
            confirmed_owner=args.confirm_existing_owner,
            confirmed_device=args.confirm_owner_device)
    if args.action == "launch":
        return launch_enrolled_owner(
            api, store, profile_id=args.profile,
            confirmed_live_steam=args.confirm_live_steam,
            confirmed_no_other_steam_writer=args.confirm_no_other_steam_writer,
            confirmed_legacy_links_reviewed=args.confirm_legacy_links_reviewed)
    raise PolicyError("Unsupported operator action")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("inspect", "enroll", "launch"):
        cmd = sub.add_parser(action)
        cmd.add_argument("--profile", default="user",
                         help="Existing named Steam profile (default: user)")
        cmd.add_argument("--state-dir",
                         help="Explicit absolute private state directory for enroll/launch")
        if action == "enroll":
            cmd.add_argument("--confirm-existing-owner", action="store_true")
            cmd.add_argument("--confirm-owner-device", action="store_true")
        if action == "launch":
            cmd.add_argument("--confirm-live-steam", action="store_true")
            cmd.add_argument("--confirm-no-other-steam-writer", action="store_true")
            cmd.add_argument("--confirm-legacy-links-reviewed", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args), sort_keys=True))
        return 0
    except PolicyError as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        return 1
    except (OSError, RuntimeError, ValueError) as exc:
        # No raw upstream Wolf, Docker or Steam payloads in operator output.
        print(json.dumps({"success": False, "error": "Host-local Wolf operation unavailable",
                          "kind": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
