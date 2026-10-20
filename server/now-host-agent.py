#!/usr/bin/env python3
"""Experimental read-only NOW host presence endpoint, on the Tailscale IPv4 only.

No service install, control operations, pairing or public WAN listeners. The
operator must explicitly invoke --serve; packaging never starts this process.
"""
import argparse
import hashlib
import http.server
import ipaddress
import json
import re
import subprocess

PORT = 18791
MAX_REPLY_BYTES = 1024
TAILNET = ipaddress.ip_network("100.64.0.0/10")
MAGIC_DNS_IP = ipaddress.ip_address("100.100.100.100")


def tailscale_json(args, runner=None):
    """Run one fixed Tailscale read-only subcommand without a shell."""
    if runner is None:
        runner = subprocess.run
    result = runner(["tailscale", *args], capture_output=True, text=True,
                    timeout=3, check=False)
    if result.returncode:
        raise RuntimeError("Tailscale command unavailable")
    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError("Invalid Tailscale response")
    return data


def tailnet_ipv4(value):
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return None
    return str(addr) if addr.version == 4 and addr in TAILNET and addr != MAGIC_DNS_IP else None


def host_identity(status, name="NOW Server", backend="unknown"):
    """Derive a display-only node marker; not a signed host identity."""
    if status.get("BackendState") != "Running":
        raise ValueError("Sign in to Tailscale on this server before starting NOW discovery")
    node = status.get("Self")
    if not isinstance(node, dict):
        raise ValueError("Tailscale does not report this machine")
    identity = node.get("StableID") or node.get("ID")
    if not isinstance(identity, (str, int)) or not str(identity).strip():
        raise ValueError("Tailscale node identity unavailable")
    addresses = [tailnet_ipv4(v) for v in node.get("TailscaleIPs", [])]
    addresses = [v for v in addresses if v]
    if not addresses:
        raise ValueError("No usable local Tailscale IPv4 address")
    if backend not in ("sunshine", "wolf", "unknown"):
        raise ValueError("Unsupported backend")
    if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9 ._-]{0,47}", name):
        raise ValueError("Invalid host display name")
    # This deterministic marker lets another enrolled Tailscale device compare
    # the response with its own peer inventory; it is NOT a crypto signature.
    marker = hashlib.sha256(("now-node-v1:" + str(identity)).encode()).hexdigest()[:32]
    return addresses[0], {
        "service": "now-host",
        "protocol": 1,
        "server_id": marker,
        "name": name,
        "backend": backend,
        "pairing": "not_implemented",
    }


def peer_authorized(address, runner=None):
    """Fail closed unless tailscaled WhoIs associates the peer with its IP."""
    address = tailnet_ipv4(address)
    if address is None:
        return False
    try:
        who = tailscale_json(["whois", "--json", address], runner=runner)
        node = who.get("Node")
        if not isinstance(node, dict) or not (node.get("StableID") or node.get("ID")):
            return False
        # Different releases may return IPs as Addresses or AllowedIPs.
        ips = node.get("Addresses") or node.get("AllowedIPs") or []
        if not isinstance(ips, list):
            return False
        for raw in ips:
            try:
                if ipaddress.ip_address(address) in ipaddress.ip_network(raw, strict=False):
                    return True
            except ValueError:
                continue
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        pass
    return False


def make_handler(payload, authorize=peer_authorized):
    class DiscoveryHandler(http.server.BaseHTTPRequestHandler):
        server_version = "NOW-discovery-prototype"
        sys_version = ""

        def setup(self):
            super().setup()
            # Bound a slow or abusive tailnet peer's connection lifetime.
            self.connection.settimeout(2)

        def do_GET(self):
            if self.path != "/v1/discover":
                self.send_error(404, "Not found")
                return
            if not authorize(self.client_address[0]):
                self.send_error(403, "Forbidden")
                return
            encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
            if len(encoded) > MAX_REPLY_BYTES:
                self.send_error(500, "Response unavailable")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):
            self.send_error(405, "Read-only endpoint")

        def log_message(self, fmt, *args):
            # Avoid IPs, tokens and client paths in user-visible logs.
            pass

    return DiscoveryHandler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Experimental NOW host discovery (read only)")
    parser.add_argument("--serve", action="store_true",
                        help="Explicitly start a foreground Tailscale-only discovery endpoint")
    parser.add_argument("--backend", choices=("unknown", "wolf", "sunshine"),
                        default="unknown", help="Advisory backend label only")
    parser.add_argument("--name", default="NOW Server", help="Non-sensitive display name")
    args = parser.parse_args(argv)
    try:
        address, payload = host_identity(tailscale_json(["status", "--json"]),
                                         name=args.name, backend=args.backend)
        if not args.serve:
            print("NOW discovery ready on " + address + ":" + str(PORT))
            print("Read-only prototype. Use --serve explicitly to listen. No changes made.")
            return 0
        # Binds to the Tailscale node address only. Never 0.0.0.0 or LAN.
        with http.server.HTTPServer((address, PORT), make_handler(payload)) as server:
            server.timeout = 2
            print("NOW discovery listening on Tailscale only (" + str(PORT) + ")")
            server.serve_forever(poll_interval=0.25)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        # Never print arbitrary Tailscale stderr or response bodies.
        print("NOW host discovery unavailable: verify Tailscale status and port availability.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
