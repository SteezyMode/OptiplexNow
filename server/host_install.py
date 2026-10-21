#!/usr/bin/env python3
"""Real, deliberately narrow NOW Host Wolf installer for clean AMD/Intel hosts.

--check reads the host only. --install MAY pull a pinned upstream image and
create a single, NOW-owned Wolf Compose project. It never installs Linux
packages/drivers, rewrites another Docker project or replaces user data.

First supported pilot candidates: Ubuntu or Pop!_OS 24.04 x86-64, AMD/Intel.
NVIDIA is intentionally blocked until a driver-versioned volume lifecycle
is implemented. Real stream/video/audio/controller validation is still required.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

import host_plan
import host_preflight
import host_stage

ROOT = Path("/var/lib/optiplex-now")
WORKSPACE = ROOT / "host"
LOCK_PATH = Path("/run/optiplex-now-host-install.lock")
PROJECT = "optiplex-now-host-pilot"
IMAGE_PREFIX = "ghcr.io/games-on-whales/wolf@"
REQUIRED_IDS = ("architecture", "operating_system", "gpu_detection",
                "virtual_controller_devices", "udev", "container_runtime",
                "wolf_ports", "disk_space", "memory")
MAX_OUTPUT = 32768


class InstallationError(RuntimeError):
    pass


def _docker(args: list[str], timeout: int = 30) -> str:
    """Use system Docker Unix socket, immutable argv and bounded timeouts."""
    env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
           "HOME": "/root" if os.geteuid() == 0 else "/",
           "DOCKER_CONFIG": "/nonexistent/now-host-docker-config"}
    try:
        cp = subprocess.run(["/usr/bin/docker", "--host",
                             "unix:///var/run/docker.sock"] + args,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallationError("Local Docker operation failed or timed out") from exc
    if cp.returncode != 0:
        raise InstallationError("Local Docker command failed; inspect the NOW install state")
    if len(cp.stdout) > MAX_OUTPUT:
        raise InstallationError("Excessive Docker command output")
    try:
        return cp.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise InstallationError("Invalid Docker command output") from exc


def _host_checks(gpu: str, render: str) -> dict:
    snapshot = host_preflight.collect_snapshot()
    report = host_preflight.evaluate(snapshot)
    statuses = {item["id"]: item["status"] for item in report["checks"]}
    blockers = [key for key in REQUIRED_IDS if statuses.get(key) != "pass"]
    if snapshot.get("os_id") not in ("ubuntu", "pop") or snapshot.get("os_version") != "24.04":
        blockers.append("only Ubuntu/Pop!_OS 24.04 pilot candidates")
    if gpu not in ("amd", "intel"):
        blockers.append("NVIDIA volume preparation has not been implemented")
    try:
        host_stage.validate_render_node(render)
    except ValueError:
        blockers.append("invalid render node")
    else:
        device = Path(render)
        vendor_file = Path("/sys/class/drm") / device.name / "device/vendor"
        vendor = host_preflight.read_small(vendor_file)
        if gpu in ("amd", "intel") and (
                vendor is None or vendor.strip().lower() != host_stage.GPU_VENDORS[gpu]):
            blockers.append("render node GPU vendor not independently verified")
        try:
            if not stat.S_ISCHR(device.stat().st_mode):
                blockers.append("render node is not a character device")
        except OSError:
            blockers.append("render node not accessible")
    if gpu in ("amd", "intel"):
        # Do not mistake another card or generic render node for video-encoding
        # support. The result below is only a pre-install compatibility check.
        for name in ("/dev/uinput", "/dev/uhid"):
            try:
                if not stat.S_ISCHR(Path(name).stat().st_mode):
                    blockers.append(name + " is not a character device")
            except OSError:
                blockers.append(name + " is unavailable")
    if not Path("/usr/bin/docker").is_file():
        blockers.append("system Docker command not installed")
    else:
        try:
            _docker(["compose", "version"], timeout=10)
            project_ids = _docker(["ps", "--all", "--no-trunc",
                                   "--filter", f"label=com.docker.compose.project={PROJECT}",
                                   "--format", "{{.ID}}"], timeout=10)
            if project_ids:
                blockers.append("NOW Compose project exists; no adoption")
        except InstallationError:
            blockers.append("local Docker/Compose access unavailable")
    if WORKSPACE.exists() or WORKSPACE.is_symlink():
        blockers.append("NOW Host workspace exists; no overwrite or implicit retry")
    return {"decision": "blocked" if blockers else "candidate",
            "gpu": gpu, "render_node": render,
            "os": snapshot.get("os_id"), "version": snapshot.get("os_version"),
            "blockers": sorted(set(blockers)),
            "notes": [
                "A candidate is not verified as capable of streaming video.",
                "No Linux packages, GPU drivers or existing services will be modified.",
                "Host Docker socket access is administrative and Wolf needs it to launch apps.",
            ]}


def _write_new(path: Path, value: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _status(workspace: Path, phase: str, image: str, *, cid: str | None = None) -> None:
    data = {"format": 1, "manager": "optiplex-now", "phase": phase,
            "image": image, "container_id": cid, "stream_verified": False}
    path = workspace / "install-state.json"
    tmp = workspace / ".install-state-next"
    _write_new(tmp, json.dumps(data, sort_keys=True, indent=2) + "\n")
    os.replace(tmp, path)
    folder = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(folder)
    finally:
        os.close(folder)


def _render_compose(gpu: str, render: str, digest: str, workspace: Path) -> str:
    plan = {"tool": "now-host-plan", "schema_version": host_plan.PLAN_SCHEMA,
            "mode": "read_only_preview", "decision": "blocked",
            "may_apply": False, "changes_performed": False}
    staged = host_stage.make_bundle(plan, digest=digest, render_node=render,
                                    gpu_vendor=gpu)
    _header, raw = staged["compose.yaml"].split("\n", 1)
    compose = json.loads(raw)
    service = compose["services"]["wolf"]
    if (compose["name"] != PROJECT
            or service["image"] != IMAGE_PREFIX + digest
            or len(compose["services"]) != 1):
        raise InstallationError("Unexpected generated Wolf template")
    volumes = service["volumes"]
    local = "./wolf:/etc/wolf:rw"
    if volumes.count(local) != 1:
        raise InstallationError("Persistent Wolf state mapping not recognized")
    volumes[volumes.index(local)] = str(workspace / "wolf") + ":/etc/wolf:rw"
    service["profiles"] = []  # No default profile; explicit service only.
    service["labels"]["io.optiplex-now.managed"] = "host-install-pilot"
    service["restart"] = "unless-stopped"
    return json.dumps(compose, sort_keys=True, indent=2) + "\n"


def install(gpu: str, render: str, digest: str, confirmation: str) -> dict:
    """Live, one-time clean host installation. No simulation or fallback path."""
    if os.geteuid() != 0:
        raise InstallationError("Root authority required (through a local authenticated prompt)")
    if confirmation != "INSTALL-WOLF":
        raise InstallationError("Explicit installation confirmation missing")
    host_stage.validate_digest(digest)
    if gpu not in ("amd", "intel"):
        raise InstallationError("NVIDIA installer is not enabled")
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        scan = _host_checks(gpu, render)
        if scan["decision"] != "candidate":
            raise InstallationError("Installation blocked: " + ", ".join(scan["blockers"]))
        if ROOT.is_symlink() or WORKSPACE.exists() or WORKSPACE.is_symlink():
            raise InstallationError("Managed root exists; refusing to overwrite")
        if not ROOT.exists():
            ROOT.mkdir(mode=0o700)
        elif not ROOT.is_dir() or ROOT.stat().st_uid != 0 or ROOT.stat().st_mode & 0o077:
            raise InstallationError("Existing NOW root is not trusted")
        WORKSPACE.mkdir(mode=0o700)
        (WORKSPACE / "wolf").mkdir(mode=0o700)
        image = IMAGE_PREFIX + digest
        compose = _render_compose(gpu, render, digest, WORKSPACE)
        _write_new(WORKSPACE / "compose.yaml", compose)
        _write_new(WORKSPACE / "owner.json", json.dumps(
            {"manager": "optiplex-now", "version": 1, "gpu": gpu,
             "render_node": render, "image": image}, sort_keys=True) + "\n")
        _status(WORKSPACE, "pulling", image)
        # Pull only the owner-confirmed immutable image reference.
        _docker(["pull", image], timeout=600)
        _status(WORKSPACE, "starting", image)
        _docker(["compose", "-p", PROJECT, "-f", str(WORKSPACE / "compose.yaml"),
                 "up", "--detach", "--no-deps", "--no-build",
                 "--no-recreate", "--pull", "never", "wolf"], timeout=90)
        ids = _docker(["ps", "--all", "--no-trunc",
                       "--filter", f"label=com.docker.compose.project={PROJECT}",
                       "--format", "{{.ID}}"]).splitlines()
        if len(ids) != 1 or not re.fullmatch(r"[a-f0-9]{64}", ids[0]):
            raise InstallationError("Wolf startup identity not verified; manual review required")
        cid = ids[0]
        image_actual = _docker(["inspect", "--type", "container",
                                "--format", "{{.Config.Image}}", cid])
        labels = json.loads(_docker(["inspect", "--type", "container",
                                     "--format", "{{json .Config.Labels}}", cid]))
        running = _docker(["inspect", "--type", "container",
                           "--format", "{{.State.Running}}", cid])
        if (image_actual != image or running != "true" or
                not isinstance(labels, dict) or
                labels.get("com.docker.compose.project") != PROJECT or
                labels.get("io.optiplex-now.managed") != "host-install-pilot" or
                labels.get("com.docker.compose.service") != "wolf"):
            raise InstallationError("Wolf container ownership/state not verified")
        _status(WORKSPACE, "running_stream_unverified", image, cid=cid)
        return {"result": "running_stream_unverified", "container_id": cid,
                "workspace": str(WORKSPACE), "stream_verified": False}
    finally:
        os.close(fd)


def main() -> int:
    p = argparse.ArgumentParser(description="NOW Host clean GPU pilot installer")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--install", action="store_true")
    p.add_argument("--gpu", choices=host_stage.GPU_CHOICES, required=True)
    p.add_argument("--render-node", required=True)
    p.add_argument("--image-digest", help="Verified Wolf OCI sha256 digest, required for --install")
    p.add_argument("--confirm", default="", help="Requires literal INSTALL-WOLF for --install")
    a = p.parse_args()
    try:
        if a.check:
            output = _host_checks(a.gpu, a.render_node)
        else:
            output = install(a.gpu, a.render_node, a.image_digest, a.confirm)
    except (InstallationError, ValueError, OSError) as exc:
        print("NOW Host: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
