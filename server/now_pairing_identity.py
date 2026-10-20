"""Verify NOW pairing requesters with actual Tailscale WhoIs identity.

Never trust client JSON, HTTP headers, an address alone or routed subnets as
identity. Reject tagged/service nodes without a unique user profile.
"""
import ipaddress
import json
import subprocess

from now_pairing_requests import PeerIdentity

NETWORK = ipaddress.ip_network("100.64.0.0/10")
MAGIC_DNS = ipaddress.ip_address("100.100.100.100")


def tailnet_ipv4(raw):
    try:
        ip = ipaddress.ip_address(raw)
    except (TypeError, ValueError):
        return None
    if ip.version != 4 or ip not in NETWORK or ip == MAGIC_DNS:
        return None
    return str(ip)


def verified_peer_from_whois(source_ip, whois):
    """Construct a trusted peer only after exact assigned IP/account checks."""
    source_ip = tailnet_ipv4(source_ip)
    if source_ip is None or not isinstance(whois, dict):
        return None
    node = whois.get("Node")
    user = whois.get("UserProfile")
    if not isinstance(node, dict) or not isinstance(user, dict):
        return None
    # Tagged nodes have service identity rather than a normal owner account.
    # This first milestone supports explicitly user-owned devices only.
    if node.get("Tags"):
        return None
    addresses = node.get("Addresses")
    if not isinstance(addresses, list):
        return None
    matched = False
    for raw in addresses:
        try:
            block = ipaddress.ip_network(raw, strict=False)
            if (block.version == 4 and block.prefixlen == 32 and
                    str(block.network_address) == source_ip):
                matched = True
        except (TypeError, ValueError):
            continue
    if not matched:
        return None
    node_id = node.get("StableID") or node.get("ID")
    user_id = user.get("ID")
    if (isinstance(node_id, bool) or not isinstance(node_id, (int, str))
            or isinstance(user_id, bool) or not isinstance(user_id, (int, str))):
        return None
    # If provided, node.User must be the exact WhoIs user profile, too.
    owner_id = node.get("User")
    if owner_id is not None and str(owner_id) != str(user_id):
        return None
    try:
        return PeerIdentity(str(node_id), str(user_id))
    except ValueError:
        return None


def verify_tailscale_peer(source_ip, *, runner=None):
    """Fail closed. Never return raw daemon data or its stderr."""
    if tailnet_ipv4(source_ip) is None:
        return None
    if runner is None:
        runner = subprocess.run
    try:
        result = runner(["tailscale", "whois", "--json", source_ip],
                        capture_output=True, text=True, timeout=3, check=False)
        if result.returncode:
            return None
        return verified_peer_from_whois(source_ip, json.loads(result.stdout))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def own_tailnet_ipv4(*, runner=None):
    """Find this host's Tailscale bind address, never infer from client data."""
    if runner is None:
        runner = subprocess.run
    result = runner(["tailscale", "status", "--json"],
                    capture_output=True, text=True, timeout=3, check=False)
    if result.returncode:
        raise ValueError("Tailscale is unavailable")
    status = json.loads(result.stdout)
    if not isinstance(status, dict) or status.get("BackendState") != "Running":
        raise ValueError("Tailscale must be connected")
    node = status.get("Self")
    if not isinstance(node, dict):
        raise ValueError("No local Tailscale node")
    ips = node.get("TailscaleIPs")
    if not isinstance(ips, list):
        raise ValueError("No local Tailscale addresses")
    matches = [tailnet_ipv4(item) for item in ips]
    matches = [ip for ip in matches if ip]
    if len(set(matches)) != 1:
        raise ValueError("No unique local Tailscale IPv4 address")
    return matches[0]
