"""Linux-local owner authorization boundary for NOW Host, source-only prototype.

Only an already-authenticated Unix-domain peer with the configured owner UID
may request a short-lived, one-use operation ticket. A trusted host-local
confirmation callback is mandatory; it must NOT be controlled by the client.
No TCP listener, SSH integration, Docker access or automatic approval exists.

The live privileged host service and GUI confirmation are NOT implemented.
This module supplies the protocol and security checks, not production consent.
"""
from __future__ import annotations

import json
from pathlib import Path
import secrets
import socket
import struct
import time

import host_transaction as tx

PROTOCOL = 1
MAX_REQUEST = 4096
TICKET_TTL = 60.0
ALLOWED_OPERATION = "start_wolf"


class AuthorizationError(RuntimeError):
    pass


def peer_identity(connection: socket.socket) -> tuple[int, int]:
    """Get peer UID and PID from the Linux kernel; never trust JSON claims."""
    if connection.family != socket.AF_UNIX:
        raise AuthorizationError("Only local Unix-domain connections are allowed")
    if not hasattr(socket, "SO_PEERCRED"):
        raise AuthorizationError("Kernel peer credentials are not supported")
    try:
        credentials = connection.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, _gid = struct.unpack("3i", credentials)
    except (OSError, struct.error) as exc:
        raise AuthorizationError("Unable to authenticate local peer") from exc
    if pid <= 0 or uid < 0:
        raise AuthorizationError("Invalid kernel peer credentials")
    return uid, pid


def checked_generation(workspace: Path, generation: str) -> Path:
    """Require a prepared, owned workspace and exact active generation."""
    root = tx._validate_workspace(workspace)
    if root.is_symlink() or not root.is_dir():
        raise AuthorizationError("No managed host workspace")
    try:
        state = tx._state(root)
    except (ValueError, OSError) as exc:
        raise AuthorizationError("Host configuration cannot be verified") from exc
    if not state or state.get("active") != generation or not isinstance(generation, str):
        raise AuthorizationError("Stale or missing host generation")
    # Never issue a new authorization for an attempt already in progress.
    if (root / "deployment.json").exists() or (root / "deployment.json").is_symlink():
        raise AuthorizationError("Previous deployment requires operator recovery")
    return root


class OwnerAuthority:
    """In-memory one-use grants, bound to OS peer credentials and generation.

    No on-disk secrets or token serialization. After a restart, all grants
    disappear. The caller must supply an independently trusted confirmation
    function implemented inside the eventual host owner UI or polkit broker.
    """

    def __init__(self, owner_uid: int, *, clock=time.monotonic):
        if not isinstance(owner_uid, int) or isinstance(owner_uid, bool) or owner_uid < 0:
            raise ValueError("An explicit nonnegative owner UID is required")
        self.owner_uid = owner_uid
        self._clock = clock
        self._tickets: dict[str, tuple[int, int, str, str, str, float]] = {}

    def _owner(self, connection: socket.socket) -> tuple[int, int]:
        uid, pid = peer_identity(connection)
        if uid != self.owner_uid:
            raise AuthorizationError("Local peer is not the configured owner")
        return uid, pid

    def issue(self, connection: socket.socket, *, operation: str,
              workspace: Path, generation: str, confirm) -> str:
        """Only host-controlled explicit confirmation may issue a ticket."""
        uid, pid = self._owner(connection)
        if operation != ALLOWED_OPERATION:
            raise AuthorizationError("Operation not permitted")
        root = checked_generation(workspace, generation)
        if not callable(confirm):
            raise AuthorizationError("No trusted confirmation mechanism")
        # Any exception or refusal is a denial. Client-provided booleans must
        # NEVER be installed as the production confirmation callback.
        try:
            accepted = confirm(uid, operation, root, generation)
        except Exception as exc:
            raise AuthorizationError("Owner confirmation failed") from exc
        if accepted is not True:
            raise AuthorizationError("Owner did not approve the operation")
        # Recheck after the confirmation dialog; user interaction can take time.
        checked_generation(root, generation)
        now = self._clock()
        self._tickets = {key: value for key, value in self._tickets.items()
                         if value[-1] > now}
        if len(self._tickets) >= 16:
            raise AuthorizationError("Too many pending authorizations")
        token = secrets.token_urlsafe(32)
        self._tickets[token] = (
            uid, pid, operation, str(root), generation, now + TICKET_TTL)
        return token

    def consume(self, connection: socket.socket, token: str, *,
                operation: str, workspace: Path, generation: str) -> None:
        """Consume ticket once, even when a subsequent check fails."""
        uid, pid = self._owner(connection)
        if not isinstance(token, str) or len(token) > 128 or len(token) < 32:
            raise AuthorizationError("Invalid owner ticket")
        record = self._tickets.pop(token, None)
        if record is None:
            raise AuthorizationError("Missing, expired or already used approval")
        root = checked_generation(workspace, generation)
        expected = (uid, pid, operation, str(root), generation)
        if record[:5] != expected or record[5] <= self._clock():
            raise AuthorizationError("Stale or mismatched owner approval")


def handle_local_request(connection: socket.socket,
                         authority: OwnerAuthority, confirm) -> dict:
    """Serve exactly one small JSON request on an accepted Unix socket.

    This source-only handler does NOT start a listener, daemon, container or
    service. No generic commands, file reads or remote connections accepted.
    """
    authority._owner(connection)
    connection.settimeout(3)
    try:
        data = bytearray()
        while b"\n" not in data:
            chunk = connection.recv(min(512, MAX_REQUEST + 1 - len(data)))
            if not chunk:
                raise AuthorizationError("Incomplete local request")
            data.extend(chunk)
            if len(data) > MAX_REQUEST:
                raise AuthorizationError("Local request too large")
        first, _, extra = bytes(data).partition(b"\n")
        if extra.strip():
            raise AuthorizationError("Multiple requests per connection are not allowed")
        try:
            request = json.loads(first.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AuthorizationError("Invalid JSON request") from exc
        if not isinstance(request, dict) or set(request) != {
            "version", "operation", "workspace", "generation"
        } or type(request["version"]) is not int or request["version"] != PROTOCOL:
            raise AuthorizationError("Unexpected protocol fields or version")
        if (not isinstance(request["workspace"], str)
                or len(request["workspace"]) > 1024):
            raise AuthorizationError("Invalid workspace path")
        token = authority.issue(
            connection, operation=request["operation"],
            workspace=Path(request["workspace"]),
            generation=request["generation"], confirm=confirm)
        return {"version": PROTOCOL, "status": "approved_for_simulation",
                "ticket": token}
    except (socket.timeout, OSError) as exc:
        raise AuthorizationError("Local connection failed") from exc


def serve_one(connection: socket.socket,
              authority: OwnerAuthority, confirm) -> None:
    """Reply to exactly one local request; expose no internal exception text.

    The caller owns accept(), socket lifecycle and the trusted local owner UI.
    This is NOT a listening service or a privileged installer endpoint.
    """
    try:
        response = handle_local_request(connection, authority, confirm)
    except AuthorizationError:
        response = {"version": PROTOCOL, "status": "denied"}
    encoded = (json.dumps(response, separators=(",", ":")) + "\n").encode()
    if len(encoded) > 1024:
        raise AuthorizationError("Internal response exceeds size limit")
    try:
        connection.settimeout(3)
        connection.sendall(encoded)
    except (OSError, socket.timeout) as exc:
        raise AuthorizationError("Failed sending local reply") from exc
