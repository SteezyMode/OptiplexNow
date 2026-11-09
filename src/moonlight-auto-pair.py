#!/usr/bin/env python3
"""Owner-only, opt-in Moonlight pairing coordinator for a Tailscale host.

No GUI or installer side effects. The HOST must already run the existing
opt-in tailnet_enrollment broker with *fresh owner Wolf pairing* enabled.
Only the broker can authorize a Tailscale owner peer; this helper cannot
enroll a Bruiser device, grant managed Games/Downloads or trust a shared node.
Not invoked by the shipped launcher until hardware validation.
"""
import argparse
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import time

TAILNET = ipaddress.ip_network("100.64.0.0/10")
BROKER_CLIENT = Path(__file__).with_name("wolf-pair-client.py")


def tailnet_address(address):
    try:
        ip = ipaddress.ip_address(address)
    except (TypeError, ValueError):
        raise ValueError("An OptiPlex Tailscale IPv4 address is required") from None
    if ip.version != 4 or ip not in TAILNET or str(ip) == "100.100.100.100":
        raise ValueError("An OptiPlex Tailscale IPv4 address is required")
    return str(ip)


def own_tailnet_address(*, runner=subprocess.run):
    result = runner(["tailscale", "status", "--json"], capture_output=True,
                    text=True, timeout=4, check=False)
    if result.returncode:
        raise ValueError("Tailscale is not connected")
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or data.get("BackendState") != "Running":
        raise ValueError("Tailscale is not connected")
    node = data.get("Self")
    addresses = node.get("TailscaleIPs") if isinstance(node, dict) else None
    if not isinstance(addresses, list):
        raise ValueError("Tailscale identity is unavailable")
    valid = set()
    for value in addresses:
        try:
            valid.add(tailnet_address(value))
        except ValueError:
            continue
    if len(valid) != 1:
        raise ValueError("Cannot identify this Tailscale device")
    return valid.pop()


def moonlight_command(mode, appimage=None):
    if mode == "native":
        if not shutil.which("moonlight"):
            raise ValueError("Moonlight Qt is not installed")
        return ["moonlight"]
    if mode == "flatpak":
        if not shutil.which("flatpak"):
            raise ValueError("Flatpak is not installed")
        return ["flatpak", "run", "com.moonlight_stream.Moonlight"]
    if mode == "appimage":
        path = Path(appimage or "")
        if (not path.is_absolute() or path.is_symlink() or not path.is_file()
                or not os.access(path, os.X_OK)):
            raise ValueError("Choose an installed executable Moonlight AppImage")
        return [str(path)]
    raise ValueError("Unsupported Moonlight mode")


def owner_wolf(host, action, payload=None):
    """Call only the existing owner/Tailscale-identity-checked Wolf endpoint."""
    spec = importlib.util.spec_from_file_location("now_wolf_pair_client", BROKER_CLIENT)
    if not spec or not spec.loader:
        raise ValueError("Packaged owner Wolf bridge missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # NO fallback to unrestricted SSH if this endpoint is absent or denied.
    return module.invoke_tailnet(host, action, payload)


def _paired(host, moonlight, runner):
    # Upstream Moonlight Qt returns nonzero when host is not paired. A successful
    # 'list' is positive evidence of an existing paired Moonlight identity.
    result = runner([*moonlight, "list", host], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=15, check=False)
    return result.returncode == 0


def ensure_paired(host, own_ip, moonlight, *, invoke=owner_wolf,
                  runner=subprocess.run, spawn=subprocess.Popen,
                  clock=time.monotonic, sleeper=time.sleep,
                  pin_factory=lambda: f"{secrets.randbelow(10000):04d}"):
    """Pair only a fresh, verified owner node. Never grant Bruiser permissions."""
    host = tailnet_address(host)
    own_ip = tailnet_address(own_ip)
    if host == own_ip:
        raise ValueError("Host cannot pair its own local Wolf client")
    if _paired(host, moonlight, runner):
        return "ALREADY_PAIRED"

    # This endpoint must be explicitly enabled on the host. It validates the
    # owner's pinned Tailscale user ID and records all preexisting Wolf pending
    # secrets so a stale or different client's request cannot be approved.
    prepared = invoke(host, "prepare")
    if prepared != {"success": True, "status": "prepared"}:
        raise ValueError("Owner-only fresh pairing is unavailable")

    pin = pin_factory()
    if (not isinstance(pin, str) or len(pin) != 4
            or not pin.isascii() or not pin.isdecimal()):
        raise ValueError("Invalid generated Moonlight PIN")
    # Moonlight Qt supports an existing, predefined PIN via its own CLI.
    # The PIN is not a password and is valid for this single pairing attempt.
    process = spawn([*moonlight, "pair", host, "--pin", pin],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, close_fds=True)
    succeeded = False
    try:
        deadline = clock() + 30
        while clock() < deadline:
            if process.poll() is not None and process.returncode != 0:
                raise ValueError("Moonlight pairing exited before approval")
            response = invoke(host, "pending")
            if not isinstance(response, dict) or response.get("success") is not True:
                raise ValueError("Wolf pending request unavailable")
            entries = response.get("clients")
            if not isinstance(entries, list) or len(entries) > 1:
                raise ValueError("Wolf pairing request is ambiguous")
            if entries:
                entry = entries[0]
                if (not isinstance(entry, dict)
                        or set(entry) != {"index", "client_ip"}
                        or type(entry["index"]) is not int
                        or not 1 <= entry["index"] <= 32
                        or entry["client_ip"] != own_ip):
                    raise ValueError("Wolf pairing request differs from this device")
                approved = invoke(host, "pair", {"index": entry["index"],
                                                  "client_ip": own_ip, "pin": pin})
                if approved != {"success": True}:
                    raise ValueError("Wolf rejected this pairing")
                break
            sleeper(0.4)
        else:
            raise ValueError("No fresh pairing request from this Tailscale device")

        if process.wait(timeout=25) != 0:
            raise ValueError("Moonlight did not finish pairing successfully")
        if not _paired(host, moonlight, runner):
            raise ValueError("Moonlight did not verify a paired host")
        succeeded = True
        return "PAIRED"
    finally:
        # Only stop the subprocess started by THIS attempt, never an existing
        # Moonlight stream or a Wolf session.
        if not succeeded and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="The configured OptiPlex Tailscale IPv4")
    parser.add_argument("--mode", choices=("native", "flatpak", "appimage"),
                        default="native")
    parser.add_argument("--appimage", default=None)
    args = parser.parse_args(argv)
    own_ip = own_tailnet_address()
    command = moonlight_command(args.mode, args.appimage)
    print(ensure_paired(args.host, own_ip, command))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError,
            subprocess.TimeoutExpired, json.JSONDecodeError):
        print("PAIRING_UNAVAILABLE")
        sys.exit(1)
