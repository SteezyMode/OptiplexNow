#!/usr/bin/env python3
"""Transport pairing requests to an explicitly provisioned NOW host over SSH.

Never passes pairing PINs in argv or exposes the Wolf API on a TCP port.
The host must have /usr/local/libexec/optiplex-now/wolf-pair-local installed.
"""
import argparse
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
    if action not in ("pending", "pair"):
        raise ValueError("Unsupported action")
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
            "-o", "StrictHostKeyChecking=yes", "-l", user, "--", host,
            HOST_HELPER, action]
    p = subprocess.run(argv, input=json.dumps(payload).encode() if payload else b"",
                       capture_output=True, timeout=15, check=False)
    if p.returncode:
        raise RuntimeError("Wolf pairing unavailable; check trusted SSH and host helper installation")
    response = json.loads(p.stdout)
    if not isinstance(response, dict) or response.get("success") is not True:
        raise RuntimeError("Wolf pairing request failed")
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pending", "pair"))
    parser.add_argument("host")
    parser.add_argument("user")
    args = parser.parse_args()
    payload = json.load(sys.stdin) if args.action == "pair" else None
    if args.action == "pair":
        if not isinstance(payload, dict) or set(payload) != {"index", "client_ip", "pin"}:
            raise ValueError("Invalid pairing request")
    print(json.dumps(invoke(args.host, args.user, args.action, payload)))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        sys.exit(1)
