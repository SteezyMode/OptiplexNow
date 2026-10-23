#!/usr/bin/env python3
"""Read-only local Docker service census for NOW host setup.

Finds *possible* existing Wolf, Jellyfin, qBittorrent and Gluetun
installations without touching containers, disclosing paths or credentials,
or treating image names as proof of ownership or safe adoption.

This tool is host-local only. It does not authenticate remote clients, grant
Docker access, or return endpoints to a NOW client.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess

SCHEMA = 1
MAX_ITEMS = 48
MAX_OUTPUT = 256 * 1024
SERVICES = ("wolf", "jellyfin", "qbittorrent", "gluetun")
# Advisory image identification; not an ownership/authorization mechanism.
KNOWN_IMAGES = {
    "wolf": ("ghcr.io/games-on-whales/wolf",),
    "jellyfin": ("jellyfin/jellyfin", "lscr.io/linuxserver/jellyfin",
                 "linuxserver/jellyfin"),
    "qbittorrent": ("lscr.io/linuxserver/qbittorrent",
                   "linuxserver/qbittorrent"),
    "gluetun": ("qmcgaw/gluetun",),
}
ID = re.compile(r"[0-9a-f]{64}\Z")
STATES = frozenset(("running", "exited", "created", "paused", "restarting",
                    "dead", "removing"))


class InventoryUnavailable(RuntimeError):
    pass


def classify_image(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 256:
        return None
    # Keep full repository name; a misleading basename or arbitrary tag
    # cannot turn a lookalike image into an installation candidate.
    image = value.lower().split("@", 1)[0]
    # Only the final path component may include a tag.
    image = image.rsplit("/", 1)
    image[-1] = image[-1].split(":", 1)[0]
    canonical = "/".join(image)
    for service, known in KNOWN_IMAGES.items():
        if canonical in known:
            return service
    return None


def docker_records(*, runner=subprocess.run) -> list[dict]:
    base = ["docker", "--host", "unix:///var/run/docker.sock"]
    def call(args: list[str], *, as_bytes: bool = False):
        try:
            result = runner(
                base + args, stdin=subprocess.DEVNULL, capture_output=True,
                timeout=8, check=False, **({} if as_bytes else {"text": True}))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InventoryUnavailable("Local Docker inventory unavailable") from exc
        if result.returncode != 0 or len(result.stdout) > MAX_OUTPUT:
            raise InventoryUnavailable("Local Docker inventory unavailable")
        return result.stdout

    ids = call(["ps", "--all", "--no-trunc", "--quiet"]).split()
    if len(ids) > MAX_ITEMS or len(ids) != len(set(ids)) or any(
            not ID.fullmatch(item) for item in ids):
        raise InventoryUnavailable("Ambiguous container inventory")
    if not ids:
        return []
    try:
        records = json.loads(call(["inspect", "--type", "container", *ids]))
    except (ValueError, UnicodeError) as exc:
        raise InventoryUnavailable("Malformed Docker inventory") from exc
    if not isinstance(records, list) or len(records) != len(ids):
        raise InventoryUnavailable("Inconsistent Docker inventory")
    seen = set()
    for record in records:
        if not isinstance(record, dict) or record.get("Id") not in ids or (
                record["Id"] in seen):
            raise InventoryUnavailable("Container identity mismatch")
        seen.add(record["Id"])
    return records


def assess(records: list[dict] | None) -> dict:
    """Classify only safe, bounded, non-secret metadata.

    None denotes an inaccessible Docker daemon, NOT zero installed services.
    An empty list only denotes that no Docker containers were observed;
    native/service installations are outside this probe.
    """
    inventory = {s: [] for s in SERVICES}
    vpn = {"topology": "not_verified",
           "gateway_health": "unknown",
           "vpn_egress_verified": False,
           "killswitch_verified": False}
    if records is not None:
        if not isinstance(records, list) or len(records) > MAX_ITEMS:
            raise InventoryUnavailable("Unusable record count")
        for rec in records:
            if not isinstance(rec, dict) or not ID.fullmatch(
                    str(rec.get("Id", ""))):
                raise InventoryUnavailable("Unusable record")
            cfg = rec.get("Config")
            cfg = cfg if isinstance(cfg, dict) else {}
            service = classify_image(cfg.get("Image"))
            if service:
                state = rec.get("State")
                state = state if isinstance(state, dict) else {}
                s = state.get("Status")
                s = s if isinstance(s, str) and s in STATES else "unknown"
                host = rec.get("HostConfig")
                host = host if isinstance(host, dict) else {}
                mode = host.get("NetworkMode")
                health = state.get("Health")
                health = health if isinstance(health, dict) else {}
                inventory[service].append({
                    "id": rec["Id"], "name": rec.get("Name"),
                    "state": s,
                    "network_mode": mode if isinstance(mode, str) else "",
                    "health": health.get("Status") if
                        health.get("Status") in ("healthy", "unhealthy",
                                                 "starting") else "unknown",
                })
        # Only ONE qBittorrent and ONE Gluetun can support a simple adopt
        # candidate; docker inspect metadata alone cannot prove a VPN tunnel.
        if len(inventory["qbittorrent"]) == len(inventory["gluetun"]) == 1:
            downloader = inventory["qbittorrent"][0]
            gateway = inventory["gluetun"][0]
            target = downloader["network_mode"].removeprefix("container:")
            if downloader["network_mode"].startswith("container:") and (
                    target == gateway["id"] or
                    (isinstance(gateway["name"], str) and
                     target == gateway["name"].lstrip("/"))):
                vpn["topology"] = "shared_gluetun_namespace"
                vpn["gateway_health"] = gateway["health"]

    services = {}
    for key, matches in inventory.items():
        if records is None:
            status = "unknown"
        elif not matches:
            status = "not_detected_in_docker"
        elif len(matches) > 1:
            status = "ambiguous_multiple"
        elif matches[0]["state"] == "running":
            status = "running_candidate"
        else:
            status = "stopped_candidate"
        services[key] = {"status": status, "docker_count": len(matches)}
    return {
        "schema_version": SCHEMA,
        "tool": "now-host-services",
        "read_only": True,
        "changes_performed": False,
        "may_adopt": False,
        "docker_access": "unavailable" if records is None else "available",
        "services": services,
        "downloads": vpn,
        "vuetorrent": "not_verified",
        "storage_paths": "not_inspected",
        "note": "Candidates only: no native-service scan, reachability, data-volume verification, owner authorization, VPN egress or kill-switch proof. Existing services must be reviewed before adoption.",
    }


def collect(*, runner=subprocess.run) -> dict:
    try:
        records = docker_records(runner=runner)
    except InventoryUnavailable:
        records = None
    return assess(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = collect()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("LOCAL SERVICE INVENTORY | READ-ONLY")
        for service, observed in report["services"].items():
            print(f"{service.upper():12} {observed['status']}"
                  f" ({observed['docker_count']} Docker candidate(s))")
        print(f"DOWNLOADER VPN: {report['downloads']['topology']}; "
              f"tunnel and kill switch NOT verified")
        print(f"VUE TORRENT: {report['vuetorrent']}")
        print(report["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
