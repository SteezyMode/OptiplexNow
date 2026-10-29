"""Read-only host-local inventory of a VPN-isolated qBittorrent deployment.

Discovery is not authorization to administer Docker or qBittorrent. This
module is never exposed directly to a client; host-side access control must
precede any future status descriptor. No environment variables, volume paths,
container labels or VPN addresses are returned.
"""
import json
import subprocess

MAX_OUTPUT = 256 * 1024
MAX_CONTAINERS = 100


class InventoryError(RuntimeError):
    pass


def _docker(*args, runner=subprocess.run):
    try:
        result = runner(
            ["docker", *args], capture_output=True, text=True, timeout=6,
            check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InventoryError("Docker inventory unavailable") from exc
    if result.returncode or len(result.stdout) > MAX_OUTPUT:
        raise InventoryError("Docker inventory unavailable")
    return result.stdout


def _containers(*, runner=subprocess.run):
    ids = _docker("ps", "-q", "--no-trunc", runner=runner).split()
    if len(ids) > MAX_CONTAINERS or any(len(i) != 64 or
                                         any(c not in "0123456789abcdef" for c in i)
                                         for i in ids):
        raise InventoryError("Unusable container inventory")
    if not ids:
        return []
    try:
        values = json.loads(_docker("inspect", *ids, runner=runner))
    except (ValueError, TypeError) as exc:
        raise InventoryError("Malformed container inventory") from exc
    if not isinstance(values, list) or len(values) != len(ids):
        raise InventoryError("Inconsistent container inventory")
    return values


def inspect_download_topology(*, runner=subprocess.run):
    """Return only verified container relationships, never credentials."""
    records = _containers(runner=runner)
    by_id = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("Id"), str):
            raise InventoryError("Malformed container record")
        by_id[record["Id"]] = record
    # Image names are advisory discovery hints, not proof that a VPN is live.
    gateways = {}
    for identifier, record in by_id.items():
        image = str(record.get("Config", {}).get("Image", "")).lower()
        if "gluetun" in image and image.split("/")[-1].split(":")[0] == "gluetun":
            gateways[identifier] = record
    results = []
    for identifier, record in by_id.items():
        image = str(record.get("Config", {}).get("Image", "")).lower()
        basename = image.split("/")[-1].split(":")[0]
        if basename != "qbittorrent":
            continue
        mode = record.get("HostConfig", {}).get("NetworkMode", "")
        if not isinstance(mode, str) or not mode.startswith("container:"):
            results.append({"service": "qbittorrent", "gateway_bound": False})
            continue
        target = mode.partition(":")[2]
        matches = [id_ for id_, gateway in gateways.items()
                   if target == id_ or
                   (len(target) == 64 and target == id_) or
                   (target == gateway.get("Name", "").lstrip("/"))]
        if len(matches) != 1:
            results.append({"service": "qbittorrent", "gateway_bound": False})
            continue
        gateway = gateways[matches[0]]
        healthy = gateway.get("State", {}).get("Health", {}).get("Status") == "healthy"
        # Expose a fixed provider label only. Never return VPN credentials,
        # environment variables, connection files or underlying container IDs.
        env = gateway.get("Config", {}).get("Env", [])
        provider = "airvpn" if any(
            item.strip().lower() == "vpn_service_provider=airvpn"
            for item in env if isinstance(item, str)) else "other"
        results.append({
            "service": "qbittorrent",
            "vpn_provider": provider,
            "gateway_bound": True,
            "gateway_healthy": healthy,
            "vpn_egress_verified": False,
            "killswitch_verified": False,
        })
    return {"version": 1, "downloaders": results}
