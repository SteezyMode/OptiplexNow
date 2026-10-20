#!/usr/bin/env python3
"""Connect NOW's GUI to an opt-in server's owner pairing inbox over Tailscale.

No SSH, passwords, admin endpoint, TLS exception or arbitrary hostname.
Tailscale authenticates the network peer; the server independently verifies
the owner's exact account ID via WhoIs and installer-pinned owner record.
"""
import http.client
import ipaddress
import json
import re
import sys

PORT = 18792
PREFIX = "NOW_OWNER_STATUS="
MAX_BYTES = 16384
TAILNET = ipaddress.ip_network("100.64.0.0/10")
REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{24,96}\Z")
NODE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
BACKEND = frozenset(("sunshine", "wolf"))


def valid_host(address):
    try:
        value = ipaddress.ip_address(address)
    except (ValueError, TypeError):
        return False
    return (value.version == 4 and value in TAILNET
            and str(value) != "100.100.100.100")


def query_owner(host, action, request_id=None, *, connection=http.client.HTTPConnection):
    if not valid_host(host):
        return False, "invalid_host"
    if action not in ("list", "approve", "deny"):
        return False, "invalid_action"
    if action == "list" and request_id is not None:
        return False, "invalid_action"
    if action != "list" and (not isinstance(request_id, str)
                              or not REQUEST_ID.fullmatch(request_id)):
        return False, "invalid_request"
    path = "/v1/owner/pairing/requests"
    if action != "list":
        path += "/" + request_id + "/" + action
    method = "GET" if action == "list" else "POST"
    client = connection(host, PORT, timeout=4)
    try:
        client.request(method, path, body=b"" if method == "POST" else None,
                       headers={"X-NOW-Owner-Client": "desktop-v1",
                                "Accept": "application/json"})
        response = client.getresponse()
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return False, "invalid_response"
        if response.status == 403:
            return False, "owner_not_authorized"
        if response.status == 409:
            return False, "request_expired"
        if response.status != 200:
            return False, "server_unavailable"
        message = json.loads(body)
        if not isinstance(message, dict):
            return False, "invalid_response"
        if action != "list":
            if message.get("decision_recorded") is True:
                return True, "decision_recorded"
            return False, "invalid_response"
        items = message.get("pending")
        if not isinstance(items, list) or len(items) > 16:
            return False, "invalid_response"
        cleaned = []
        for entry in items:
            if not isinstance(entry, dict):
                return False, "invalid_response"
            rid = entry.get("request_id")
            node = entry.get("device_id")
            backend = entry.get("backend")
            if not (isinstance(rid,str) and REQUEST_ID.fullmatch(rid)
                    and isinstance(node,str) and NODE_ID.fullmatch(node)
                    and backend in BACKEND):
                return False, "invalid_response"
            cleaned.append((rid, node, backend))
        return True, cleaned
    except (OSError, ValueError, json.JSONDecodeError, TimeoutError):
        return False, "server_unavailable"
    finally:
        client.close()


def main(argv):
    if len(argv) not in (2, 3):
        print(PREFIX + "invalid_action")
        return 2
    host, action = argv[0], argv[1]
    request_id = argv[2] if len(argv) == 3 else None
    success, response = query_owner(host, action, request_id)
    if not success:
        print(PREFIX + response)
        return 1
    if action == "list":
        if not response:
            print(PREFIX + "none")
        else:
            for rid, node, backend in response:
                print(PREFIX + "request\t" + rid + "\t" + node + "\t" + backend)
    else:
        print(PREFIX + "decision_recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
