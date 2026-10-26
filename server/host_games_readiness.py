#!/usr/bin/env python3
"""Read-only Wolf first-Games readiness inspection for NOW-managed clean hosts.

No Wolf config edits, Steam profile synthesis, Docker operations or pairing.
This distinguishes upstream config v2 named profiles from newer v3 global
apps/per-client app_state_folder semantics. Neither counts as a game stream.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import tomllib

MAX_CONFIG_BYTES = 512 * 1024


def _report(state: str, *, schema: int | None = None,
            steam_app: bool = False, owner_profile: bool = False,
            steam_home_present: bool = False) -> dict:
    return {
        "state": state, "wolf_config_version": schema,
        "steam_app_configured": steam_app,
        "named_owner_profile_found": owner_profile,
        "owner_steam_home_present": steam_home_present,
        "first_game_verified": False,
        "steam_login_verified": False,
        "video_audio_controller_verified": False,
        "client_enrollment_verified": False,
    }


def inspect_config(wolf_root: Path) -> dict:
    """Inspect only explicitly identified local Wolf state, never expose secrets.

    A named profile is only a *candidate*. Existing files are not proof of an
    authenticated Steam account or a functioning session.
    """
    wolf_root = Path(wolf_root)
    config = wolf_root / "cfg" / "config.toml"
    try:
        metadata = config.lstat()
    except FileNotFoundError:
        return _report("wolf_config_pending")
    except OSError:
        return _report("wolf_config_unreadable")
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_CONFIG_BYTES:
        return _report("wolf_config_unsafe_or_oversized")
    try:
        # lstat rejects the leaf symlink. The caller supplies a trusted local
        # NOW-owned root, never a client-selected path or remote filesystem.
        data = config.read_bytes()
        if len(data) > MAX_CONFIG_BYTES:
            return _report("wolf_config_unsafe_or_oversized")
        parsed = tomllib.loads(data.decode("utf-8"))
    except (OSError, ValueError, UnicodeError, tomllib.TOMLDecodeError):
        return _report("wolf_config_invalid")
    if not isinstance(parsed, dict):
        return _report("wolf_config_invalid")
    version = parsed.get("config_version")
    if type(version) is not int or version not in (2, 3):
        return _report("wolf_config_version_unsupported")

    if version == 3:
        apps = parsed.get("apps")
        if not isinstance(apps, list):
            return _report("wolf_config_invalid", schema=3)
        steam = any(isinstance(app, dict) and app.get("title") == "Steam"
                    and isinstance(app.get("runner"), dict)
                    and app["runner"].get("type") == "docker"
                    for app in apps)
        # Upstream v3 associates app_state_folder with each paired client.
        # We cannot promise one persistent owner Steam profile on this schema.
        return _report("v3_per_device_state_requires_owner_mapping" if steam
                       else "steam_app_missing", schema=3, steam_app=steam)

    profiles = parsed.get("profiles")
    if not isinstance(profiles, list):
        return _report("wolf_config_invalid", schema=2)
    matching = [p for p in profiles if isinstance(p, dict) and p.get("id") == "user"]
    if len(matching) != 1:
        return _report("named_owner_profile_missing_or_ambiguous", schema=2)
    owner = matching[0]
    apps = owner.get("apps")
    if not isinstance(apps, list):
        return _report("steam_app_missing", schema=2, owner_profile=True)
    steam = any(isinstance(app, dict) and app.get("title") == "Steam"
                and isinstance(app.get("runner"), dict)
                and app["runner"].get("type") == "docker"
                for app in apps)
    if not steam:
        return _report("steam_app_missing", schema=2, owner_profile=True)
    home = wolf_root / "profile_data" / "user" / "Steam"
    # An empty home is still not a logged-in session. Never create/chown it.
    try:
        present = stat.S_ISDIR(home.lstat().st_mode)
    except OSError:
        present = False
    return _report("named_steam_candidate", schema=2, steam_app=True,
                   owner_profile=True, steam_home_present=present)


def main() -> int:
    parser = argparse.ArgumentParser(description="NOW read-only local Games inspection")
    parser.add_argument("--wolf-root", type=Path,
                        default=Path("/var/lib/optiplex-now/host/wolf"))
    args = parser.parse_args()
    print(json.dumps(inspect_config(args.wolf_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
