"""Narrow host-operator pilot for the existing owner Steam lobby transaction.

No listener, daemon, remote-client authentication, Moonlight stream launch or
automatic retry. The operator must hold local host/Docker administrative rights.
The inspect path is read-only. All session IDs and Wolf payloads stay private.
"""
from owner_access import (OwnerStore, PolicyError, approve_device, new_owner,
                          paired_client_ids, resolve_games, _valid_client_id)
from owner_lobby import plan_owner_steam_lobby, _inventory
from owner_launch import launch_owner_steam


def inspect_candidate(wolf_api, *, profile_id="user", video_caps=None):
    """Verify a single live Wolf UI owner stream against actual host inventories.

    Return a redacted report plus private, in-memory binding for local operators.
    No writes to Wolf, disk, or Steam are performed.
    """
    if not callable(wolf_api):
        raise PolicyError("Missing host-local Wolf API")
    clients = wolf_api("GET", "/api/v1/clients")
    profiles = wolf_api("GET", "/api/v1/profiles")
    apps = wolf_api("GET", "/api/v1/apps")
    sessions = wolf_api("GET", "/api/v1/sessions")
    lobbies = wolf_api("GET", "/api/v1/lobbies")

    # Validate all identities before choosing the live device. Duplicate
    # entries with conflicting storage folders must fail closed.
    known = paired_client_ids(clients)
    live = _inventory(sessions, "sessions", 256)
    if len(live) != 1:
        raise PolicyError("Exactly one active Wolf UI stream is required")
    ids = [a.get("id") for a in _inventory(apps, "apps", 256)
           if a.get("title") == "Wolf UI"]
    if len(ids) != 1 or not isinstance(ids[0], str) or not ids[0]:
        raise PolicyError("Wolf UI application is not uniquely identifiable")
    session = live[0]
    client_id = session.get("client_id")
    if not _valid_client_id(client_id) or client_id not in known:
        raise PolicyError("Active session has no valid paired identity")
    if session.get("app_id") != ids[0]:
        raise PolicyError("Active session is not Wolf UI")
    matching = [c for c in clients["clients"] if c.get("client_id") == client_id]
    if len(matching) != 1:
        raise PolicyError("Active paired client has duplicate records")
    if _inventory(lobbies, "lobbies", 256):
        raise PolicyError("Existing Wolf lobby prevents a safe pilot")

    # Use actual owner policy / lobby planner, not a second approximate schema
    # check. The in-memory policy and launch plan are never printed or saved.
    temporary_policy = new_owner(profile_id, profiles)
    approve_device(temporary_policy, client_id, clients)
    plan_owner_steam_lobby(temporary_policy, client_id, clients, profiles,
                           apps, sessions, lobbies, video_caps=video_caps)
    report = {
        "success": True,
        "ready_for_operator_enrollment": True,
        "named_profile": profile_id,
        "active_wolf_ui_sessions": 1,
        "matched_paired_client_records": 1,
        "existing_lobbies": 0,
        "steam_runner_validated": True,
        "steam_launch_performed": False,
        "remote_client_authentication_implemented": False,
    }
    return report, client_id, clients, profiles


def enroll_current_owner(wolf_api, store, *, profile_id="user",
                         confirmed_owner=False, confirmed_device=False,
                         video_caps=None):
    """Explicit local operator adoption of one active Moonlight Wolf UI device."""
    if not confirmed_owner or not confirmed_device:
        raise PolicyError("Explicit existing-owner and paired-device consent required")
    report, client_id, clients, profiles = inspect_candidate(
        wolf_api, profile_id=profile_id, video_caps=video_caps)
    policy = new_owner(profile_id, profiles)
    approve_device(policy, client_id, clients)
    with store.locked() as fd:
        if store.read(fd) is not None:
            raise PolicyError("Owner policy already exists; refusing overwrite")
        store.write(fd, policy)
    return {**report, "owner_policy_enrolled": True}


def launch_enrolled_owner(wolf_api, store, *, profile_id="user",
                          confirmed_live_steam=False,
                          confirmed_no_other_steam_writer=False,
                          confirmed_legacy_links_reviewed=False,
                          video_caps=None):
    """Host operator only. Creates/joins a real lobby, never a remote handler."""
    if not all((confirmed_live_steam, confirmed_no_other_steam_writer,
                confirmed_legacy_links_reviewed)):
        raise PolicyError("Live Steam, writer isolation and legacy-link review consent required")
    _, client_id, clients, _ = inspect_candidate(
        wolf_api, profile_id=profile_id, video_caps=video_caps)
    with store.locked() as fd:
        data = store.read(fd)
        if data is None:
            raise PolicyError("Owner policy not enrolled")
        grant = resolve_games(data, client_id, clients)
        if grant["wolf_profile_id"] != profile_id:
            raise PolicyError("Requested profile differs from enrolled owner")
    # Re-check authorization and inventories inside durable lease transaction.
    # No remote request can select client_id, named profile, runner or Steam data.
    return launch_owner_steam(client_id, wolf_api, store=store,
                              execution_approved=True, video_caps=video_caps)
