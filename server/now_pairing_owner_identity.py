"""Pin NOW's owner identity during trusted SERVER installation, never via HTTP.

The server installer should populate this file after a privileged,
authenticated initial claim. Incoming devices cannot enroll an owner,
replace the stored identity, or supply a recipient email address.
"""
import os
import json
import ipaddress
import subprocess
import re
import stat

OWNER_ID = re.compile(r"[1-9][0-9]{0,19}\Z")


def parse_owner_user_id(data):
    if not isinstance(data, str):
        raise ValueError("Invalid owner identity")
    value = data.strip()
    if not OWNER_ID.fullmatch(value):
        raise ValueError("Invalid owner identity")
    return value


def load_pinned_owner(path):
    """Reject foreign, shared, symlinked, relative and empty owner files."""
    if not isinstance(path, str) or not os.path.isabs(path):
        raise ValueError("Owner file must have an absolute path")
    metadata = os.lstat(path)
    if (not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077):
        raise PermissionError("Owner identity must be private and service-owned")
    if metadata.st_size < 1 or metadata.st_size > 128:
        raise ValueError("Invalid owner identity file")
    # O_NOFOLLOW guards against swapping the file for a symlink after lstat.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        current = os.fstat(fd)
        if (current.st_dev != metadata.st_dev or current.st_ino != metadata.st_ino
                or not stat.S_ISREG(current.st_mode)
                or current.st_uid != os.geteuid()
                or stat.S_IMODE(current.st_mode) & 0o077):
            raise PermissionError("Owner file changed or is not private")
        value = os.read(fd, 129)
        if len(value) > 128:
            raise ValueError("Owner file too long")
        return parse_owner_user_id(value.decode("ascii"))
    finally:
        os.close(fd)


def owner_from_local_tailscale(*, runner=subprocess.run):
    """Trusted host bootstrap for an already user-enrolled Tailscale server.

    Used only at explicit SERVER-role activation, never as a request handler.
    Tagged or shared/unnamed nodes cannot claim owner identity automatically.
    """
    try:
        outcome = runner(["tailscale", "status", "--json"], capture_output=True,
                         text=True, timeout=3, check=False)
        if outcome.returncode or len(outcome.stdout) > 524288:
            raise ValueError("Tailscale status unavailable")
        status = json.loads(outcome.stdout)
        if not isinstance(status, dict) or status.get("BackendState") != "Running":
            raise ValueError("Tailscale server is not connected")
        node = status.get("Self")
        if not isinstance(node, dict) or node.get("Tags") or node.get("ShareeNode"):
            raise ValueError("Server identity is not a personal owner node")
        user_id = parse_owner_user_id(str(node.get("UserID", "")))
        ips = node.get("TailscaleIPs")
        network = ipaddress.ip_network("100.64.0.0/10")
        if not isinstance(ips, list):
            raise ValueError("Server has no Tailnet identity")
        valid_ips = []
        for raw in ips:
            try:
                ip = ipaddress.ip_address(raw)
            except (TypeError, ValueError):
                continue
            if ip.version == 4 and ip in network and str(ip) != "100.100.100.100":
                valid_ips.append(str(ip))
        if len(set(valid_ips)) != 1:
            raise ValueError("Server has no unique Tailscale IPv4 address")
        return user_id
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired) as err:
        raise ValueError("Cannot establish registered local Tailscale owner") from err
