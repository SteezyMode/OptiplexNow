"""Owner-device entitlement policy for a future local NOW Host authority.

This module does not launch Wolf, pair devices, or grant network access. It stores
an owner/workspace relationship separately from Moonlight device certificates.
Only the privileged host-local adapter should call mutation operations. In
particular, neither a client-supplied profile ID nor pairing alone confers access.
"""
import contextlib
import fcntl
import json
import os
import re
import stat
import uuid

VERSION = 1
STORE_LIMIT = 65536
CLIENT_ID = re.compile(r"[0-9]{1,20}\Z")
PROFILE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class PolicyError(ValueError):
    pass


def _valid_client_id(value):
    return isinstance(value, str) and CLIENT_ID.fullmatch(value) is not None


def _valid_profile_id(value):
    return (isinstance(value, str) and PROFILE_ID.fullmatch(value) is not None
            and value != "moonlight-profile-id")


def _uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except (TypeError, ValueError):
        return False


def paired_client_ids(reply):
    """Return known paired Moonlight identities; refuse conflicts or ambiguity."""
    if (not isinstance(reply, dict) or reply.get("success") is not True
            or not isinstance(reply.get("clients"), list)
            or len(reply["clients"]) > 2048):
        raise PolicyError("Invalid Wolf paired-client inventory")
    known = {}
    for entry in reply["clients"]:
        if not isinstance(entry, dict):
            raise PolicyError("Invalid Wolf client entry")
        client, folder = entry.get("client_id"), entry.get("app_state_folder")
        if not _valid_client_id(client) or not isinstance(folder, str) or not folder:
            raise PolicyError("Invalid Wolf client identity or folder")
        if client in known and known[client] != folder:
            raise PolicyError("Conflicting Wolf records for the same client")
        known[client] = folder
    return frozenset(known)


def named_steam_profiles(reply):
    if (not isinstance(reply, dict) or reply.get("success") is not True
            or not isinstance(reply.get("profiles"), list)
            or len(reply["profiles"]) > 256):
        raise PolicyError("Invalid Wolf profiles inventory")
    profiles = set()
    candidates = set()
    for entry in reply["profiles"]:
        if not isinstance(entry, dict):
            raise PolicyError("Invalid Wolf profile entry")
        name, apps = entry.get("id"), entry.get("apps")
        if not isinstance(name, str) or len(name) > 128 or not name or not isinstance(apps, list):
            raise PolicyError("Invalid Wolf profile")
        if name in profiles:
            raise PolicyError("Duplicate Wolf profile ID")
        profiles.add(name)
        if any(not isinstance(app, dict) for app in apps):
            raise PolicyError("Invalid Wolf app entry")
        if sum(app.get("title") == "Steam" for app in apps) > 1:
            raise PolicyError("Ambiguous Steam app in Wolf profile")
        if any(app.get("title") == "Steam" for app in apps) and _valid_profile_id(name):
            candidates.add(name)
    return frozenset(candidates)


def validate(data):
    """Validate a versioned, bounded owner-only policy; fail closed on drift."""
    if not isinstance(data, dict) or set(data) != {
        "version", "host_id", "principals", "workspaces", "devices"
    } or data["version"] != VERSION or not _uuid(data["host_id"]):
        raise PolicyError("Invalid owner policy header")
    principals, workspaces, devices = data["principals"], data["workspaces"], data["devices"]
    if (not isinstance(principals, list) or len(principals) != 1 or
            not isinstance(workspaces, list) or len(workspaces) != 1 or
            not isinstance(devices, list) or len(devices) > 512):
        raise PolicyError("Unsupported owner policy shape")
    p, w = principals[0], workspaces[0]
    if (not isinstance(p, dict) or set(p) != {"id", "role"} or not _uuid(p["id"])
            or p["role"] != "owner" or not isinstance(w, dict)
            or set(w) != {"id", "principal_id", "provider", "profile_id", "service"}
            or not _uuid(w["id"]) or w["principal_id"] != p["id"]
            or w["provider"] != "wolf" or w["service"] != "games"
            or not _valid_profile_id(w["profile_id"])):
        raise PolicyError("Invalid owner Steam workspace")
    seen = set()
    for device in devices:
        if (not isinstance(device, dict) or
                set(device) != {"client_id", "principal_id", "services", "revoked"} or
                not _valid_client_id(device["client_id"]) or
                device["client_id"] in seen or device["principal_id"] != p["id"] or
                device["services"] != ["games"] or type(device["revoked"]) is not bool):
            raise PolicyError("Invalid or conflicting device grant")
        seen.add(device["client_id"])
    return data


