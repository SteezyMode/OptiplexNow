#!/usr/bin/env python3
"""Read-only NOW Host inventory for a future, narrowly supported Wolf installer.

No sudo, package installation, Docker writes, port binding, or user secrets.
This is NOT a streaming compatibility certificate or a host installer.
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import socket
import stat
import subprocess
from pathlib import Path

SCHEMA_VERSION = 1
# Wolf stable troubleshooting: these are observed local bind conflicts only.
WOLF_PORTS = {
    "tcp": {47984, 47989, 48010},
    "udp": {47999, 48100, 48200},
}
GPU_VENDORS = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "Intel"}
MIN_NVIDIA_DRIVER = (530, 30, 2)
MIN_FREE_BYTES = 10 * 1024**3
MIN_MEM_BYTES = 4 * 1024**3


def read_small(path: Path, limit: int = 128 * 1024) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            content = handle.read(limit + 1)
            return content if len(content) <= limit else None
    except (OSError, ValueError):
        return None


def parse_os_release(content: str | None) -> dict[str, str]:
    if not content:
        return {}
    result = {}
    for line in content.splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = value[:128]
    return result


def parse_mem_available(content: str | None) -> int | None:
    if content:
        match = re.search(r"^MemAvailable:\s*(\d+)\s*kB\s*$", content, re.M)
        if match:
            return int(match.group(1)) * 1024
    return None


def parse_bound_ports(content: str | None, protocol: str) -> set[int] | None:
    """Read /proc/net/* sockets in this network namespace. TCP: LISTEN only."""
    if content is None:
        return None
    found = set()
    for line in content.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 4 or ":" not in fields[1]:
            continue
        if protocol == "tcp" and fields[3] != "0A":
            continue
        try:
            port = int(fields[1].rsplit(":", 1)[1], 16)
        except ValueError:
            continue
        if 0 < port <= 65535:
            found.add(port)
    return found


def driver_version(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", value.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def docker_server_version(timeout_seconds: float = 3) -> str | None:
    """Only queries daemon metadata. Never adds the user to the Docker group."""
    if not shutil.which("docker"):
        return None
    try:
        run = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=timeout_seconds, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = run.stdout.strip()
    return value[:48] if run.returncode == 0 and re.fullmatch(r"[0-9][0-9A-Za-z.+-]*", value) else None


def collect_snapshot(root: Path = Path("/"), *, machine: str | None = None,
                     docker_version: str | None = None,
                     check_docker: bool = True) -> dict:
    """Collect local observations. root and injected values support offline fixtures."""
    root = Path(root)
    release = parse_os_release(read_small(root / "etc/os-release"))
    arch = machine if machine is not None else platform.machine()
    gpus = []
    pci_root = root / "sys/bus/pci/devices"
    if pci_root.is_dir():
        for device in sorted(pci_root.iterdir())[:128]:
            pci_class = read_small(device / "class")
            vendor = read_small(device / "vendor")
            if not pci_class or not vendor or not pci_class.strip().lower().startswith("0x03"):
                continue
            vendor_id = vendor.strip().lower()
            gpus.append(GPU_VENDORS.get(vendor_id, "Other PCI GPU"))
    gpus = sorted(set(gpus))
    render_nodes = []
    drm = root / "dev/dri"
    if drm.is_dir():
        render_nodes = sorted(node.name for node in drm.glob("renderD*")
                              if re.fullmatch(r"renderD\d+", node.name))[:16]
    devices = {name: (root / "dev" / name).exists() for name in ("uinput", "uhid")}
    gpu_device = (root / "dev/nvidia0").exists()
    docker_socket = root / "var/run/docker.sock"
    try:
        docker_socket_present = stat.S_ISSOCK(docker_socket.stat().st_mode)
    except OSError:
        docker_socket_present = False
    docker_cli = shutil.which("docker") is not None if root == Path("/") else False
    if docker_version is None and check_docker and root == Path("/") and docker_cli:
        docker_version = docker_server_version()

    port_reads = {}
    for proto in ("tcp", "udp"):
        for family in ("", "6"):
            port_reads[proto + family] = parse_bound_ports(
                read_small(root / "proc/net" / (proto + family)), proto)

    available = parse_mem_available(read_small(root / "proc/meminfo"))
    try:
        disk_free = shutil.disk_usage(root).free
    except OSError:
        disk_free = None

    return {
        "os_id": release.get("ID", "").lower(),
        "os_version": release.get("VERSION_ID", ""),
        "os_like": release.get("ID_LIKE", "").lower().split(),
        "architecture": arch.lower(),
        "gpu_vendors": gpus,
        "render_nodes": render_nodes,
        "nvidia_node": gpu_device,
        "nvidia_driver": (read_small(root / "sys/module/nvidia/version") or "").strip()[:48],
        "nvidia_drm_modeset": (read_small(root / "sys/module/nvidia_drm/parameters/modeset") or "").strip()[:8],
        "controller_devices": devices,
        "udev_present": (root / "run/udev").is_dir(),
        "docker_cli": docker_cli,
        "docker_socket": docker_socket_present,
        "docker_version": docker_version,
        "port_reads": {name: sorted(value) if value is not None else None
                       for name, value in port_reads.items()},
        "memory_available_bytes": available,
        "disk_free_bytes": disk_free,
    }


def evaluate(snapshot: dict) -> dict:
    """Pure classification: missing evidence is not inferred as compatibility."""
    checks = []

    def add(identifier: str, status: str, detail: str) -> None:
        checks.append({"id": identifier, "status": status, "detail": detail})

    arch = snapshot.get("architecture", "")
    add("architecture", "pass" if arch in ("x86_64", "amd64") else
        ("unsupported" if arch else "unknown"),
        f"Detected {arch or 'unknown'}; first pilot targets x86-64 Linux.")

    distro = snapshot.get("os_id", "")
    version = snapshot.get("os_version", "")
    if distro in ("ubuntu", "pop") and version == "24.04":
        os_status = "pass"
        os_text = (("Pop!_OS" if distro == "pop" else "Ubuntu")
                   + " 24.04 is a pilot candidate; GPU encoding is not certified.")
    elif not distro:
        os_status = "unknown"
        os_text = "Unable to identify the Linux distribution."
    else:
        os_status = "unknown"
        os_text = f"{distro} {version or '(unversioned)'} has not been qualified for the first pilot."
    add("operating_system", os_status, os_text)

    gpus = snapshot.get("gpu_vendors", [])
    nodes = snapshot.get("render_nodes", [])
    nv = bool(snapshot.get("nvidia_node"))
    add("gpu_detection",
        "pass" if gpus and (nodes or nv) else
        ("attention" if not nodes and not nv else "unknown"),
        f"PCI graphics: {', '.join(gpus) if gpus else 'unidentified'}; render nodes: {', '.join(nodes) if nodes else 'none observed'}; NVIDIA node: {'present' if nv else 'absent'}.")
    add("hardware_encoder", "unknown",
        "No actual codec/encoder or Wolf stream test performed. GPU presence cannot prove encoding support.")

    if "NVIDIA" in gpus or nv:
        parsed = driver_version(snapshot.get("nvidia_driver"))
        add("nvidia_driver",
            ("unknown" if parsed is None else
             "attention" if parsed < MIN_NVIDIA_DRIVER else "pass"),
            f"NVIDIA kernel driver: {snapshot.get('nvidia_driver') or 'unknown'}; Wolf documents >= 530.30.02.")
        modeset = snapshot.get("nvidia_drm_modeset")
        add("nvidia_drm_modeset", "pass" if modeset == "Y" else
            "attention" if modeset == "N" else "unknown",
            f"nvidia-drm modeset: {modeset or 'unknown'}; Wolf requires Y.")

    devices = snapshot.get("controller_devices", {})
    missing = [device for device in ("uinput", "uhid") if not devices.get(device)]
    add("virtual_controller_devices", "attention" if missing else "pass",
        f"Controller input devices absent: {', '.join(missing)}." if missing else
        "uinput and uhid nodes observed; access permissions not validated.")
    add("udev", "pass" if snapshot.get("udev_present") else "attention",
        "udev runtime directory observed." if snapshot.get("udev_present") else
        "/run/udev was not observed; Wolf may require device events.")

    docker = snapshot.get("docker_version")
    add("container_runtime", "pass" if docker else "attention",
        f"Docker daemon query succeeded (version {docker}); permissions and GPU integration untested."
        if docker else
        "Docker daemon not verified from this user account; missing CLI, socket or permission may be the cause.")

    reads = snapshot.get("port_reads", {})
    conflicts = []
    incomplete = []
    for proto, numbers in WOLF_PORTS.items():
        a, b = reads.get(proto), reads.get(proto + "6")
        if a is None or b is None:
            incomplete.append(proto)
        observed = set(a or []) | set(b or [])
        conflicts.extend(f"{port}/{proto}" for port in sorted(numbers & observed))
    add("wolf_ports", "attention" if conflicts else
        "unknown" if incomplete else "pass",
        f"Local binds observed: {', '.join(conflicts)}. No services were stopped."
        if conflicts else
        ("Could not inspect all IPv4/IPv6 socket tables." if incomplete else
         "No matching local binds observed at scan time; no firewall or reachability test."))

    disk = snapshot.get("disk_free_bytes")
    add("disk_space", "unknown" if disk is None else
        "attention" if disk < MIN_FREE_BYTES else "pass",
        f"Free space visible: {disk // 1024**3} GiB; provisional 10 GiB minimum."
        if disk is not None else "Free disk space could not be inspected.")
    mem = snapshot.get("memory_available_bytes")
    add("memory", "unknown" if mem is None else
        "attention" if mem < MIN_MEM_BYTES else "pass",
        f"Available memory: {mem // 1024**2} MiB; provisional 4 GiB minimum."
        if mem is not None else "Available memory could not be inspected.")

    statuses = {check["status"] for check in checks}
    overall = ("unsupported" if "unsupported" in statuses else
               "requires_attention" if "attention" in statuses else "unknown")
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "now-host-preflight",
        "read_only": True,
        "overall": overall,
        "verified_streaming": False,
        "pilot_scope": "Ubuntu 24.04 amd64 candidate; no certified host matrix yet",
        "checks": checks,
        "note": "Information only. Nothing has been installed or changed. A passing check is not proof of Wolf compatibility.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only NOW Host inventory; does not install or change services.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable local findings.")
    args = parser.parse_args()
    result = evaluate(collect_snapshot())
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"NOW Host Preflight | {result['overall']} | READ-ONLY")
        for check in result["checks"]:
            print(f"[{check['status'].upper():18}] {check['id']}: {check['detail']}")
        print("\n" + result["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
