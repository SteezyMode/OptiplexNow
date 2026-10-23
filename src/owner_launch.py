"""Host-local owner Steam lobby transaction, NOT exposed to NOW clients.

This module can perform native Wolf lobby POSTs only when explicitly enabled by
a future trusted host-side caller. It does not authenticate the caller. The
caller MUST bind a server-verified device identity, not a client-submitted ID.
Do not enable on a production Wolf host until upstream direct-app bypass,
session IDs, and lease lifecycle have been tested against disposable state.

Lease durability protects only cooperating NOW launches. It is NOT a lock
against the Wolf UI, native Moonlight direct launch, or other administrators.
"""
import json
import os
import stat
import uuid

from owner_access import (OwnerStore, PolicyError, STORE_LIMIT, _valid_client_id, _uuid,
                          resolve_games)
from owner_lobby import plan_owner_steam_lobby, fill_join_lobby, LOBBY_ID, _inventory

LEASE_FILE = "owner-steam-lease.json"
LEASE_VERSION = 2
LEGACY_LEASE_VERSION = 1
LEASE_STATES = frozenset(("creating", "created", "joined", "uncertain"))


def _validate_lease(lease):
    if not isinstance(lease, dict):
        raise PolicyError("Invalid owner Steam lease")
    version = lease.get("version")
    common = {"version", "id", "client_id", "workspace_id", "state", "lobby_id"}
    expected = common | ({"pin"} if version == LEASE_VERSION else set())
    if version not in (LEGACY_LEASE_VERSION, LEASE_VERSION) or set(lease) != expected:
        raise PolicyError("Invalid owner Steam lease")
    if (type(lease["version"]) is not int or
            not _uuid(lease["id"])
            or not _uuid(lease["workspace_id"]) or
            not _valid_client_id(lease["client_id"]) or
            not isinstance(lease["state"], str) or
            lease["state"] not in LEASE_STATES):
        raise PolicyError("Invalid owner Steam lease values")
    lobby_id = lease["lobby_id"]
    if lobby_id is not None and (not isinstance(lobby_id, str) or
                                not LOBBY_ID.fullmatch(lobby_id)):
        raise PolicyError("Invalid owner Steam lease lobby")
    if lease["state"] in ("created", "joined") and lobby_id is None:
        raise PolicyError("Missing created Steam lobby ID")
    if version == LEASE_VERSION:
        pin = lease["pin"]
        if (not isinstance(pin, list) or len(pin) != 8 or
                any(type(digit) is not int or not 0 <= digit <= 9 for digit in pin)):
            raise PolicyError("Invalid private Steam lobby PIN")
    return lease


