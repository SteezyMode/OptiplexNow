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
    if action not in ("list", "approve", "deny", "trust"):
        return False, "invalid_action"
    if action == "list" and request_id is not None:
        return False, "invalid_action"
    if action != "list" and (not isinstance(request_id, str)
                              or not REQUEST_ID.fullmatch(request_id)):
        return False, "invalid_request"
    path = "/v1/owner/pairing/requests"
    if action != "list":
        path += "/" + request_id + "/" + ("approve-and-trust" if action == "trust" else action)
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
                if action == "trust" and message.get("future_devices_trusted") is True:
                    return True, "trusted_account"
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



def request_access(host, backend="wolf", *, connection=http.client.HTTPConnection):
    """Submit one idempotent first-client pairing request without SSH."""
    if not valid_host(host):
        return False, "invalid_host"
    if backend not in BACKEND:
        return False, "invalid_action"
    client = connection(host, PORT, timeout=4)
    try:
        client.request("POST", "/v1/pairing/requests",
                       body=json.dumps({"backend":backend}).encode(),
                       headers={"Content-Type":"application/json",
                                "Accept":"application/json"})
        response = client.getresponse()
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return False, "invalid_response"
        if response.status == 403:
            return False, "device_not_authorized_on_tailnet"
        if response.status != 202:
            return False, "server_unavailable"
        result = json.loads(data)
        if not isinstance(result,dict):
            return False, "invalid_response"
        rid = result.get("request_id")
        state = result.get("owner_status")
        if not isinstance(rid,str) or not REQUEST_ID.fullmatch(rid):
            return False, "invalid_response"
        if state not in ("pending","approved","denied"):
            return False, "invalid_response"
        return True, state
    except (OSError, ValueError, json.JSONDecodeError, TimeoutError):
        return False, "server_unavailable"
    finally:
        client.close()


def household_setting(host, desired=None, *, connection=http.client.HTTPConnection):
    """Get or change owner auto-trust via independently WhoIs-verified broker."""
    if not valid_host(host):
        return False, "invalid_host"
    if desired is not None and type(desired) is not bool:
        return False, "invalid_action"
    conn = connection(host, PORT, timeout=4)
    try:
        payload = None if desired is None else json.dumps({"auto_owner": desired}).encode()
        conn.request("GET" if desired is None else "POST",
                     "/v1/owner/household",body=payload,
                     headers={"X-NOW-Owner-Client":"desktop-v1",
                              "Accept":"application/json",
                              **({"Content-Type":"application/json"} if payload is not None else {})})
        response = conn.getresponse()
        data = response.read(MAX_BYTES + 1)
        if len(data)>MAX_BYTES:return False,"invalid_response"
        if response.status==403:return False,"owner_not_authorized"
        if response.status!=200:return False,"server_unavailable"
        reply=json.loads(data)
        if not isinstance(reply,dict) or type(reply.get("auto_owner")) is not bool:
            return False,"invalid_response"
        return True,reply["auto_owner"]
    except (OSError,ValueError,TimeoutError,json.JSONDecodeError):
        return False,"server_unavailable"
    finally:
        conn.close()

def main(argv):
    if len(argv) not in (2, 3):
        print(PREFIX + "invalid_action")
        return 2
    host, action = argv[0], argv[1]
    request_id = argv[2] if len(argv) == 3 else None
    if action in ("owner-status", "owner-enable", "owner-disable"):
        if request_id is not None:
            print(PREFIX+"invalid_action")
            return 2
        desired = (True if action == "owner-enable" else
                   False if action == "owner-disable" else None)
        success, value = household_setting(host, desired)
        print(PREFIX + (("owner_on" if value else "owner_off")
                        if success else value))
        return 0 if success else 1
    if action == "request":
        if request_id is not None or len(argv) != 2:
            print(PREFIX + "invalid_action")
            return 2
        success, state = request_access(host)
        print(PREFIX + (("access_" + state) if success else state))
        return 0 if success else 1
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
        print(PREFIX + response)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
