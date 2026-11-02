#!/usr/bin/env python3
"""Link an EXISTING DroppedNeedle owner to the approved NOW host.

Run locally in an interactive host terminal only. This never resets DN, issues
client credentials, changes SSH keys, or grants a Music device permission.
The password is read with getpass and stored in the existing private host
owner-link format (0600) only after successful login.
"""
from __future__ import annotations

import argparse
import getpass
import ipaddress
import os
from pathlib import Path
import socket
import sys
from urllib.parse import urlsplit

from owner_access import OwnerStore, PolicyError
from owner_games_ssh import _read_private_config
from owner_music_ssh import ACCOUNT_FILE, read_owner_music_account
from music_owner_bootstrap import _private_config_dir, _write_once
from music_device_provision import DroppedNeedleAPI, ProvisionError


def _host_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ProvisionError("Invalid Music server URL.")
    if parts.path not in ("", "/"):
        raise ProvisionError("Music server must be a base URL.")
    # Never submit an owner password over unauthenticated arbitrary HTTP.
    if parts.scheme == "http":
        try:
            target = ipaddress.ip_address(parts.hostname)
        except ValueError:
            raise ProvisionError("HTTP Music URL must use a host-local IP.") from None
        if not target.is_loopback:
            # DroppedNeedle may be bound only to the server's own Tailscale IP.
            # Confirm that the requested interface address belongs to THIS host.
            import subprocess
            result = subprocess.run(["ip", "-j", "addr", "show"], capture_output=True,
                                    timeout=5, check=True, text=True)
            import json
            local_ips = {
                item["local"] for interface in json.loads(result.stdout)
                for item in interface.get("addr_info", [])
                if item.get("family") == "inet" and "local" in item
            }
            if str(target) not in local_ips or not target in ipaddress.ip_network("100.64.0.0/10"):
                raise ProvisionError("HTTP Music URL must be this host's Tailscale interface.")
    return url.rstrip("/")


def link_existing(*, url, username, password, account_path=ACCOUNT_FILE):
    base = _host_url(url)
    cfg = _read_private_config()
    if not cfg["enabled"] or not cfg["legacy_links_reviewed"]:
        raise PolicyError("Approve this host in Bruiser before linking Music.")
    store = OwnerStore(cfg["state_dir"])
    with store.locked() as fd:
        policy = store.read(fd)
        if policy is None or len(policy["principals"]) != 1 or policy["principals"][0]["role"] != "owner":
            raise PolicyError("Bruiser owner policy is unavailable.")
        principal = policy["principals"][0]["id"]
        account_path = Path(account_path)
        _private_config_dir(account_path)
        if account_path.exists() or account_path.is_symlink():
            raise PolicyError("Music owner is already linked; nothing was overwritten.")
        api = DroppedNeedleAPI(base)
        status = api.call("GET", "/auth/setup/status")
        if status.get("required") is not False:
            raise ProvisionError("Music is not initialized; existing-owner link refused.")
        token, user_id = api.login(username, password)
        del token, user_id
        record = {
            "version": 1, "base_url": base, "owner_principal_id": principal,
            "username": username, "password": password,
        }
        _write_once(account_path, record)
        read_owner_music_account(account_path)
    return "Existing Music owner linked. No device grants were changed."


def main():
    parser = argparse.ArgumentParser(description="Private existing-owner Music account link")
    parser.add_argument("--url", required=True, help="Host-local DroppedNeedle URL")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        print("Run in an interactive host terminal; no passwords through pipes.")
        return 1
    username = input("Existing DroppedNeedle username: ").strip()
    password = getpass.getpass("Existing DroppedNeedle password (not displayed): ")
    try:
        print(link_existing(url=args.url, username=username, password=password))
        return 0
    except (ProvisionError, PolicyError, OSError, ValueError):
        print("Music owner link not completed. Existing account and host are unchanged.")
        return 1
    finally:
        password = ""


if __name__ == "__main__":
    sys.exit(main())
