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

from owner_access import OwnerStore, PolicyError, STORE_LIMIT, _valid_client_id, _uuid
from owner_lobby import plan_owner_steam_lobby, fill_join_lobby

LEASE_FILE = "owner-steam-lease.json"
LEASE_VERSION = 1
LEASE_STATES = frozenset(("creating", "created", "joined", "uncertain"))


def _validate_lease(lease):
    if not isinstance(lease, dict) or set(lease) != {
            "version", "id", "client_id", "workspace_id", "state", "lobby_id"}:
        raise PolicyError("Invalid owner Steam lease")
    if (lease["version"] != LEASE_VERSION or not _uuid(lease["id"])
            or not _uuid(lease["workspace_id"]) or
            not _valid_client_id(lease["client_id"]) or
            lease["state"] not in LEASE_STATES):
        raise PolicyError("Invalid owner Steam lease values")
    lobby_id = lease["lobby_id"]
    if lobby_id is not None and (not isinstance(lobby_id, str) or
                                len(lobby_id) > 128 or
                                not lobby_id or
                                not all(c.isalnum() or c in "-_" for c in lobby_id)):
        raise PolicyError("Invalid owner Steam lease lobby")
    if lease["state"] in ("created", "joined") and lobby_id is None:
        raise PolicyError("Missing created Steam lobby ID")
    return lease


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
                       store=None, execution_approved=False, video_caps=""):
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
