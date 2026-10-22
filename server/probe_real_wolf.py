#!/usr/bin/env python3
"""Read-only API compatibility against an ALREADY ISOLATED, disposable real Wolf.

Refuses default/prod Wolf names, unlabeled containers, host networking, reused
/etc/wolf storage and missing isolation metadata. NEVER performs a Wolf POST.
Prints only counts/booleans/schema field names, not secret-bearing raw replies.

Test levels: real daemon GET API != real Moonlight/GPU stream/Create/Join.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wolf_socket_adapter import check_request

LABEL = "io.optiplex-now.compat-disposable"
NAME = re.compile(r"now-wolf-compat-[a-zA-Z0-9_-]{4,48}\Z")
TIMEOUT = 12
MAX_BYTES = 262144
ENDPOINTS = (
    ("clients", "/api/v1/clients"),
    ("profiles", "/api/v1/profiles"),
    ("apps", "/api/v1/apps"),
    ("sessions", "/api/v1/sessions"),
    ("lobbies", "/api/v1/lobbies"),
)


class ProbeError(RuntimeError):
    pass


def docker(argv, input_data=b""):
    try:
        cp = subprocess.run(
            ["docker", *argv], input=input_data, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ProbeError("Local Docker API unavailable or timed out") from None
    if cp.returncode != 0 or len(cp.stdout) > MAX_BYTES:
        raise ProbeError("Isolated Wolf Docker operation unavailable")
    return cp.stdout


def validate_container(name, info):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ProbeError("Refusing an unrecognized or default Wolf container")
    if not isinstance(info, dict) or info.get("Name") != "/" + name:
        raise ProbeError("Docker returned an unexpected container")
    config, host = info.get("Config"), info.get("HostConfig")
    if not isinstance(config, dict) or not isinstance(host, dict):
        raise ProbeError("Missing Docker isolation metadata")
    if config.get("Labels", {}).get(LABEL) != "true":
        raise ProbeError("Container lacks explicit disposable-probe label")
    if host.get("NetworkMode") != "none":
        raise ProbeError("Probe container must have isolated network mode")
    if host.get("Privileged") or host.get("Binds") is None and not info.get("Mounts"):
        raise ProbeError("Privileged container or missing isolated storage")
    if not info.get("State", {}).get("Running"):
        raise ProbeError("Disposable Wolf container is not running")
    mounts = info.get("Mounts")
    if not isinstance(mounts, list) or not mounts or len(mounts) > 16:
        raise ProbeError("Disposable Wolf mount layout is invalid")
    primary = [m for m in mounts if m.get("Type") == "bind"]
    if len(primary) != 1 or primary[0].get("Destination") != "/etc/wolf":
        raise ProbeError("Disposable Wolf must have only the scratch bind mount")
    m = primary[0]
    src = m.get("Source")
    if (not isinstance(src, str) or not os.path.isabs(src)
            or not m.get("RW")):
        raise ProbeError("Disposable Wolf storage layout is unsafe")
    # The image may declare extra Docker-created anonymous volumes. Accept
    # only 64-hex anonymous names at destinations declared by the image.
    # Reject named/persistent volumes or any second host bind.
    declared = config.get("Volumes") or {}
    if not isinstance(declared, dict):
        raise ProbeError("Unexpected Wolf image volumes metadata")
    allowed_volumes = {dest.rstrip("/") for dest in declared
                       if isinstance(dest, str) and dest.startswith("/")}
    for other in mounts:
        if other is m:
            continue
        name = other.get("Name")
        dest = other.get("Destination")
        if (other.get("Type") != "volume"
                or not isinstance(name, str)
                or re.fullmatch(r"[0-9a-f]{64}", name) is None
                or not isinstance(dest, str)
                or dest not in allowed_volumes
                or dest in ("", "/", "/etc/wolf")):
            raise ProbeError("Foreign or persistent Wolf volume refused")
    # GitHub hosted runners create this scratch path. Never allow /etc/wolf,
    # home directories or any other preexisting real server Wolf storage.
    norm = os.path.realpath(src)
    if (norm == "/etc/wolf" or norm.startswith("/etc/wolf/")
            or "/now-wolf-compat-" not in norm
            or "/etc/" in norm):
        raise ProbeError("Disposable Wolf storage is not under a scratch directory")
    return src


def inspect_container(name, docker_call=docker):
    if not NAME.fullmatch(name):
        raise ProbeError("Unrecognized disposable Wolf container name")
    raw = docker_call(["inspect", "--type", "container", name])
    try:
        items = json.loads(raw)
        if not isinstance(items, list) or len(items) != 1:
            raise ValueError("unexpected inspect shape")
        validate_container(name, items[0])
    except (ValueError, KeyError, TypeError):
        raise ProbeError("Invalid Docker isolation metadata") from None
    return items[0]


def probe(name, docker_call=docker):
    inspect_container(name, docker_call)
    source = (Path(__file__).resolve().parents[1] / "src" /
              "wolf_socket_adapter.py").read_text(encoding="utf-8")
    results = {}
    for label, endpoint in ENDPOINTS:
        check_request("GET", endpoint, None)
        raw = docker_call(["exec", "-i", name, "python3", "-c",
                           source, "GET", endpoint])
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ProbeError("Wolf returned an invalid " + label + " inventory") from None
        if (not isinstance(value, dict) or value.get("success") is not True
                or not isinstance(value.get(label), list)):
            raise ProbeError("Wolf " + label + " API shape was incompatible")
        results[label] = len(value[label])
    return {
        "probe": "real_wolf_read_only",
        "result": "pass",
        "isolated_container": True,
        "endpoint_counts": results,
        "creates_lobbies": False,
        "real_moonlight_session_tested": False,
        "steam_stream_tested": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(probe(args.container), sort_keys=True))
        return 0
    except (ProbeError, OSError) as exc:
        print(json.dumps({"probe": "real_wolf_read_only", "result": "blocked",
                          "reason": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
