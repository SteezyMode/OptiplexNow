"""Owner-bound, exact-hash qBittorrent actions with guarded optional data deletion.

The restricted SSH broker must authenticate the device before calling this.
Only a verified local VPN-bound qBittorrent endpoint may receive operations.
"""
import json
import re
import subprocess
from urllib.parse import urlencode
from download_destinations import _mounts
from download_inventory import InventoryError
from download_queue import locate_verified_downloader

OPERATIONS = {
    "pause": "stop",      # qBittorrent 5.1 Web API names
    "resume": "start",
    "reannounce": "reannounce",
    "recheck": "recheck",
    "remove": "delete",
    "remove_delete": "delete",  # Explicit owner confirmation and scoped path checks.
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
            not isinstance(torrents[0].get("hash"), str) or
            torrents[0]["hash"].lower() != torrent_hash):
        raise InventoryError("Torrent no longer exists")
    fields = {"hashes": torrent_hash}
    if operation in ("remove", "remove_delete"):
        fields["deleteFiles"] = "true" if operation == "remove_delete" else "false"
    if operation == "remove_delete":
        # Delete only inside a currently verified writable qBittorrent
        # storage mount. Never delete a mount root or a service/config path.
        # Filesystem mounts are discovered, not supplied by the client.
        _, verified_gateway, verified_port, mounts = _mounts(runner=runner)
        if (verified_gateway, verified_port) != (gateway, port):
            raise InventoryError("Downloader binding changed")
        info = torrents[0]
        save_path, content_path = info.get("save_path"), info.get("content_path")
        if not isinstance(save_path,str) or not isinstance(content_path,str):
            raise InventoryError("Cannot verify torrent data location")
        def clean(path):
            return (path.startswith("/") and
                    all(part not in (".","..") for part in path.split("/")[1:]) and
                    "//" not in path and "\\" not in path)
        if not clean(save_path) or not clean(content_path):
            raise InventoryError("Untrusted torrent data location")
        approved = False
        for mount in mounts.values():
            mount_root = mount["target"].rstrip("/")
            if ((save_path == mount_root or
                 save_path.startswith(mount_root + "/")) and
                    content_path.startswith(save_path.rstrip("/") + "/") and
                    content_path.startswith(mount_root + "/")):
                approved = True
                break
        if not approved:
            raise InventoryError("Torrent data is outside writable downloader storage")
    action = OPERATIONS[operation]
    argv = ["docker", "exec", gateway, "wget", "-q", "-T", "5", "-O", "-",
            "--header", f"Referer: http://127.0.0.1:{port}/",
            "--post-data=" + urlencode(fields), base + action]
    try:
        response = runner(argv, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InventoryError("Torrent operation unavailable") from exc
    if (response.returncode or not isinstance(response.stdout, bytes)
            or len(response.stdout) > 1024
            or response.stdout.strip() not in (b"", b"Ok.")):
        raise InventoryError("Torrent operation failed")
    return {"status": "submitted", "operation": operation}
