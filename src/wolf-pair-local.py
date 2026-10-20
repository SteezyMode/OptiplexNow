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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pending", "pair"))
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
    else:
        # Local authenticated caller sends index and PIN through stdin (not process argv).
        request = json.load(sys.stdin)
        index, pin = request.get("index"), request.get("pin")
        if type(index) is not int or index < 1 or not isinstance(pin, str) or not (4 <= len(pin) <= 12) or not pin.isdigit():
            raise ValueError("Invalid index or PIN")
        pending = call_api("GET", "/api/v1/pair/pending")
        requests = pending.get("requests") or []
        if pending.get("success") is not True or index > len(requests):
            raise ValueError("Pairing request expired; refresh pending requests")
        secret = requests[index - 1].get("pair_secret")
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