def _archive_lease(dir_fd, lease):
    """Move the validated blocker to a non-public evidence file under the lock.

    The state directory is owner-only; never return the archived PIN.
    """
    name = "owner-steam-lease.closed-" + lease["id"] + ".json"
    try:
        os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise PolicyError("Owner Steam recovery archive already exists")
    os.rename(LEASE_FILE, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
    os.fsync(dir_fd)


def _require_idle_wolf(wolf_api):
    """Fail closed unless runtime state is definitively empty."""
    lobbies = _inventory(wolf_api("GET", "/api/v1/lobbies"), "lobbies", 256)
    sessions = _inventory(wolf_api("GET", "/api/v1/sessions"), "sessions", 256)
    if lobbies or sessions:
        raise PolicyError("Wolf has active sessions or lobbies; recovery blocked")


def reconcile_stopped_owner_steam(wolf_api, *, store, confirmed_runtime_stopped=False,
                                  confirmed_no_other_steam_writer=False):
    """Operator-only release of an old lease AFTER verified out-of-band stop.

    In particular, v1 lacks the PIN needed to stop a live Wolf lobby. This
    function does NOT stop one, restart Wolf or infer an idle Steam process.
    """
    if not (confirmed_runtime_stopped and confirmed_no_other_steam_writer):
        raise PolicyError("Explicit runtime shutdown and Steam writer review required")
    if not callable(wolf_api):
        raise PolicyError("Missing trusted host-local Wolf API")
    with store.locked() as fd:
        lease = read_lease(fd)
        if lease is None:
            raise PolicyError("No owner Steam lease to reconcile")
        policy = store.read(fd)
        if policy is None or lease["workspace_id"] != policy["workspaces"][0]["id"]:
            raise PolicyError("Owner policy/lease mismatch")
        _require_idle_wolf(wolf_api)
        _archive_lease(fd, lease)
    return {"success": True, "status": "idle", "lease_archived": True}




def cleanup_finished_owner_wolf_ui(wolf_api, *, store,
                                   expected_client_id, host_writer_check):
    """Stop only a provably identified residual owner Wolf UI session.

    A client_id is NOT a session_id. Some Wolf versions omit session_id from
    the session inventory; these must fail closed instead of guessing.
    This is a one-shot mutation: retain the lease if API outcome is uncertain.
    """
    if not _valid_client_id(expected_client_id) or not callable(wolf_api):
        raise PolicyError("Authenticated Games device required")
    if not callable(host_writer_check):
        raise PolicyError("Steam writer verification required")
    with store.locked() as fd:
        lease = read_lease(fd)
        if (lease is None or lease["version"] != LEASE_VERSION or
                lease["state"] != "joined" or lease["client_id"] != expected_client_id):
            raise PolicyError("No owned completed Games lease to clean up")
        policy = store.read(fd)
        if (policy is None or not policy.get("workspaces") or
                lease["workspace_id"] != policy["workspaces"][0]["id"]):
            raise PolicyError("Owner workspace changed")
        lobbies = _inventory(wolf_api("GET", "/api/v1/lobbies"), "lobbies", 256)
        sessions = _inventory(wolf_api("GET", "/api/v1/sessions"), "sessions", 256)
        if lobbies or len(sessions) != 1:
            raise PolicyError("Wolf UI cleanup requires exactly one session and no lobbies")
        session = sessions[0]
        apps = _inventory(wolf_api("GET", "/api/v1/apps"), "apps", 256)
        wolf_ui = [a.get("id") for a in apps if a.get("title") == "Wolf UI"]
        if (len(wolf_ui) != 1 or session.get("app_id") != wolf_ui[0] or
                session.get("client_id") != expected_client_id):
            raise PolicyError("Residual Wolf UI belongs to another stream")
        session_id = session.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise PolicyError("Wolf does not expose a verifiable session_id; cleanup refused")
        if host_writer_check() is not True:
            raise PolicyError("Steam still has an active writer")
        # Fail closed if the same stream is no longer present or has changed.
        again = _inventory(wolf_api("GET", "/api/v1/sessions"), "sessions", 256)
        if len(again) != 1 or again[0] != session or _inventory(
                wolf_api("GET", "/api/v1/lobbies"), "lobbies", 256):
            raise PolicyError("Wolf stream changed before cleanup")
        lease["state"] = "uncertain"
        write_lease(fd, lease)
        try:
            reply = wolf_api("POST", "/api/v1/sessions/stop",
                             {"session_id": session_id})
            if not isinstance(reply, dict) or reply.get("success") is not True:
                raise PolicyError("Wolf session stop not confirmed")
            _require_idle_wolf(wolf_api)
            if host_writer_check() is not True:
                raise PolicyError("Steam writer detected after cleanup")
        except Exception:
            raise PolicyError("Wolf UI cleanup uncertain; manual review required") from None
        _archive_lease(fd, lease)
    return {"success": True, "status": "idle", "lease_archived": True}



def reconcile_finished_owner_steam(wolf_api, *, store,
                                   expected_client_id,
                                   host_writer_check):
    """Archive a previously JOINED owner lease only after observed full exit.

    This is a bounded, non-Wolf-mutating operation for an authenticated owner
    device. It does not stop Wolf, stop Steam, kill a stream, or take over another
    client's lease. If the user has not actually exited, refuse and retain the
    blocker. The check is deliberately stricter than a disappearing Moonlight
    window: zero Wolf lobbies, ZERO Wolf sessions and no Steam writers.
    Concurrency isolation against separately privileged Wolf UI/direct users
    must be established independently before enabling Games writes.
    """
    if not _valid_client_id(expected_client_id) or not callable(wolf_api):
        raise PolicyError("Trusted finished-owner Steam authority required")
    if not callable(host_writer_check):
        raise PolicyError("Host Steam writer preflight required")
    with store.locked() as fd:
        lease = read_lease(fd)
        if lease is None:
            return {"success": True, "status": "idle", "lease_archived": False}
        if lease["version"] != LEASE_VERSION or lease["state"] != "joined":
            raise PolicyError("Uncertain/legacy Steam lease needs operator review")
        if lease["client_id"] != expected_client_id:
            raise PolicyError("Steam lease belongs to a different owner device")
        policy = store.read(fd)
        if (policy is None or not policy.get("workspaces") or
                lease["workspace_id"] != policy["workspaces"][0]["id"] or
                len([dev for dev in policy["devices"]
                     if dev["client_id"] == expected_client_id
                     and not dev["revoked"]]) != 1):
            raise PolicyError("Owner Steam grant or workspace changed")
        # A disconnected Moonlight client is not proof of Steam shutdown.
        # GET checks MUST succeed; incomplete or unexpected Wolf state blocks.
        _require_idle_wolf(wolf_api)
        try:
            clear = host_writer_check()
        except Exception:
            raise PolicyError("Cannot verify Steam writers after exit") from None
        if clear is not True:
            raise PolicyError("Steam still has another writer")
        # Narrow the gap between writer snapshot and final archive; not an
        # atomic exclusion barrier, hence separate Wolf admission is required.
        _require_idle_wolf(wolf_api)
        _archive_lease(fd, lease)
    return {"success": True, "status": "idle", "lease_archived": True}


def stop_owner_steam(wolf_api, *, store, confirmed_stop=False,
                     expected_client_id=None, expected_lease_id=None):
    """Host-local, one-shot PIN-gated StopLobby; no retries on uncertain POST.

    Only version 2 leases contain the PIN. Existing version 1 sessions remain
    playable and require supervised out-of-band shutdown and reconciliation.
    """
    if not confirmed_stop:
        raise PolicyError("Explicit owner Steam stop approval required")
    if not callable(wolf_api):
        raise PolicyError("Missing trusted host-local Wolf API")
    with store.locked() as fd:
        lease = read_lease(fd)
        if lease is None:
            raise PolicyError("No active owner Steam lease")
        if lease["version"] != LEASE_VERSION:
            raise PolicyError("Legacy owner Steam lease has no recoverable PIN")
        if lease["state"] != "joined" or lease["lobby_id"] is None:
            raise PolicyError("Steam lobby state uncertain; refuse automatic stop")
        # Prevent a verified client request from stopping a replacement lease
        # created between initial status authorization and the StopLobby lock.
        if expected_client_id is not None and lease["client_id"] != expected_client_id:
            raise PolicyError("Steam lease belongs to a different owner device")
        if expected_lease_id is not None and lease["id"] != expected_lease_id:
            raise PolicyError("Steam lease changed before stop; retry refused")
        policy = store.read(fd)
        if policy is None or lease["workspace_id"] != policy["workspaces"][0]["id"]:
            raise PolicyError("Owner policy/lease mismatch")
        matching_grants = [
            dev for dev in policy["devices"]
            if dev["client_id"] == lease["client_id"] and not dev["revoked"]]
        if len(matching_grants) != 1:
            raise PolicyError("Lease owner device is no longer authorized")
        current = _inventory(wolf_api("GET", "/api/v1/lobbies"), "lobbies", 256)
        if len(current) != 1:
            raise PolicyError("Ambiguous or absent Wolf lobby; stop refused")
        lobby = current[0]
        connected = lobby.get("connected_sessions")
        if (lobby.get("id") != lease["lobby_id"] or
                lobby.get("name") != "Steam" or
                lobby.get("started_by_profile_id") != policy["workspaces"][0]["profile_id"] or
                lobby.get("pin_required") is not True or
                lobby.get("multi_user") is not False or
                not isinstance(connected, list) or
                len(connected) > 1 or
                any(client != lease["client_id"] for client in connected)):
            raise PolicyError("Wolf lobby differs from authorized owner Steam")
        sessions = _inventory(wolf_api("GET", "/api/v1/sessions"), "sessions", 256)
        if len(sessions) > 1 or any(s.get("client_id") != lease["client_id"] for s in sessions):
            raise PolicyError("Another Wolf session is active")
        # Persist uncertainty BEFORE mutating Wolf. A crash, timeout or bad
        # response then blocks any further stop or create attempt.
        lease["state"] = "uncertain"
        write_lease(fd, lease)
        try:
            response = wolf_api("POST", "/api/v1/lobbies/stop", {
                "lobby_id": lease["lobby_id"], "pin": lease["pin"]})
            if not isinstance(response, dict) or response.get("success") is not True:
                raise PolicyError("Wolf stop result uncertain")
            remaining = _inventory(wolf_api("GET", "/api/v1/lobbies"), "lobbies", 256)
            if remaining:
                raise PolicyError("Wolf still reports a lobby")
            live = _inventory(wolf_api("GET", "/api/v1/sessions"), "sessions", 256)
            if len(live) > 1 or any(s.get("client_id") != lease["client_id"] for s in live):
                raise PolicyError("Unexpected Wolf session after stop")
        except Exception:
            # Never reveal raw Wolf failure / private PIN or retry a POST.
            raise PolicyError("Steam stop unverified; lease retained for manual review") from None
        _archive_lease(fd, lease)
    return {"success": True, "status": "idle", "lease_archived": True}


def read_lease(dir_fd):
    """Read private local evidence only. Never return unredacted Wolf data."""
    try:
        fd = os.open(LEASE_FILE, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                     dir_fd=dir_fd)
    except FileNotFoundError:
        return None
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o600
                or meta.st_size > STORE_LIMIT):
            raise PolicyError("Unsafe owner Steam lease file")
        with os.fdopen(fd, "rb", closefd=False) as inp:
            raw = inp.read(STORE_LIMIT + 1)
        if len(raw) > STORE_LIMIT:
            raise PolicyError("Oversized owner Steam lease")
        return _validate_lease(json.loads(raw))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyError("Corrupted owner Steam lease") from exc
    finally:
        os.close(fd)


