#!/usr/bin/env python3
"""Find verified NOW host presence endpoints among already-authorized tailnet peers.

Read-only. Does not enroll Tailscale, share devices, pair Moonlight or connect to
SSH. Sends short GET requests only to Tailscale peer IPs from local tailscaled.
Never uses HTTP(S)_PROXY or scans public/LAN networks.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import http.client
import ipaddress
import json
import re
import subprocess
import sys

PORT = 18791
MAX_PEERS = 24
MAX_BODY = 1024
NETWORK = ipaddress.ip_network("100.64.0.0/10")
DNS_ADDR = ipaddress.ip_address("100.100.100.100")


def tailnet_address(raw):
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return None
    return str(ip) if ip.version == 4 and ip in NETWORK and ip != DNS_ADDR else None


def peers_to_check(status, limit=MAX_PEERS):
    if status.get("BackendState") != "Running":
        raise ValueError("Connect Tailscale before discovering NOW hosts")
    nodes = status.get("Peer") or {}
    if not isinstance(nodes, dict):
        return []
    choices = []
    seen = set()
    for item in nodes.values():
        if not isinstance(item, dict) or item.get("Online") is not True:
            continue
        node_id = item.get("StableID") or item.get("ID")
        if not isinstance(node_id, (str, int)) or not str(node_id):
            continue
        for raw in item.get("TailscaleIPs") or []:
            ip = tailnet_address(raw)
            if ip and ip not in seen:
                seen.add(ip)
                choices.append((ip, hashlib.sha256(
                    ("now-node-v1:" + str(node_id)).encode()).hexdigest()[:32]))
                break
        if len(choices) >= limit:
            break
    return choices


def probe(ip, expected_id, *, connector=None):
    """No proxies. Discovery response must match the observed Tailscale node."""
    if not tailnet_address(ip):
        return None
    if connector is None:
        connector = http.client.HTTPConnection
    connection = connector(ip, PORT, timeout=0.9)
    try:
        connection.request("GET", "/v1/discover", headers={
            "Accept": "application/json", "Connection": "close"})
        response = connection.getresponse()
        if response.status != 200:
            return None
        if response.getheader("Content-Type", "").split(";")[0].strip() != "application/json":
            return None
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            return None
        obj = json.loads(body)
        if not isinstance(obj, dict):
            return None
        if obj.get("service") != "now-host" or type(obj.get("protocol")) is not int or obj["protocol"] != 1:
            return None
        if obj.get("server_id") != expected_id:
            return None
        name, backend = obj.get("name"), obj.get("backend")
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9 ._-]{0,47}", name):
            return None
        if backend not in ("unknown", "wolf", "sunshine"):
            return None
        return {"ip": ip, "server_id": expected_id, "name": name, "backend": backend}
    except (OSError, ValueError, TypeError, KeyError, TimeoutError, http.client.HTTPException):
        return None
    finally:
        connection.close()


def discover(status, *, probe_fn=probe, max_workers=6):
    results = []
    choices = peers_to_check(status)
    if not choices:
        return results
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(probe_fn, ip, node_id): ip for ip, node_id in choices}
        for future in as_completed(futures):
            try:
                item = future.result()
            except Exception:
                continue
            if item:
                results.append(item)
    return sorted(results, key=lambda v: (v["name"].casefold(), v["ip"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only NOW host discovery")
    parser.add_argument("--json", action="store_true", help="Emit sanitized JSON")
    options = parser.parse_args(argv)
    try:
        result = subprocess.run(["tailscale", "status", "--json"],
                                capture_output=True, text=True, timeout=4, check=False)
        if result.returncode:
            raise ValueError("Tailscale is not connected")
        nodes = json.loads(result.stdout)
        matches = discover(nodes)
        if options.json:
            print(json.dumps({"protocol": 1, "hosts": matches}, sort_keys=True))
        else:
            for server in matches:
                label = "{} ({})".format(server["name"], server["backend"].title())
                print("{}\t{}\t{}".format(server["ip"], label, server["server_id"]))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired, TypeError):
        print("NOW discovery unavailable. Sign into Tailscale and retry.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
