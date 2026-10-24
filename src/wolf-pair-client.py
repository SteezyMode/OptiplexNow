#!/usr/bin/env python3
"""Pair owner Moonlight through a verified Tailscale host, or legacy owner SSH.

The preferred fixed-port Tailscale broker is opt-in and host-owner-only.
Identity denials and malformed replies never fall back to administrator SSH.
Never exposes Wolf pairing secrets, arbitrary Docker APIs or an SSH password.
"""
import argparse
import http.client
import ipaddress
import json
import re
import subprocess
import sys

HOST_HELPER = "/usr/local/libexec/optiplex-now/wolf-pair-local"
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$", re.I)
HOST_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,252}$", re.I)


def validated(host, user):
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not HOST_RE.fullmatch(host) or ".." in host:
            raise ValueError("Invalid host")
    if not USER_RE.fullmatch(user):
        raise ValueError("Invalid SSH user")


def invoke(host, user, action, payload=None):
    validated(host, user)
    if action not in ("pending", "pending-text", "pair", "owner-status"):
        raise ValueError("Unsupported action")
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
            "-o", "StrictHostKeyChecking=yes", "-l", user, "--", host,
            HOST_HELPER, "pending" if action == "pending-text" else action]
    p = subprocess.run(argv, input=json.dumps(payload).encode() if payload else b"",
                       capture_output=True, timeout=15, check=False)
    if p.returncode:
        raise RuntimeError("Wolf pairing unavailable; check trusted SSH and host helper installation")
    response = json.loads(p.stdout)
    if not isinstance(response, dict) or response.get("success") is not True:
        raise RuntimeError("Wolf pairing request failed")
    return response



PAIR_PORT = 18793
PAIR_PENDING_ROUTE = "/v1/owner/wolf-pair/pending"
PAIR_APPROVE_ROUTE = "/v1/owner/wolf-pair/approve"
TAILNET = ipaddress.ip_network("100.64.0.0/10")


def invoke_tailnet(host, action, payload=None, *, connection=http.client.HTTPConnection):
    """Owner-only, fixed API PIN transport without client SSH credentials."""
    try:
        value = ipaddress.ip_address(host)
    except (TypeError, ValueError):
        raise ValueError("Only direct Tailscale IPv4 is supported") from None
    if (value.version != 4 or value not in TAILNET or
            str(value) == "100.100.100.100"):
        raise ValueError("Only direct Tailscale IPv4 is supported")
    if action not in ("pending", "pending-text", "pair"):
        raise ValueError("Unsupported Tailscale Wolf action")
    if action == "pair":
        if (not isinstance(payload, dict) or set(payload) !=
                {"index", "client_ip", "pin"}
                or type(payload["index"]) is not int or payload["index"] < 1
                or payload["client_ip"] != host
                or not isinstance(payload["pin"], str)
                or not 4 <= len(payload["pin"]) <= 12
                or not all("0" <= x <= "9" for x in payload["pin"])):
            raise ValueError("Invalid Wolf pairing payload")
    elif payload is not None:
        raise ValueError("Unexpected Wolf pending payload")
    client = connection(host, PAIR_PORT, timeout=15)
    try:
        if action == "pair":
            client.request("POST", PAIR_APPROVE_ROUTE,
                           body=json.dumps(payload, separators=(",", ":")).encode(),
                           headers={"Content-Type": "application/json",
                                    "Accept": "application/json"})
        else:
            client.request("GET", PAIR_PENDING_ROUTE,
                           headers={"Accept": "application/json"})
        reply = client.getresponse()
        raw = reply.read(4097)
        if reply.status != 200 or len(raw) > 4096:
            raise RuntimeError("Owner Wolf pairing denied or unavailable")
        result = json.loads(raw)
        if (not isinstance(result, dict) or result.get("success") is not True):
            raise RuntimeError("Wolf pairing request not confirmed")
        if action == "pair":
            if set(result) != {"success"}:
                raise ValueError("Unexpected Wolf pairing reply")
        else:
            clients = result.get("clients")
            if (set(result) != {"success", "clients"} or
                    not isinstance(clients, list) or len(clients) > 1):
                raise ValueError("Invalid Wolf pending reply")
            for item in clients:
                if (not isinstance(item, dict)
                        or set(item) != {"index", "client_ip"}
                        or type(item["index"]) is not int or item["index"] < 1
                        or item["client_ip"] != host):
                    raise ValueError("Unexpected Wolf pending device")
        return result
    finally:
        client.close()


def invoke_preferred(host, user, action, payload=None):
    """Don't bypass an explicit identity denial through administrator SSH."""
    try:
        return invoke_tailnet(host, action, payload)
    except ConnectionRefusedError:
        # Compatibility for owners who have not installed the optional host
        # broker. This requires existing trusted admin SSH, never provisions it.
        return invoke(host, user, action, payload)
    except ValueError as exc:
        if str(exc) == "Only direct Tailscale IPv4 is supported":
            return invoke(host, user, action, payload)
        raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pending", "pending-text", "pair"))
    parser.add_argument("host")
    parser.add_argument("user")
    args = parser.parse_args()
    payload = json.load(sys.stdin) if args.action == "pair" else None
    if args.action == "pair":
        if not isinstance(payload, dict) or set(payload) != {"index", "client_ip", "pin"}:
            raise ValueError("Invalid pairing request")
    response = invoke_preferred(args.host, args.user, args.action, payload)
    if args.action == "pending-text":
        for client in response.get("clients", []):
            index, address = client.get("index"), client.get("client_ip")
            if type(index) is int and isinstance(address, str):
                try:
                    ipaddress.ip_address(address)
                except ValueError:
                    continue
                print(f"{index}\t{address}")
    else:
        print(json.dumps(response))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        sys.exit(1)
