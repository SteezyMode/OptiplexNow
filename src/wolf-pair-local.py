#!/usr/bin/env python3
"""Local-only Wolf pairing bridge. Run on the Wolf host; never expose as a network service.

Requires local permission to execute docker. The caller must authorize access separately.
Output of 'pending' intentionally omits pair_secret. For 'pair', supply JSON on stdin.
"""
import argparse
import json
import subprocess
import sys

CONTAINER = "wolf"
SOCKET = "/run/user/wolf/wolf.sock"
MAX_RESPONSE = 65536

WOLF_CLIENT = r'''
import json
import socket
import sys
method, path = sys.argv[1:3]
body = sys.stdin.buffer.read(4096) if method == "POST" else b""
sock = socket.socket(socket.AF_UNIX)
sock.settimeout(5)
sock.connect("/run/user/wolf/wolf.sock")
request = (method + " " + path + " HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n").encode()
if body:
    request += ("Content-Type: application/json\r\nContent-Length: " + str(len(body)) + "\r\n").encode()
sock.sendall(request + b"\r\n" + body)
response = bytearray()
while True:
    chunk = sock.recv(16384)
    if not chunk:
        break
    response.extend(chunk)
    if len(response) > 65536:
        raise ValueError("Wolf response too large")
sock.close()
headers, sep, payload = bytes(response).partition(b"\r\n\r\n")
if not sep or b" 200 " not in headers.split(b"\r\n", 1)[0]:
    raise RuntimeError("Wolf API returned an error")
print(payload.decode("utf-8"))
'''

def call_api(method, path, body=None):
    args = ["docker", "exec", "-i", CONTAINER, "python3", "-c", WOLF_CLIENT, method, path]
    p = subprocess.run(args, input=json.dumps(body).encode() if body is not None else b"",
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
    if p.returncode:
        raise RuntimeError("Cannot access local Wolf API; verify Docker permissions and Wolf state")
    return json.loads(p.stdout)

def owner_profile_readiness(profiles_reply, clients_reply):
    """Return non-secret, read-only Wolf metadata; never grant access.

    A single named Steam profile is only a candidate. It is NOT evidence that
    an SSH caller, a Moonlight certificate or an invited member owns it.
    """
    if (not isinstance(profiles_reply, dict) or
            profiles_reply.get("success") is not True or
            not isinstance(profiles_reply.get("profiles"), list) or
            not isinstance(clients_reply, dict) or
            clients_reply.get("success") is not True or
            not isinstance(clients_reply.get("clients"), list)):
        raise ValueError("Malformed Wolf profile or client inventory")
    profiles = profiles_reply["profiles"]
    clients = clients_reply["clients"]
    if len(profiles) > 256 or len(clients) > 2048:
        raise ValueError("Wolf inventory exceeds inspection limits")

    profile_ids = set()
    candidates = []
    direct = False
    for profile in profiles:
        if not isinstance(profile, dict):
            raise ValueError("Invalid Wolf profile entry")
        ident = profile.get("id")
        apps = profile.get("apps")
        if not isinstance(ident, str) or not ident or len(ident) > 128 or not isinstance(apps, list):
            raise ValueError("Invalid Wolf profile identity or app list")
        if ident in profile_ids:
            raise ValueError("Duplicate Wolf profile identity")
        profile_ids.add(ident)
        steam_count = sum(
            isinstance(app, dict) and app.get("title") == "Steam"
            for app in apps
        )
        if any(not isinstance(app, dict) for app in apps) or steam_count > 1:
            raise ValueError("Invalid or ambiguous Wolf Steam application")
        if steam_count:
            if ident == "moonlight-profile-id":
                direct = True
            else:
                # Never forward Wolf profile PINs or app runner configuration.
                candidates.append({"profile_id": ident})

    seen = {}
    repeated = 0
    for client in clients:
        if not isinstance(client, dict):
            raise ValueError("Invalid paired client")
        ident = client.get("client_id")
        folder = client.get("app_state_folder")
        if not isinstance(ident, str) or not ident or len(ident) > 128:
            raise ValueError("Invalid paired client identity")
        if not isinstance(folder, str) or not folder or len(folder) > 256:
            raise ValueError("Invalid paired client state")
        if ident in seen:
            if seen[ident] != folder:
                raise ValueError("Conflicting Wolf records for one client")
            repeated += 1
        else:
            seen[ident] = folder

    status = ("none" if not candidates else
              "single_named_candidate" if len(candidates) == 1 else
              "multiple_named_candidates")
    return {
        "success": True,
        "status": status,
        "direct_steam_available": direct,
        "named_steam_candidates": candidates,
        "unique_paired_clients": len(seen),
        "identical_duplicate_records": repeated,
        # A read-only profile match must NEVER grant a device or member access.
        "owner_mapping_verified": False,
        "can_auto_assign": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pending", "pair", "owner-status"))
    args = parser.parse_args()
    if args.action == "pending":
        response = call_api("GET", "/api/v1/pair/pending")
        if response.get("success") is not True:
            raise RuntimeError("Wolf refused pending pairing query")
        # No pair secrets leave this helper during listing.
        requests = response.get("requests") or []
        print(json.dumps({"success": True, "count": len(requests),
                          "clients": [{"index": i + 1, "client_ip": r.get("client_ip", "")}
                                      for i, r in enumerate(requests)]}))
    elif args.action == "owner-status":
        profiles = call_api("GET", "/api/v1/profiles")
        clients = call_api("GET", "/api/v1/clients")
        print(json.dumps(owner_profile_readiness(profiles, clients)))
    else:
        # Local authenticated caller sends index and PIN through stdin (not process argv).
        request = json.load(sys.stdin)
        index, pin = request.get("index"), request.get("pin")
        client_ip = request.get("client_ip")
        if type(index) is not int or index < 1 or not isinstance(pin, str) or not (4 <= len(pin) <= 12) or not pin.isdigit():
            raise ValueError("Invalid index or PIN")
        pending = call_api("GET", "/api/v1/pair/pending")
        requests = pending.get("requests") or []
        if pending.get("success") is not True or index > len(requests):
            raise ValueError("Pairing request expired; refresh pending requests")
        selected = requests[index - 1]
        if not isinstance(client_ip, str) or selected.get("client_ip") != client_ip:
            raise ValueError("Pending clients changed; refresh and select again")
        secret = selected.get("pair_secret")
        if not isinstance(secret, str) or not secret:
            raise ValueError("Pairing request missing secret")
        result = call_api("POST", "/api/v1/pair/client", {"pair_secret": secret, "pin": pin})
        print(json.dumps({"success": result.get("success") is True}))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        sys.exit(1)
