"""In-memory, deny-by-default owner approval for future Moonlight pairing.

This module deliberately has no network endpoint, executable entry point,
persistence, privileged operations or Wolf/Sunshine/Moonlight integration.

Caller trust boundary:
  * PeerIdentity must be constructed by a *trusted* Tailscale WhoIs verifier,
    never from client-supplied JSON, headers, display names or request bodies.
  * owner_decide() and take_grant_for_adapter() may only be invoked from a
    separately authenticated, local-owner / privileged-host boundary.
  * Request status and IDs confer no streaming authorization.
"""

from dataclasses import dataclass
import re
import secrets
import threading
import time

BACKENDS = frozenset(("sunshine", "wolf"))
DEFAULT_TTL_SECONDS = 180
DEFAULT_MAX_REQUESTS = 16
_ID = re.compile(r"[a-zA-Z0-9_-]{1,128}\Z")
_REQUEST_ID = re.compile(r"[a-zA-Z0-9_-]{24,96}\Z")


@dataclass(frozen=True)
class PeerIdentity:
    """Verified Tailscale device AND account identifiers, not network inputs."""

    node_id: str
    user_id: str

    def __post_init__(self):
        for value in (self.node_id, self.user_id):
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise ValueError("Invalid verified peer identity")


@dataclass(frozen=True)
class PairingGrant:
    """One-time internal authority for a future backend-specific adapter.

    Not a Moonlight certificate, password, access token or HTTP response.
    """

    request_id: str
    peer: PeerIdentity
    backend: str


@dataclass(frozen=True)
class OwnerReview:
    """Minimal request details intended only for a trusted local owner UI."""

    request_id: str
    peer: PeerIdentity
    backend: str
    expires_in_seconds: int


@dataclass
class _Request:
    request_id: str
    peer: PeerIdentity
    backend: str
    expires_at: float
    state: str = "pending"


class PairingRequests:
    """Volatile approval queue. One outstanding request per verified device.

    No auto-approval, no replay, no privilege escalation and no data written to
    disk. Restarting the process invalidates every pending authorization.
    """

    def __init__(self, *, ttl_seconds=DEFAULT_TTL_SECONDS,
                 max_requests=DEFAULT_MAX_REQUESTS, clock=None):
        if (type(ttl_seconds) not in (int, float) or
                not 1 <= ttl_seconds <= 600):
            raise ValueError("TTL must be between 1 and 600 seconds")
        if type(max_requests) is not int or not 1 <= max_requests <= 64:
            raise ValueError("Invalid request queue size")
        self._clock = clock if clock is not None else time.monotonic
        if not callable(self._clock):
            raise TypeError("clock must be callable")
        self._ttl = ttl_seconds
        self._limit = max_requests
        self._requests = {}
        self._lock = threading.Lock()

    @staticmethod
    def _valid_peer(peer):
        if not isinstance(peer, PeerIdentity):
            raise TypeError("PeerIdentity must come from a trusted verifier")

    @staticmethod
    def _valid_backend(backend):
        if not isinstance(backend, str) or backend not in BACKENDS:
            raise ValueError("Unknown pairing backend")

    def _purge(self, now):
        for request_id, entry in tuple(self._requests.items()):
            if now >= entry.expires_at:
                del self._requests[request_id]

    def request(self, peer, backend):
        """Register a request from a verified device. Returns an opaque ID.

        Repeated attempts by the same device cannot evade a pending or denied
        decision by changing the backend or obtaining unlimited new IDs.
        """
        self._valid_peer(peer)
        self._valid_backend(backend)
        with self._lock:
            now = self._clock()
            self._purge(now)
            for entry in self._requests.values():
                if entry.peer == peer:
                    if entry.backend != backend:
                        raise ValueError("Device already has a request for another backend")
                    return entry.request_id
            if len(self._requests) >= self._limit:
                raise RuntimeError("Pairing request queue is full")
            # Cryptographically random opaque IDs; collisions fail closed.
            for _ in range(3):
                request_id = secrets.token_urlsafe(24)
                if request_id not in self._requests:
                    break
            else:
                raise RuntimeError("Cannot allocate pairing request ID")
            self._requests[request_id] = _Request(
                request_id=request_id, peer=peer,
                backend=backend, expires_at=now + self._ttl)
            return request_id

    def status_for_peer(self, peer, request_id):
        """A client may learn only the status of its own request.

        'approved' is not proof that a Moonlight pairing has been completed.
        """
        self._valid_peer(peer)
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            return "unknown"
        with self._lock:
            self._purge(self._clock())
            entry = self._requests.get(request_id)
            return entry.state if entry and entry.peer == peer else "unknown"

    def cancel_for_peer(self, peer, request_id):
        """Allow a verified requester to cancel, never approve."""
        self._valid_peer(peer)
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            return False
        with self._lock:
            self._purge(self._clock())
            entry = self._requests.get(request_id)
            # Only pending requests can be withdrawn. A denied request must
            # retain its cooldown; clients cannot cancel/reissue to bypass it.
            if not entry or entry.peer != peer or entry.state != "pending":
                return False
            del self._requests[request_id]
            return True

    def owner_pending(self):
        """For local-owner UI only; must not be exposed on a client endpoint."""
        with self._lock:
            now = self._clock()
            self._purge(now)
            return [
                OwnerReview(entry.request_id, entry.peer, entry.backend,
                            max(0, int(entry.expires_at - now)))
                for entry in self._requests.values()
                if entry.state == "pending"
            ]

    def owner_decide(self, request_id, *, approve):
        """Local-owner-only action. The caller must enforce owner auth."""
        if type(approve) is not bool:
            raise TypeError("Owner decision must be a boolean")
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            return False
        with self._lock:
            self._purge(self._clock())
            entry = self._requests.get(request_id)
            if not entry or entry.state != "pending":
                return False
            entry.state = "approved" if approve else "denied"
            return True

    def take_grant_for_adapter(self, peer, request_id, backend):
        """Local trusted adapter only. Consume once, bind peer AND backend.

        Must never be an HTTP action exposed to an untrusted client; it returns
        internal authority, not an access credential or native pairing result.
        """
        self._valid_peer(peer)
        self._valid_backend(backend)
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            return None
        with self._lock:
            self._purge(self._clock())
            entry = self._requests.get(request_id)
            if (entry is None or entry.state != "approved" or
                    entry.peer != peer or entry.backend != backend):
                return None
            del self._requests[request_id]
            return PairingGrant(request_id, peer, backend)
