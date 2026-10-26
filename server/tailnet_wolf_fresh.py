"""Opt-in safe selection of only new Wolf requests from an owner Tailscale node.

Wolf can retain abandoned PIN requests after the Moonlight process exits.
The request index is NOT a stable identity. Prepare must run BEFORE starting
a fresh Moonlight attempt. Existing secrets are kept only in server memory and
never returned through HTTP. No request is deleted or implicitly approved.
"""
import time
from owner_access import PolicyError
from tailnet_owner_identity import tailnet_ipv4

TTL = 300
LIMIT = 32


def _requests(call_api):
    result = call_api("GET", "/api/v1/pair/pending")
    if (not isinstance(result, dict) or result.get("success") is not True
            or not isinstance(result.get("requests"), list)
            or len(result["requests"]) > LIMIT):
        raise PolicyError("Wolf pending queue malformed")
    records = result["requests"]
    secrets = set()
    for item in records:
        if (not isinstance(item, dict) or not isinstance(item.get("client_ip"), str)
                or not isinstance(item.get("pair_secret"), str)
                or not 1 <= len(item["pair_secret"]) <= 4096
                or item["pair_secret"] in secrets):
            raise PolicyError("Unsafe Wolf pending queue")
        secrets.add(item["pair_secret"])
    return records


class FreshPairWindow:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self._prepared = {}

    def _key(self, verified_peer, source):
        if (not isinstance(verified_peer, tuple) or len(verified_peer) != 2
                or not all(isinstance(x, str) and x for x in verified_peer)
                or tailnet_ipv4(source) != source):
            raise PolicyError("Pairing preparation requires verified owner source")
        return (*verified_peer, source)

    def prepare(self, verified_peer, source, *, call_api):
        key = self._key(verified_peer, source)
        records = _requests(call_api)
        baseline = frozenset(x["pair_secret"] for x in records)
        now = self.clock()
        self._prepared = {k: v for k, v in self._prepared.items()
                          if v[0] > now}
        if len(self._prepared) >= LIMIT and key not in self._prepared:
            raise PolicyError("Too many pairing preparations")
        self._prepared[key] = (now + TTL, baseline)
        return {"success": True, "status": "prepared"}

    def _fresh(self, verified_peer, source, *, call_api):
        key = self._key(verified_peer, source)
        prepared = self._prepared.get(key)
        if prepared is None or prepared[0] <= self.clock():
            raise PolicyError("Fresh Wolf pairing preparation required")
        baseline = prepared[1]
        records = _requests(call_api)
        fresh = [(i, x) for i, x in enumerate(records, 1)
                 if x["client_ip"] == source and x["pair_secret"] not in baseline]
        if len(fresh) > 1:
            raise PolicyError("More than one new Wolf request from same node")
        return fresh

    def pending(self, verified_peer, source, *, call_api):
        fresh = self._fresh(verified_peer, source, call_api=call_api)
        return {"success": True, "clients": [
            {"index": i, "client_ip": source} for i, _ in fresh]}

    def pair(self, verified_peer, source, payload, *, call_api):
        if not isinstance(payload, dict) or set(payload) != {
                "index", "client_ip", "pin"}:
            raise PolicyError("Invalid pairing payload")
        index, address, pin = payload["index"], payload["client_ip"], payload["pin"]
        if (type(index) is not int or not 1 <= index <= LIMIT
                or address != source or not isinstance(pin, str)
                or not 4 <= len(pin) <= 12 or not pin.isascii()
                or not pin.isdecimal()):
            raise PolicyError("Invalid pending pairing selection")
        fresh = self._fresh(verified_peer, source, call_api=call_api)
        if len(fresh) != 1 or fresh[0][0] != index:
            raise PolicyError("Fresh Wolf pending selection changed")
        secret = fresh[0][1]["pair_secret"]
        result = call_api("POST", "/api/v1/pair/client",
                          {"pair_secret": secret, "pin": pin})
        if not isinstance(result, dict) or result.get("success") is not True:
            raise PolicyError("Wolf refused fresh pairing PIN")
        # Invalidates approval retries. Does not attest that the subsequent
        # cryptographic handshake or client registration completed.
        self._prepared.pop(self._key(verified_peer, source), None)
        return {"success": True}
