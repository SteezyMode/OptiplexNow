#!/usr/bin/env python3
"""Read-only, local host inventory for future NOW server provisioning.

No root permissions, network sign-in, service changes or external connections.
Output intentionally excludes IPs, usernames, Tailscale peers and Docker secrets.
This is an inventory, NOT streaming readiness certification.
"""

import argparse
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path

SCHEMA_VERSION = 1
READ_COMMANDS = (
    ("tailscale", "status", "--json"),
    ("nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"),
    ("lspci", "-nn"),
    ("docker", "info", "--format", "{{.ServerVersion}}"),
    ("docker", "ps", "--format", "{{.Names}}|{{.Image}}"),
    ("systemctl", "--user", "is-active", "sunshine.service"),
    ("systemctl", "is-active", "sunshine.service"),
    ("systemctl", "is-active", "wolf-start.service"),
    ("ss", "-H", "-ltnu"),
)
# Advisory only, not a complete port inventory for either streaming backend.
STREAMING_PORTS = (47984, 47989, 47990, 47998, 47999, 48000, 48010)


def os_release_parse(raw):
    """Parse os-release text without evaluating shell syntax."""
    values = {}
    for row in raw.splitlines():
        row = row.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        if key not in {"ID", "VERSION_ID"}:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value if re.fullmatch(r"[a-zA-Z0-9._+-]{1,40}", value) else "unknown"
    return values


def run_command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result if result.returncode == 0 else None


def _safe_label(value, limit=96):
    return re.sub(r"[^a-zA-Z0-9 ._+()/-]", "?", str(value))[:limit].strip()


def _is_active(invoke, command):
    result = invoke(command)
    return result is not None and result.stdout.strip() == "active"


def ports_from_ss(raw):
    """Only return recognized port numbers, never the bound addresses."""
    ports = set()
    for line in raw.splitlines():
        fields = line.split()
        # ss -H -ltnu: PROTOCOL STATE RECV-Q SEND-Q LOCAL PEER
        if len(fields) < 5 or fields[0] not in ("tcp", "udp"):
            continue
        match = re.search(r":(\d{1,5})$", fields[4])
        if match and int(match.group(1)) in STREAMING_PORTS:
            ports.add(int(match.group(1)))
    return sorted(ports)


