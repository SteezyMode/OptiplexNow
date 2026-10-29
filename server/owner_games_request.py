"""Host-side owner Games request gate, source-only; no remote listener.

A future trusted transport supplies an authenticated Wolf device identity, NOT
anything from the request. This module deliberately does not accept user
selected profile IDs, Steam paths, PINs, client IDs, or video caps.

It does not authenticate SSH/Tailscale/Moonlight requests itself. Do NOT expose
this function as a web endpoint, generic SSH command or client-side import
until the caller performs independently verified device authentication.
"""
from owner_access import OwnerStore, PolicyError, _valid_client_id, resolve_games
from owner_launch import (read_lease, launch_owner_steam, stop_owner_steam,
                          reconcile_finished_owner_steam, cleanup_finished_owner_wolf_ui)
from owner_lobby import _inventory
from owner_host_pilot import inspect_candidate
from media_endpoint import inspect_local_jellyfin
from download_inventory import inspect_download_topology, InventoryError
from download_queue import inspect_queue
from download_search import search_once, checked_query

VERSION = 1
ACTIONS = frozenset(("status", "start", "stop", "reconcile", "observe", "cleanup", "media", "downloads_status", "downloads_queue", "downloads_search"))


def _validated_request(request):
    if not isinstance(request, dict):
        raise PolicyError("Unsupported owner Games request")
    action = request.get("action")
    fields = {"version", "action", "query"} if action == "downloads_search" else {"version", "action"}
    if (set(request) != fields
            or type(request.get("version")) is not int or request["version"] != VERSION
            or not isinstance(action, str) or action not in ACTIONS):
        raise PolicyError("Unsupported owner Games request")
    if action == "downloads_search":
        try:
            checked_query(request["query"])
        except InventoryError:
            raise PolicyError("Invalid download search") from None
    return action