def write_lease(dir_fd, lease):
    """Atomic, owner-only write while caller holds OwnerStore.locked()."""
    _validate_lease(lease)
    body = (json.dumps(lease, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(body) > STORE_LIMIT:
        raise PolicyError("Oversized owner Steam lease")
    temp = ".owner-lease-" + str(uuid.uuid4())
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                 getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=dir_fd)
    try:
        with os.fdopen(fd, "wb", closefd=False) as out:
            out.write(body)
            out.flush()
            os.fsync(fd)
        os.replace(temp, LEASE_FILE, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        os.fsync(dir_fd)
    finally:
        os.close(fd)
        try:
            os.unlink(temp, dir_fd=dir_fd)
        except FileNotFoundError:
            pass


def owner_launch_status(store):
    """Read-only, minimal status. Requires host-local filesystem permission."""
    with store.locked() as fd:
        lease = read_lease(fd)
        if lease is None:
            return {"status": "idle"}
        return {"status": lease["state"], "manual_review_required": True}


def launch_owner_steam(trusted_client_id, wolf_api, *,
                       store=None, execution_approved=False, video_caps=None):
    """Create + join a named owner Steam lobby under a persisted launch lease.

    *** NOT A NETWORK HANDLER. ***
    trusted_client_id must come from a verified authenticated local host broker.
    wolf_api is a host-local, bounded callable (method, path[, json_body]).
    All other games sessions or lobbies trigger a refusal in owner_lobby.py.
    A lease always remains after any attempted create, until an explicit,
    future checked recovery routine is implemented. No automatic retry/stop.
    """
    if not execution_approved:
        raise PolicyError("Live Wolf lobby execution is disabled by default")
    if not _valid_client_id(trusted_client_id):
        raise PolicyError("Invalid authenticated Wolf device identity")
    if wolf_api is None or not callable(wolf_api):
        raise PolicyError("Missing trusted host-local Wolf API")
    store = store or OwnerStore("/var/lib/optiplex-now")
    with store.locked() as fd:
        if read_lease(fd) is not None:
            raise PolicyError("Previous owner lobby transaction requires manual review")
        policy = store.read(fd)
        if policy is None:
            raise PolicyError("Owner Steam policy is not initialized")

        # Never use a client-supplied profile name, app ID or session settings.
        clients = wolf_api("GET", "/api/v1/clients")
        # Fail closed on the owner's grant before reading additional sensitive
        # Wolf state or considering any launch.
        resolve_games(policy, trusted_client_id, clients)
        profiles = wolf_api("GET", "/api/v1/profiles")
        apps = wolf_api("GET", "/api/v1/apps")
        sessions = wolf_api("GET", "/api/v1/sessions")
        lobbies = wolf_api("GET", "/api/v1/lobbies")
        plan = plan_owner_steam_lobby(
            policy, trusted_client_id, clients, profiles, apps,
            sessions, lobbies, video_caps=video_caps)

        lease = {
            "version": LEASE_VERSION, "id": str(uuid.uuid4()),
            "client_id": trusted_client_id, "workspace_id": plan["workspace_id"],
            "state": "creating", "lobby_id": None,
            "pin": list(plan["create_body"]["pin"]),
        }
        # Write durable blocker BEFORE any mutating Wolf API request.
        write_lease(fd, lease)
        try:
            created = wolf_api("POST", plan["create_path"], plan["create_body"])
            join_body = fill_join_lobby(plan, created)
            lease["lobby_id"] = join_body["lobby_id"]
            lease["state"] = "created"
            write_lease(fd, lease)
            joined = wolf_api("POST", plan["join_path"], join_body)
            if not isinstance(joined, dict) or joined.get("success") is not True:
                raise PolicyError("Wolf did not confirm the private lobby join")
            lease["state"] = "joined"
            write_lease(fd, lease)
        except Exception:
            # An API timeout or unexpected reply can mean a POST succeeded.
            # Never assume it was rolled back or stop a possibly live stream.
            # If this write fails, the prior creating/created lease remains.
            lease["state"] = "uncertain"
            try:
                write_lease(fd, lease)
            except OSError:
                pass
            raise PolicyError(
                "Owner Steam lobby state uncertain; no automatic retry or cleanup"
            ) from None

        # Never return private lobby PIN, runner config, or Wolf session keys.
        return {"success": True, "status": "joined",
                "manual_review_required_for_next_launch": True}
