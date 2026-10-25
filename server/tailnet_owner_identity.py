"""Narrow, fail-closed Tailscale identity checks for owner-only enrollment.

No listening socket, user enrollment, SSH, Docker or Wolf interaction here.
A trusted host installer must separately pin the owner Tailscale numeric user ID.
"""
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess

TAILNET = ipaddress.ip_network("100.64.0.0/10")
NUMERIC_ID = re.compile(r"[1-9][0-9]{0,19}\Z")


def tailnet_ipv4(value):
    try:
        address = ipaddress.ip_address(value)
    except (TypeError, ValueError):
        return None
    if address.version != 4 or address not in TAILNET or str(address) == "100.100.100.100":
        return None
    return str(address)


def parse_owner_id(raw):
    if not isinstance(raw, str):
        raise ValueError("Invalid owner ID")
    value = raw.strip()
    if NUMERIC_ID.fullmatch(value) is None:
        raise ValueError("Invalid owner ID")
    return value


def pinned_owner_id(path):
    """Only a private host-installation-controlled owner file can set identity."""
    pathname = Path(path)
    if not pathname.is_absolute() or pathname.is_symlink():
        raise ValueError("Unsafe pinned owner file")
    fd = os.open(pathname, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or info.st_size < 1 or info.st_size > 128):
            raise ValueError("Unsafe pinned owner file")
        value = os.read(fd, 129)
        if len(value) > 128:
            raise ValueError("Oversized pinned owner ID")
        return parse_owner_id(value.decode("ascii"))
    finally:
        os.close(fd)


def pinned_approver_node_id(path):
    """Pin an existing owner's trusted phone StableID from host-local setup.

    A signed-in computer on the same Tailscale *account* is not automatically
    trusted to approve itself. Only a separately preapproved phone node may
    open approval pages or POST an owner grant.
    """
    pathname = Path(path)
    if not pathname.is_absolute() or pathname.is_symlink():
        raise ValueError("Unsafe pinned owner phone file")
    fd = os.open(pathname, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or stat.S_IMODE(meta.st_mode) != 0o600
                or meta.st_nlink != 1 or not 1 <= meta.st_size <= 128):
            raise ValueError("Unsafe pinned owner phone file")
        raw = os.read(fd, 129).decode("ascii").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", raw):
            raise ValueError("Invalid owner phone StableID")
        return raw
    finally:
        os.close(fd)


def peer_from_whois(source, result):
    """Return verified (user ID, node ID), never names, IP alone or headers."""
    address = tailnet_ipv4(source)
    if address is None or not isinstance(result, dict):
        return None
    node, user = result.get("Node"), result.get("UserProfile")
    if not isinstance(node, dict) or not isinstance(user, dict) or node.get("Tags"):
        return None
    addresses = node.get("Addresses")
    if not isinstance(addresses, list):
        return None
    matched = False
    for item in addresses:
        try:
            block = ipaddress.ip_network(item, strict=False)
            if block.version == 4 and block.prefixlen == 32 and str(block.network_address) == address:
                matched = True
        except (TypeError, ValueError):
            pass
    if not matched:
        return None
    raw_user = user.get("ID")
    if isinstance(raw_user, bool) or not isinstance(raw_user, (str, int)):
        return None
    try:
        user_id = parse_owner_id(str(raw_user))
    except ValueError:
        return None
    node_owner = node.get("User")
    if node_owner is not None and str(node_owner) != user_id:
        return None
    node_id = node.get("StableID") or node.get("ID")
    if isinstance(node_id, bool) or not isinstance(node_id, (str, int)):
        return None
    node_id = str(node_id)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", node_id):
        return None
    return user_id, node_id


def verify_owner_peer(source_ip, pinned_id, *, runner=subprocess.run):
    if tailnet_ipv4(source_ip) is None:
        return None
    try:
        response = runner(["tailscale", "whois", "--json", source_ip],
                          capture_output=True, text=True, timeout=3, check=False)
        if response.returncode or not isinstance(response.stdout, str) or len(response.stdout) > 65536:
            return None
        peer = peer_from_whois(source_ip, json.loads(response.stdout))
        return peer if peer is not None and peer[0] == pinned_id else None
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        return None


def own_tailnet_ipv4(*, runner=subprocess.run):
    try:
        response = runner(["tailscale", "status", "--json"],
                          capture_output=True, text=True, timeout=3, check=False)
        if response.returncode or not isinstance(response.stdout, str) or len(response.stdout) > 524288:
            raise ValueError("Tailnet unavailable")
        data = json.loads(response.stdout)
        if not isinstance(data, dict) or data.get("BackendState") != "Running":
            raise ValueError("Tailnet not connected")
        node = data.get("Self")
        addresses = node.get("TailscaleIPs") if isinstance(node, dict) else None
        if not isinstance(addresses, list):
            raise ValueError("No host Tailscale addresses")
        unique = {ip for raw in addresses if (ip := tailnet_ipv4(raw))}
        if len(unique) != 1:
            raise ValueError("Host Tailscale IPv4 unavailable or ambiguous")
        return unique.pop()
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Cannot verify local Tailscale address") from exc