def handle_owner_games_request(request, *, verified_client_id, store, wolf_api,
                               host_video_caps=None, host_approved=False,
                               host_writer_check=None):
    """Handle one narrow request from a *separately authenticated* host caller.

    verified_client_id MUST be bound to the requesting credential by trusted
    host configuration. The request cannot select or impersonate it.

    host_approved and host_video_caps are host configuration, NOT fields the
    remote client can send. host_writer_check is a privileged, host-side
    preflight callback that MUST re-evaluate Steam processes and legacy
    writable profile aliases on every start; client booleans are never trusted.
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

    if action == "downloads_search":
        try:
            # Only enabled, pre-existing qBittorrent plugins. No add/delete,
            # custom endpoint, file path or plugin install accepted.
            return {"success": True, "service": "qbittorrent",
                    **search_once(request["query"])}
        except InventoryError:
            return {"success": False, "status": "search_unavailable"}

    if action == "downloads_queue":
        try:
            return {"success": True, **inspect_queue()}
        except InventoryError:
            return {"success": False, "status": "queue_unavailable"}

    if action == "downloads_status":
        try:
            return {"success": True, **inspect_download_topology()}
        except InventoryError:
            return {"success": False, "status": "inventory_unavailable"}

    if action == "media":
        return {"success": True, **inspect_local_jellyfin()}

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

    if action == "observe":
        # Read-only observation after a successful managed Start. No automatic
        # StopLobby and no lease deletion. Distinguish Steam runner exit from
        # the still-running Wolf UI Moonlight session.
        if lease is None or lease["state"] != "joined" or not lease["lobby_id"]:
            raise PolicyError("No confirmed owner Games session to observe")
        if lease["client_id"] != verified_client_id:
            raise PolicyError("Owner Games session belongs to another device")
        lobbies = _inventory(wolf_api("GET", "/api/v1/lobbies"), "lobbies", 256)
        if lobbies:
            if len(lobbies) != 1:
                raise PolicyError("Unexpected concurrent Wolf lobby")
            lobby = lobbies[0]
            if (lobby.get("id") != lease["lobby_id"] or
                    lobby.get("name") != "Steam" or
                    lobby.get("started_by_profile_id") != profile_id or
                    lobby.get("pin_required") is not True or
                    lobby.get("multi_user") is not False or
                    not isinstance(lobby.get("connected_sessions"), list) or
                    any(c != verified_client_id
                        for c in lobby["connected_sessions"])):
                raise PolicyError("Observed lobby differs from owner Steam")
            return {"success": True, "status": "running"}
        # Wolf's runner-exit StopLobby returns its stream producer to Wolf UI
        # rather than necessarily closing Moonlight. Verify only this bound
        # client remains, and no Steam writer exists. Otherwise fail closed.
        sessions = _inventory(wolf_api("GET", "/api/v1/sessions"), "sessions", 256)
        if len(sessions) > 1 or any(
                item.get("client_id") != verified_client_id for item in sessions):
            raise PolicyError("Another Wolf session remains active")
        if sessions:
            apps = _inventory(wolf_api("GET", "/api/v1/apps"), "apps", 256)
            wolf_ui = [a.get("id") for a in apps if a.get("title") == "Wolf UI"]
            if len(wolf_ui) != 1 or sessions[0].get("app_id") != wolf_ui[0]:
                raise PolicyError("Unexpected Wolf stream after owner Steam")
        if not callable(host_writer_check):
            raise PolicyError("Host Steam writer observation unavailable")
        try:
            if host_writer_check() is not True:
                return {"success": True, "status": "running"}
        except Exception:
            raise PolicyError("Host Steam writer observation failed") from None
        # Lease identity may have changed while the Wolf GETs ran. Read again
        # under the same owner lock; only the original joined transaction may
        # be described as finished. Still do not archive or stop anything.
        with store.locked() as fd:
            current = read_lease(fd)
            if (current is None or current["id"] != lease["id"] or
                    current["state"] != "joined" or
                    current["client_id"] != verified_client_id):
                raise PolicyError("Owner Steam lease changed while observing")
        # The actual reconciliation still requires zero Wolf sessions after
        # the client's OWN Moonlight process exits.
        return {"success": True, "status": "finished"}

    if action == "cleanup":
        return cleanup_finished_owner_wolf_ui(
            wolf_api, store=store, expected_client_id=verified_client_id,
            host_writer_check=host_writer_check)

    if action == "reconcile":
        # This is NOT a forced stop or a blind lease clear. It only archives a
        # joined lease belonging to this credential if the entire Wolf runtime
        # and Steam writer census are definitively idle. Otherwise it refuses.
        return reconcile_finished_owner_steam(
            wolf_api, store=store,
            expected_client_id=verified_client_id,
            host_writer_check=host_writer_check)

    if action == "start":
        if lease is not None:
            raise PolicyError("Owner Steam already has a blocking lease")
        # Inspect the actual active Moonlight session, never a client-claimed
        # identity. Requires exactly one Wolf UI session and zero lobbies.
        _, live_client, _, _ = inspect_candidate(
            wolf_api, profile_id=profile_id, video_caps=host_video_caps)
        if live_client != verified_client_id:
            raise PolicyError("Wolf UI session belongs to another device")
        if not callable(host_writer_check):
            raise PolicyError("Host Steam writer preflight is unavailable")
        try:
            writer_clear = host_writer_check()
        except Exception:
            raise PolicyError("Host Steam writer preflight failed") from None
        if writer_clear is not True:
            raise PolicyError("Host Steam writer isolation is not verified")
        # The underlying owner transaction re-checks grant and Wolf state
        # under the persisted lease lock immediately before its single POST.
        return launch_owner_steam(
            verified_client_id, wolf_api, store=store, execution_approved=True,
            video_caps=host_video_caps)

    if lease is None or lease["client_id"] != verified_client_id:
        raise PolicyError("Cannot stop another owner's Steam session")
    return stop_owner_steam(wolf_api, store=store, confirmed_stop=True,
                            expected_client_id=verified_client_id,
                            expected_lease_id=lease["id"])
