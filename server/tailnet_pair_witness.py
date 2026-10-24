"""In-memory, short-lived owner pairing witness for explicit Games enrollment.

A candidate is a uniquely NEW Wolf client observed after the server handled
a PIN approval for this exact Tailscale owner/node/source. This observation
narrows owner review; it is NOT a cryptographic assertion connecting the
Tailscale node, SSH key and Moonlight certificate. No witness alone grants
access or installs an SSH key. Restarting the listener drops witnesses.
"""
import re
import time

from owner_access import PolicyError, paired_client_ids
from tailnet_owner_identity import tailnet_ipv4

TTL = 600
MAX_IDENTITIES = 16
REQUEST_ID = re.compile(r"[0-9a-f]{32}\Z")


class PairingWitness:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self._peers = {}

    def _key(self, peer, address):
        if (not isinstance(peer, tuple) or len(peer) != 2
                or not all(isinstance(value, str) and value for value in peer)
                or tailnet_ipv4(address) != address):
            raise PolicyError("Unverified owner node for pairing witness")
        return (peer[0], peer[1], address)

    def _record(self, peer, address):
        key = self._key(peer, address)
        now = self.clock()
        self._peers = {k: v for k, v in self._peers.items()
                       if v["until"] > now}
        if key not in self._peers and len(self._peers) >= MAX_IDENTITIES:
            raise PolicyError("Too many owner pairing witnesses")
        return self._peers.setdefault(key, {
            "until": now + TTL, "requests": {}, "baseline": None,
            "paired_at": None})

    def staged(self, peer, address, request_id):
        if not isinstance(request_id, str) or REQUEST_ID.fullmatch(request_id) is None:
            raise PolicyError("Invalid owner enrollment request reference")
        entry = self._record(peer, address)
        entry["requests"][request_id] = self.clock() + TTL
        if len(entry["requests"]) > 16:
            raise PolicyError("Too many staged owner keys for node")

    def paired(self, peer, address, before):
        if not isinstance(before, frozenset) or not before or not all(
                isinstance(value, str) for value in before):
            # Empty pre-pair client inventory is a legitimate first setup.
            if before != frozenset():
                raise PolicyError("Invalid pre-pair Wolf client inventory")
        entry = self._record(peer, address)
        entry["baseline"] = before
        entry["paired_at"] = self.clock()
        entry["until"] = entry["paired_at"] + TTL

    def candidate(self, peer, address, request_id, wolf_api):
        key = self._key(peer, address)
        entry = self._peers.get(key)
        now = self.clock()
        if (entry is None or entry["until"] <= now
                or not isinstance(request_id, str)
                or REQUEST_ID.fullmatch(request_id) is None
                or entry["requests"].get(request_id, 0) <= now
                or entry["baseline"] is None or entry["paired_at"] is None
                or entry["paired_at"] + TTL <= now):
            raise PolicyError("No fresh owner pairing and staged key for same node")
        paired = paired_client_ids(wolf_api("GET", "/api/v1/clients"))
        new = paired - entry["baseline"]
        if len(new) != 1:
            raise PolicyError("Wolf pairing identity not uniquely observed")
        return next(iter(new))

    def consumed(self, peer, address, request_id):
        entry = self._peers.get(self._key(peer, address))
        if entry:
            entry["requests"].pop(request_id, None)
            entry["baseline"] = None
            entry["paired_at"] = None
