#!/usr/bin/env python3
"""Report a compact, truthful local Tailscale state for the GTK wizard.

Never changes network settings, starts tailscaled or enrolls a device.
"""
import ipaddress
import json
import shutil
import subprocess


def classify(status):
    if not isinstance(status, dict):
        return "UNAVAILABLE"
    state = status.get("BackendState")
    if state in ("NeedsLogin", "NeedsMachineAuth"):
        return "SIGN_IN"
    if state != "Running":
        return "NOT_CONNECTED" if isinstance(state, str) else "UNAVAILABLE"
    node = status.get("Self")
    if not isinstance(node, dict):
        return "UNAVAILABLE"
    addresses = node.get("TailscaleIPs")
    if not isinstance(addresses, list):
        return "UNAVAILABLE"
    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
            if not parsed.is_unspecified and not parsed.is_loopback:
                return "CONNECTED"
        except (ValueError, TypeError):
            continue
    return "UNAVAILABLE"


def status():
    if not shutil.which("tailscale"):
        return "NOT_INSTALLED"
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"], capture_output=True,
            text=True, timeout=4, check=False
        )
        if result.returncode != 0:
            return "UNAVAILABLE"
        return classify(json.loads(result.stdout))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return "UNAVAILABLE"


if __name__ == "__main__":
    print(status())
