"""Narrow owner-only Wolf PIN pairing bridge over a verified Tailscale peer.

Unlike the existing owner SSH pilot, a normal client needs no server username
or shell credential. Wolf's pending secret never leaves this host adapter.
The only eligible pending Wolf request must originate from the SAME verified
Tailscale source IP as the HTTP requester. This is not general guest pairing,
an anonymous Wolf proxy or an authorization grant for managed Games/Downloads.
"""
import ipaddress

from owner_access import PolicyError
from tailnet_owner_identity import tailnet_ipv4

MAX_PENDING = 32


def _pending_for_peer(peer_ip, call_api):
    peer = tailnet_ipv4(peer_ip)
    if peer is None:
        raise PolicyError("Wolf pairing requires an authenticated Tailscale source")
    reply = call_api("GET", "/api/v1/pair/pending")
    pending = reply.get("requests") if isinstance(reply, dict) else None
    if (not isinstance(reply, dict) or reply.get("success") is not True
            or not isinstance(pending, list) or len(pending) > MAX_PENDING):
        raise PolicyError("Wolf pending inventory unavailable")
    matches = []
    for position, item in enumerate(pending, start=1):
        if not isinstance(item, dict):
            raise PolicyError("Wolf pending inventory invalid")
        address = item.get("client_ip")
        if not isinstance(address, str):
            raise PolicyError("Wolf pending client address invalid")
        try:
            validated = str(ipaddress.ip_address(address))
        except ValueError:
            raise PolicyError("Wolf pending client address invalid") from None
        if validated == peer:
            matches.append((position, item))
    if len(matches) > 1:
        raise PolicyError("Ambiguous Wolf requests from same Tailscale node")
    return matches


def pending_owner_wolf(peer_ip, *, call_api):
    """Reveal only this verified peer's pending entry, never pair_secret."""
    matches = _pending_for_peer(peer_ip, call_api)
    return {"success": True, "clients": [
        {"index": index, "client_ip": peer_ip} for index, _ in matches]}


def pair_owner_wolf(peer_ip, payload, *, call_api):
    """Validate PIN, recheck pending source/IP and use host-only Wolf secret."""
    if not isinstance(payload, dict) or set(payload) != {"index", "client_ip", "pin"}:
        raise PolicyError("Invalid Moonlight pairing request")
    index, address, pin = payload["index"], payload["client_ip"], payload["pin"]
    if (type(index) is not int or not 1 <= index <= MAX_PENDING
            or not isinstance(address, str) or address != peer_ip
            or not isinstance(pin, str) or not 4 <= len(pin) <= 12
            or not all("0" <= char <= "9" for char in pin)):
        raise PolicyError("Invalid Moonlight pairing values")
    matches = _pending_for_peer(peer_ip, call_api)
    if not matches or matches[0][0] != index:
        raise PolicyError("Wolf pending device changed; refresh required")
    secret = matches[0][1].get("pair_secret")
    if not isinstance(secret, str) or not 1 <= len(secret) <= 4096:
        raise PolicyError("Wolf pairing secret unavailable")
    result = call_api("POST", "/api/v1/pair/client",
                      {"pair_secret": secret, "pin": pin})
    if not isinstance(result, dict) or result.get("success") is not True:
        raise PolicyError("Wolf refused selected device pairing")
    return {"success": True}
