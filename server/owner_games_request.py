"""Host-side owner Games request gate, source-only; no remote listener.

A future trusted transport supplies an authenticated Wolf device identity, NOT
anything from the request. This module deliberately does not accept user
selected profile IDs, Steam paths, PINs, client IDs, or video caps.

It does not authenticate SSH/Tailscale/Moonlight requests itself. Do NOT expose
this function as a web endpoint, generic SSH command or client-side import
until the caller performs independently verified device authentication.
"""
from owner_access import OwnerStore, PolicyError, _valid_client_id, resolve_games
from owner_launch import read_lease, launch_owner_steam, stop_owner_steam
from owner_lobby import _inventory
from owner_host_pilot import inspect_candidate

VERSION = 1
ACTIONS = frozenset(("status", "start", "stop"))


def _validated_request(request):
    if (not isinstance(request, dict) or set(request) != {"version", "action"}
            or type(request["version"]) is not int or request["version"] != VERSION
            or not isinstance(request["action"], str) or request["action"] not in ACTIONS):
        raise PolicyError("Unsupported owner Games request")
    return request["action"]


def handle_owner_games_request(request, *, verified_client_id, store, wolf_api,
                               host_video_caps=None, host_approved=False):
    """Handle one narrow request from a *separately authenticated* host caller.

    verified_client_id MUST be bound to the requesting credential by trusted
    host configuration. The request cannot select or impersonate it.

    host_approved and host_video_caps are host configuration, NOT fields the
    remote client can send. Legacy writable profile aliases and other Steam
    writers MUST be reviewed before enabling a production start operation.
    """
    action = _validated_request(request)
    if not _valid_client_id(verified_client_id):
        raise PolicyError("Invalid host-authenticated owner Games device")
    if not isinstance(store, OwnerStore) or not callable(wolf_api):
        raise PolicyError("Trusted host Games authority unavailable")

    # Resolve device entitlement server-side before exposing status or making
    # any state-changing API call. The lease and policy use the same state lock.
    with store.locked() as fd:
        policy = store.read(fd)
        if policy is None:
            raise PolicyError("Owner Games policy is not initialized")
        paired = wolf_api("GET", "/api/v1/clients")
        binding = resolve_games(policy, verified_client_id, paired)
        lease = read_lease(fd)
        profile_id = binding["wolf_profile_id"]
        if lease is not None and lease["workspace_id"] != binding["workspace_id"]:
            raise PolicyError("Owner Steam lease/workspace mismatch")

    if action == "status":
        if lease is not None:
            return {"success": True, "status": "in_use",
                    "same_device": lease["client_id"] == verified_client_id,
                    "manual_review_required": True}
        # Never describe an unrelated live Wolf UI or game session as idle.
        sessions = _inventory(wolf_api("GET", "/api/v1/sessions"), "sessions", 256)
        lobbies = _inventory(wolf_api("GET", "/api/v1/lobbies"), "lobbies", 256)
        if lobbies or len(sessions) > 1:
            return {"success": True, "status": "busy"}
        if not sessions or sessions[0].get("client_id") != verified_client_id:
            return {"success": True, "status": "needs_wolf_ui"}
        apps = _inventory(wolf_api("GET", "/api/v1/apps"), "apps", 256)
        wolf_ui = [item.get("id") for item in apps if item.get("title") == "Wolf UI"]
        if (len(wolf_ui) != 1 or not isinstance(wolf_ui[0], str)
                or not wolf_ui[0] or sessions[0].get("app_id") != wolf_ui[0]):
            return {"success": True, "status": "needs_wolf_ui"}
        return {"success": True, "status": "wolf_ui_connected"}

    # Host-only deployment switch, never a field of the request.
    if host_approved is not True:
        raise PolicyError("Host has not enabled owner Games control")

    if action == "start":
        if lease is not None:
            raise PolicyError("Owner Steam already has a blocking lease")
        # Inspect the actual active Moonlight session, never a client-claimed
        # identity. Requires exactly one Wolf UI session and zero lobbies.
        _, live_client, _, _ = inspect_candidate(
            wolf_api, profile_id=profile_id, video_caps=host_video_caps)
        if live_client != verified_client_id:
            raise PolicyError("Wolf UI session belongs to another device")
        # The underlying owner transaction re-checks grant and Wolf state
        # under the persisted lease lock immediately before its single POST.
        return launch_owner_steam(
            verified_client_id, wolf_api, store=store, execution_approved=True,
            video_caps=host_video_caps)

    if lease is None or lease["client_id"] != verified_client_id:
        raise PolicyError("Cannot stop another owner's Steam session")
    return stop_owner_steam(wolf_api, store=store, confirmed_stop=True)