def collect(*, os_release=None, arch=None, memory_kib=None, home_free_bytes=None,
            which=None, runner=None):
    """Report on this host; dependencies are injectable for offline tests."""
    if os_release is None:
        try:
            os_release = Path("/etc/os-release").read_text(encoding="utf-8")
        except OSError:
            os_release = ""
    if arch is None:
        arch = platform.machine()
    if memory_kib is None:
        try:
            mem = Path("/proc/meminfo").read_text(encoding="utf-8")
            match = re.search(r"(?m)^MemTotal:\s*(\d+)\s+kB", mem)
            memory_kib = int(match.group(1)) if match else None
        except OSError:
            memory_kib = None
    if home_free_bytes is None:
        try:
            home_free_bytes = shutil.disk_usage(Path.home()).free
        except OSError:
            home_free_bytes = None
    if which is None:
        which = shutil.which
    if runner is None:
        runner = run_command

    info = os_release_parse(os_release)
    os_id = info.get("ID", "unknown").lower()
    version = info.get("VERSION_ID", "unknown")
    architecture = _safe_label(arch, 32)
    test_scope = (os_id in ("ubuntu", "pop") and version == "24.04"
                  and architecture in ("x86_64", "amd64"))

    def invoke(args):
        if tuple(args) not in READ_COMMANDS or not which(args[0]):
            return None
        try:
            return runner(list(args))
        except (OSError, subprocess.TimeoutExpired):
            return None

    gpu_info = invoke(READ_COMMANDS[1])
    nvidia_gpu = []
    if gpu_info:
        for raw in gpu_info.stdout.splitlines()[:8]:
            if "," not in raw:
                continue
            name, driver = raw.rsplit(",", 1)
            name, driver = _safe_label(name), _safe_label(driver, 32)
            if name and re.fullmatch(r"\d+(?:\.\d+)*", driver):
                nvidia_gpu.append({"model": name, "driver": driver})

    pci = invoke(READ_COMMANDS[2])
    gpu_vendors = set()
    if pci:
        for line in pci.stdout.splitlines():
            if not re.search(r"\b(VGA compatible controller|3D controller|Display controller)\b", line, re.I):
                continue
            for vendor, label in (("10de", "nvidia"), ("1002", "amd"), ("8086", "intel")):
                if f"[{vendor}:" in line.lower() or f"[{vendor}]" in line.lower():
                    gpu_vendors.add(label)
    if nvidia_gpu:
        gpu_vendors.add("nvidia")

    tailscale = "not_installed" if not which("tailscale") else "unknown"
    tail = invoke(READ_COMMANDS[0])
    if tail:
        try:
            obj = json.loads(tail.stdout)
            state = obj.get("BackendState") if isinstance(obj, dict) else None
            tailscale = {"Running": "connected", "NeedsLogin": "needs_login",
                         "Stopped": "stopped"}.get(state, "unknown")
        except (ValueError, TypeError):
            tailscale = "unknown"

    docker = "not_installed" if not which("docker") else "unavailable"
    if invoke(READ_COMMANDS[3]):
        docker = "accessible"
    containers = invoke(READ_COMMANDS[4]) if docker == "accessible" else None
    wolf = "unknown" if docker == "unavailable" else "not_detected"
    if containers:
        if any(re.search(r"(^|[/|])wolf(?=[:|\s]|$)", line, re.I)
               for line in containers.stdout.splitlines()):
            wolf = "detected"
    if _is_active(invoke, READ_COMMANDS[7]):
        wolf = "detected"

    sunshine = "installed" if which("sunshine") else "not_detected"
    if _is_active(invoke, READ_COMMANDS[5]) or _is_active(invoke, READ_COMMANDS[6]):
        sunshine = "running"

    ss = invoke(READ_COMMANDS[8])
    occupied_ports = ports_from_ss(ss.stdout) if ss else None

    notes = []
    if not test_scope:
        notes.append("Outside initial proposed Ubuntu/Pop!_OS 24.04 amd64 test scope")
    if not nvidia_gpu:
        notes.append("NVIDIA driver/encoder not verified; actual encoding still requires streaming test")
    else:
        notes.append("NVIDIA driver detected; encoder availability and playback not yet tested")
    if docker == "unavailable":
        notes.append("Docker installed but inaccessible or daemon unavailable")
    if tailscale in ("not_installed", "needs_login", "stopped", "unknown"):
        notes.append("Tailscale is not verified connected; login and access remain separate actions")
    if wolf == "detected" and sunshine in ("installed", "running"):
        notes.append("Both streaming backends present; review actual port ownership before install")
    if occupied_ports:
        notes.append("Streaming-related ports already listening; do not claim they are free")

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": "this_computer_read_only",
        "platform": {
            "os_id": os_id, "os_version": version,
            "architecture": architecture,
            "initial_test_scope_match": test_scope,
        },
        "hardware": {
            "memory_gib": round(memory_kib / 1048576, 1) if memory_kib is not None else None,
            "home_free_gib": round(home_free_bytes / 1073741824, 1) if home_free_bytes is not None else None,
            "gpu_vendors_detected": sorted(gpu_vendors),
            "nvidia_driver_gpus": nvidia_gpu,
            "encoder_tested": False,
        },
        "components": {
            "tailscale": tailscale, "docker": docker,
            "wolf": wolf, "sunshine": sunshine,
        },
        "streaming_ports_listening": occupied_ports,
        "observations": notes,
        "streaming_ready": "not_tested",
        "changes_made": False,
    }


def format_human(data):
    p, h, c = data["platform"], data["hardware"], data["components"]
    lines = [
        "NOW | Server preflight (read only)",
        "OS: {} {} ({})".format(p["os_id"], p["os_version"], p["architecture"]),
        "Within initial test scope: {}".format("yes" if p["initial_test_scope_match"] else "no"),
        "GPU vendors: {}".format(", ".join(h["gpu_vendors_detected"]) or "not determined"),
        "NVIDIA driver: {}".format(
            ", ".join(x["driver"] for x in h["nvidia_driver_gpus"]) or "not verified"),
        "Memory: {} GiB | Home free: {} GiB".format(
            h["memory_gib"] if h["memory_gib"] is not None else "unknown",
            h["home_free_gib"] if h["home_free_gib"] is not None else "unknown"),
        "Tailscale: {} | Docker: {}".format(c["tailscale"], c["docker"]),
        "Wolf: {} | Sunshine: {}".format(c["wolf"], c["sunshine"]),
        "Streaming ports listening: {}".format(
            ", ".join(map(str, data["streaming_ports_listening"]))
            if data["streaming_ports_listening"] is not None else "unknown"),
    ]
    lines.extend("- " + note for note in data["observations"])
    lines.append("No changes made. Actual streaming and encoder readiness NOT tested.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only local server compatibility inventory")
    parser.add_argument("--json", action="store_true", help="Machine-readable report")
    args = parser.parse_args(argv)
    data = collect()
    print(json.dumps(data, sort_keys=True, indent=2) if args.json else format_human(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
