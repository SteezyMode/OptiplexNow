"""Owner-bound, single-torrent qBittorrent management with no file deletion.

The restricted SSH broker must authenticate the device before calling this.
Only a verified local VPN-bound qBittorrent endpoint may receive operations.
"""
import json
import re
import subprocess
from urllib.parse import urlencode
from download_inventory import InventoryError
from download_queue import locate_verified_downloader

OPERATIONS = {
    "pause": "stop",      # qBittorrent 5.1 Web API names
    "resume": "start",
    "reannounce": "reannounce",
    "recheck": "recheck",
    "remove": "delete",
}
HASH = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?\Z")


def checked_hash(value):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise InventoryError("Invalid torrent selector")
    return value.lower()


def manage_torrent(operation, torrent_hash, *, runner=subprocess.run):
    if operation not in OPERATIONS:
        raise InventoryError("Unsupported torrent operation")
    torrent_hash = checked_hash(torrent_hash)
    gateway, port = locate_verified_downloader(runner=runner)
    base = f"http://127.0.0.1:{port}/api/v2/torrents/"
    # Confirm this exact hash still exists; never select all or multiple.
    lookup = ["docker", "exec", gateway, "wget", "-q", "-T", "5",
              "-O", "-", base + "info?" + urlencode({"hashes": torrent_hash})]
    try:
        existing = runner(lookup, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InventoryError("Torrent lookup unavailable") from exc
    if (existing.returncode or not isinstance(existing.stdout, bytes)
            or len(existing.stdout) > 8192):
        raise InventoryError("Torrent lookup failed")
    try:
        torrents = json.loads(existing.stdout)
    except (UnicodeDecodeError, ValueError) as exc:
        raise InventoryError("Invalid torrent lookup") from exc
    if (not isinstance(torrents, list) or len(torrents) != 1 or
            not isinstance(torrents[0], dict) or
            torrents[0].get("hash", "").lower() != torrent_hash):
        raise InventoryError("Torrent no longer exists")
    fields = {"hashes": torrent_hash}
    if operation == "remove":
        fields["deleteFiles"] = "false"  # Never delete user media from NOW.
    action = OPERATIONS[operation]
    argv = ["docker", "exec", gateway, "wget", "-q", "-T", "5", "-O", "-",
            "--header", f"Referer: http://127.0.0.1:{port}/",
            "--post-data=" + urlencode(fields), base + action]
    try:
        response = runner(argv, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InventoryError("Torrent operation unavailable") from exc
    if (response.returncode or not isinstance(response.stdout, bytes)
            or len(response.stdout) > 1024):
        raise InventoryError("Torrent operation failed")
    return {"status": "submitted", "operation": operation}