def new_owner(profile_id, profiles_reply):
    """Host owner explicitly adopts a verified, existing named Wolf Steam app."""
    if profile_id not in named_steam_profiles(profiles_reply):
        raise PolicyError("Selected existing named Steam profile not found")
    principal = str(uuid.uuid4())
    return validate({
        "version": VERSION, "host_id": str(uuid.uuid4()),
        "principals": [{"id": principal, "role": "owner"}],
        "workspaces": [{
            "id": str(uuid.uuid4()), "principal_id": principal,
            "provider": "wolf", "profile_id": profile_id, "service": "games"
        }],
        "devices": []
    })


def approve_device(data, client_id, clients_reply):
    validate(data)
    if not _valid_client_id(client_id) or client_id not in paired_client_ids(clients_reply):
        raise PolicyError("Device is not in the current Wolf paired-client inventory")
    for device in data["devices"]:
        if device["client_id"] == client_id:
            if device["revoked"]:
                device["revoked"] = False
                return
            raise PolicyError("Device already approved")
    data["devices"].append({
        "client_id": client_id, "principal_id": data["principals"][0]["id"],
        "services": ["games"], "revoked": False
    })
    validate(data)


def revoke_device(data, client_id):
    validate(data)
    for device in data["devices"]:
        if device["client_id"] == client_id and not device["revoked"]:
            device["revoked"] = True
            return
    raise PolicyError("No active grant for device")


def resolve_games(data, client_id, clients_reply):
    """Server-only resolution; no entitlement derived from a client profile name."""
    validate(data)
    if client_id not in paired_client_ids(clients_reply):
        raise PolicyError("Device is not paired with this Wolf host")
    for device in data["devices"]:
        if (device["client_id"] == client_id and not device["revoked"]
                and "games" in device["services"]):
            return {
                "principal_id": device["principal_id"],
                "workspace_id": data["workspaces"][0]["id"],
                "wolf_profile_id": data["workspaces"][0]["profile_id"],
            }
    raise PolicyError("Device has no owner Games authorization")


class OwnerStore:
    """Private atomic store. Directory must be owned by executing user, mode 0700."""
    def __init__(self, directory):
        self.directory = directory

    @contextlib.contextmanager
    def locked(self):
        try:
            os.mkdir(self.directory, 0o700)
        except FileExistsError:
            pass
        flags = os.O_RDONLY | O_DIRECTORY | O_NOFOLLOW
        try:
            fd = os.open(self.directory, flags)
        except OSError as exc:
            raise PolicyError("Unsafe owner state directory") from exc
        try:
            meta = os.fstat(fd)
            if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid()
                    or stat.S_IMODE(meta.st_mode) != 0o700):
                raise PolicyError("Owner state directory ownership/mode invalid")
            lock = os.open(".lock", os.O_CREAT | os.O_RDWR | O_NOFOLLOW, 0o600, dir_fd=fd)
            try:
                lm = os.fstat(lock)
                if (not stat.S_ISREG(lm.st_mode) or lm.st_uid != os.geteuid()
                        or stat.S_IMODE(lm.st_mode) != 0o600):
                    raise PolicyError("Owner policy lock permissions invalid")
                fcntl.flock(lock, fcntl.LOCK_EX)
                yield fd
            finally:
                os.close(lock)
        finally:
            os.close(fd)

    def read(self, fd):
        try:
            handle = os.open("owner-access.json", os.O_RDONLY | O_NOFOLLOW, dir_fd=fd)
        except FileNotFoundError:
            return None
        try:
            meta = os.fstat(handle)
            if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
                    or meta.st_uid != os.geteuid()
                    or stat.S_IMODE(meta.st_mode) != 0o600
                    or meta.st_size > STORE_LIMIT):
                raise PolicyError("Owner policy file permissions/size invalid")
            with os.fdopen(handle, "rb", closefd=False) as stream:
                body = stream.read(STORE_LIMIT + 1)
            if len(body) > STORE_LIMIT:
                raise PolicyError("Owner policy exceeds limit")
            return validate(json.loads(body))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PolicyError("Corrupted owner policy") from exc
        finally:
            os.close(handle)

    def write(self, fd, data):
        validate(data)
        body = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(body) > STORE_LIMIT:
            raise PolicyError("Owner policy exceeds limit")
        name = ".owner-access-" + str(uuid.uuid4())
        handle = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | O_NOFOLLOW,
                         0o600, dir_fd=fd)
        try:
            with os.fdopen(handle, "wb", closefd=False) as stream:
                stream.write(body)
                stream.flush()
                os.fsync(handle)
            os.replace(name, "owner-access.json", src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
        finally:
            os.close(handle)
            try:
                os.unlink(name, dir_fd=fd)
            except FileNotFoundError:
                pass
