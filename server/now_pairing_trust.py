"""Small persistent Tailscale-account allowlist for household NOW pairing.

Created only by an explicitly enabled server-role broker, inside its existing
private owner-owned socket directory. Never grant an arbitrary tailnet peer
owner privileges: this policy only marks a *pairing request* approved, and a
native Wolf/MoonlightWeb adapter must still complete service authentication.
"""
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading

_NAME = "household-trust.json"
_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_MAX_FAMILY = 8


class HouseholdTrust:
    def __init__(self, socket_dir, owner_id, *, default_auto_owner=False):
        if not isinstance(owner_id, str) or not _ID.fullmatch(owner_id):
            raise ValueError("Owner identity required")
        directory = Path(socket_dir)
        info = os.lstat(directory)
        if (not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise PermissionError("Household policy needs a private owner directory")
        self.path = directory / _NAME
        self.owner_id = owner_id
        self._lock = threading.RLock()
        if self.path.exists() or self.path.is_symlink():
            self._read()
        else:
            self._write({"auto_owner": bool(default_auto_owner), "family": []})

    def _read(self):
        info = os.lstat(self.path)
        if (not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 1024):
            raise PermissionError("Household policy is not a private regular file")
        fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            current = os.fstat(fd)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise PermissionError("Household policy changed during read")
            raw = os.read(fd, 1025)
        finally:
            os.close(fd)
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != {"owner_id", "auto_owner", "family"}:
            raise ValueError("Invalid household policy")
        if value["owner_id"] != self.owner_id or type(value["auto_owner"]) is not bool:
            raise PermissionError("Household policy belongs to another owner")
        family = value["family"]
        if (not isinstance(family, list) or len(family) > _MAX_FAMILY or
                len(set(str(x) for x in family)) != len(family) or
                any(not isinstance(x, str) or not _ID.fullmatch(x)
                    or x == self.owner_id for x in family)):
            raise ValueError("Invalid trusted household members")
        return value

    def _write(self, value):
        data = dict(value, owner_id=self.owner_id)
        encoded = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
        if len(encoded) > 1024:
            raise ValueError("Household policy too long")
        fd, tmp = tempfile.mkstemp(prefix=".household-", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(encoded)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def status(self):
        with self._lock:
            data = self._read()
            return {"auto_owner": data["auto_owner"],
                    "trusted_family_count": len(data["family"])}

    def trusts(self, peer):
        from now_pairing_requests import PeerIdentity
        if not isinstance(peer, PeerIdentity):
            return False
        with self._lock:
            data = self._read()
            return ((data["auto_owner"] and peer.user_id == self.owner_id)
                    or peer.user_id in data["family"])

    def set_owner_auto(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Expected true or false")
        with self._lock:
            data = self._read()
            data["auto_owner"] = enabled
            self._write(data)

    def trust_existing_request(self, peer):
        """Owner-approved, verified pending peer; not an arbitrary user ID."""
        from now_pairing_requests import PeerIdentity
        if not isinstance(peer, PeerIdentity) or not _ID.fullmatch(peer.user_id):
            raise ValueError("Verified personal Tailscale user required")
        if peer.user_id == self.owner_id:
            raise ValueError("Owner identity is controlled by auto_owner setting")
        with self._lock:
            data = self._read()
            if peer.user_id not in data["family"]:
                if len(data["family"]) >= _MAX_FAMILY:
                    raise ValueError("Household allowlist full")
                data["family"].append(peer.user_id)
                self._write(data)
