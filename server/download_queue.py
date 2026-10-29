"""Bounded owner-only qBittorrent queue snapshot through a verified VPN gateway.

Caller MUST authenticate and authorize owner device before invoking this.
Localhost qBittorrent WebUI may bypass auth: never expose this helper directly
or let callers supply endpoints, container names, commands, or paths.
"""
import json
import re
import subprocess
from download_inventory import _containers, InventoryError

MAX_BYTES = 65536
MAX_ITEMS = 100
MAX_NAME = 160

def locate_verified_downloader(*, runner=subprocess.run):
    """Return only the private verified gateway container ID and WebUI port.

    Never return these privileged locators in owner-client responses.
    Gateway health confirms topology, not VPN egress/kill-switch correctness.
    """
    records = _containers(runner=runner)
    gateways = {}
    for record in records:
        image = str(record.get("Config", {}).get("Image", "")).lower()
        if image.split("/")[-1].split(":")[0] == "gluetun":
            gateways[record["Id"]] = record
    candidates = []
    for record in records:
        image = str(record.get("Config", {}).get("Image", "")).lower()
        if image.split("/")[-1].split(":")[0] != "qbittorrent":
            continue
        mode = record.get("HostConfig", {}).get("NetworkMode", "")
        if not isinstance(mode, str) or not mode.startswith("container:"):
            continue
        target = mode.partition(":")[2]
        matches = [identifier for identifier, gateway in gateways.items()
                   if target == identifier or
                   target == gateway.get("Name", "").lstrip("/")]
        if len(matches) == 1:
            candidates.append((record, matches[0], gateways[matches[0]]))
    if len(candidates) != 1:
        raise InventoryError("No unique VPN-bound downloader")
    record, gateway_id, gateway = candidates[0]
    if gateway.get("State", {}).get("Health", {}).get("Status") != "healthy":
        raise InventoryError("VPN gateway is unhealthy")
    ports = [v.partition("=")[2] for v in record.get("Config", {}).get("Env", [])
             if isinstance(v, str) and v.startswith("WEBUI_PORT=")]
    if len(ports) != 1 or not re.fullmatch(r"[0-9]{2,5}", ports[0]):
        raise InventoryError("Downloader port unavailable")
    port = int(ports[0])
    if not 1024 <= port <= 65535:
        raise InventoryError("Downloader port invalid")
    return gateway_id, port


def inspect_queue(*, runner=subprocess.run):
    gateway_id, port = locate_verified_downloader(runner=runner)
    url = f"http://127.0.0.1:{port}/api/v2/torrents/info"
    try:
        completed = runner(["docker", "exec", gateway_id, "wget", "-q", "-T", "5",
                            "-O", "-", url], capture_output=True, timeout=8,
                           check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InventoryError("Queue unavailable") from exc
    raw = completed.stdout
    if completed.returncode != 0 or not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise InventoryError("Queue unavailable")
    try:
        items = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InventoryError("Queue response malformed") from exc
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise InventoryError("Queue exceeds safe display limit")
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise InventoryError("Queue item malformed")
        name = item.get("name")
        state = item.get("state")
        progress = item.get("progress")
        if not isinstance(name, str) or not isinstance(state, str):
            raise InventoryError("Queue item invalid")
        if type(progress) not in (int, float) or not 0 <= progress <= 1:
            raise InventoryError("Queue progress invalid")
        torrent_hash = item.get("hash")
        speed, eta, seeds = (item.get("dlspeed"), item.get("eta"),
                             item.get("num_seeds"))
        if (not isinstance(torrent_hash, str) or
                not re.fullmatch(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?", torrent_hash)
                or any(type(v) is not int or v < -1 or v > 2**31-1
                       for v in (speed, eta, seeds))):
            raise InventoryError("Torrent status has invalid fields")
        result.append({"name": name[:MAX_NAME], "state": state[:48],
                       "progress_percent": round(progress * 100, 1),
                       "torrent_hash": torrent_hash.lower(),
                       "download_bps": speed, "eta_seconds": eta,
                       "seeders": seeds})
    return {"service": "qbittorrent", "queue": result, "truncated": False,
            "webui_port": port}
