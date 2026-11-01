"""Read-only, owner-authorized per-torrent file listing from the VPN-bound qBittorrent.

No host filesystem paths, credentials, container IDs or raw qBittorrent JSON
reach the client. The restricted SSH owner gate authorizes before calling this.
"""
import json
import math
import re
import subprocess
from urllib.parse import urlencode

from download_inventory import InventoryError
from download_manage import checked_hash
from download_queue import locate_verified_downloader

MAX_BYTES = 262144
MAX_FILES = 120


def inspect_torrent_files(torrent_hash, *, runner=subprocess.run):
    torrent_hash = checked_hash(torrent_hash)
    gateway, port = locate_verified_downloader(runner=runner)
    url = (f"http://127.0.0.1:{port}/api/v2/torrents/files?" +
           urlencode({"hash": torrent_hash}))
    cmd = ["docker", "exec", gateway, "wget", "-q", "-T", "5", "-O", "-", url]
    try:
        response = runner(cmd, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InventoryError("Torrent file listing unavailable") from exc
    if (response.returncode or not isinstance(response.stdout, bytes) or
            len(response.stdout) > MAX_BYTES):
        raise InventoryError("Torrent file listing unavailable")
    try:
        records = json.loads(response.stdout)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InventoryError("Invalid torrent file listing") from exc
    if not isinstance(records, list) or len(records) > 10000:
        raise InventoryError("Unusable torrent file listing")
    files = []
    for item in records[:MAX_FILES]:
        if not isinstance(item, dict):
            raise InventoryError("Invalid file record")
        name, size, progress, priority = (item.get("name"), item.get("size"),
                                          item.get("progress"), item.get("priority"))
        if (not isinstance(name, str) or not 1 <= len(name) <= 220 or
                name.startswith("/") or "\\\\" in name or
                any(part in ("", ".", "..") for part in name.split("/")) or
                any(ord(c) < 32 or ord(c) == 127 for c in name) or
                type(size) is not int or not 0 <= size <= 2**63-1 or
                type(progress) not in (int, float) or
                not math.isfinite(progress) or not 0 <= progress <= 1 or
                type(priority) is not int or not 0 <= priority <= 7):
            raise InventoryError("Invalid torrent file metadata")
        files.append({"name": name, "size": size,
                      "progress_percent": round(progress * 100, 1),
                      "priority": priority})
    return {"service": "qbittorrent", "torrent_hash": torrent_hash,
            "files": files, "truncated": len(records) > MAX_FILES}
