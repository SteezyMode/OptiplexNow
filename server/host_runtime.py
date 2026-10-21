"""Fail-closed Wolf first-start coordinator, currently SIMULATION ONLY.

Exercises genuine install/inspect/cleanup decisions against an injected fake
Docker adapter. There is deliberately no callable live deployment entry point.
The live LocalDocker implementation is refused regardless of approval flags.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import host_docker
import host_plan
import host_stage
import host_transaction as tx

JOURNAL = "deployment.json"
JOURNAL_SCHEMA = 1
REQUIRED_CHECKS = {
    "architecture", "operating_system", "gpu_detection", "hardware_encoder",
    "virtual_controller_devices", "udev", "container_runtime",
    "wolf_ports", "disk_space", "memory",
}


class ActivationBlocked(RuntimeError):
    pass


def _active_bundle(root: Path) -> tuple[Path, dict]:
    """Reject altered/tampered generation bytes and unexpected filesystem layout."""
    state = tx._state(root)
    if not state or state.get("runtime") != "not_started" or not state.get("active"):
        raise ActivationBlocked("Missing prepared, inactive managed generation")
    base = root / tx.GEN_DIR
    if base.is_symlink() or not base.is_dir():
        raise ActivationBlocked("Unsafe generation storage")
    active = base / state["active"]
    if active.is_symlink() or not active.is_dir():
        raise ActivationBlocked("Unsafe active generation")
    files = {name: tx._read_bounded_regular(active / name)
             for name in tx.INPUT_FILES}
    digest = hashlib.sha256()
    for name in tx.INPUT_FILES:
        digest.update(name.encode() + b"\x00" + files[name] + b"\x00")
    if digest.hexdigest() != state["active"]:
        raise ActivationBlocked("Active generation checksum mismatch")
    try:
        manifest = json.loads(files["manifest.json"])
        gpu = manifest["gpu_vendor"]
        image = manifest["image"]
        render = manifest["render_node"]
        digest_pin = image.removeprefix("ghcr.io/games-on-whales/wolf@")
        expected = host_stage.make_bundle(
            {"tool": "now-host-plan", "schema_version": host_plan.PLAN_SCHEMA,
             "mode": "read_only_preview", "decision": "blocked",
             "may_apply": False, "changes_performed": False},
            digest=digest_pin, render_node=render, gpu_vendor=gpu)
        compose = expected["compose.yaml"]
        header, data = compose.split("\n", 1)
        config = json.loads(data)
        mounts = config["services"]["wolf"]["volumes"]
        mount = "./wolf:/etc/wolf:rw"
        if mounts.count(mount) != 1:
            raise ValueError("No stable Wolf state mount")
        mounts[mounts.index(mount)] = str(root / "wolf") + ":/etc/wolf:rw"
        expected["compose.yaml"] = header + "\n" + json.dumps(
            config, indent=2, sort_keys=True) + "\n"
    except (KeyError, ValueError, AttributeError, TypeError) as exc:
        raise ActivationBlocked("Unrecognized staged generation") from exc
    if any(files[name] != expected[name].encode("utf-8")
           for name in tx.INPUT_FILES):
        raise ActivationBlocked("Altered staged generation; refusing first start")
    if (root / "wolf").is_symlink() or not (root / "wolf").is_dir():
        raise ActivationBlocked("Persistent Wolf state is not a real directory")
    return active / "compose.yaml", manifest


def _readiness(report: dict, gpu: str) -> None:
    try:
        checks = host_plan._validate_preflight(report)
    except (ValueError, TypeError) as exc:
        raise ActivationBlocked("Invalid or untrusted preflight report") from exc
    relevant = REQUIRED_CHECKS | (
        {"nvidia_driver", "nvidia_drm_modeset"} if gpu == "nvidia" else set()
    )
    missing = sorted(check for check in relevant if checks.get(check) != "pass")
    if missing:
        # Actual host_preflight currently reports hardware_encoder=unknown.
        # Consequently, no physical host can satisfy this simulation gate yet.
        raise ActivationBlocked("Unsupported or unverified: " + ", ".join(missing))


def _journal(root: Path, event: dict, *, new: bool = False) -> None:
    payload = {
        "schema_version": JOURNAL_SCHEMA,
        "tool": "now-host-runtime",
        "mode": "simulation_only",
        **event,
    }
    if new:
        tx._write_exclusive(root / JOURNAL,
                            (json.dumps(payload, sort_keys=True) + "\n").encode())
    else:
        _replace_journal(root, payload)


def _replace_journal(root: Path, value: dict) -> None:
    """Atomic, durable journal update without changing active configuration."""
    descriptor, temporary = tempfile.mkstemp(prefix=".deploy-", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / JOURNAL)
        folder = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def simulate_first_start(workspace: Path, report: dict, docker: object,
                         *, owner_confirmed: bool) -> dict:
    """Exercise startup and targeted cleanup using a fake Docker implementation.

    DO NOT call from production code. A real LocalDocker object is rejected.
    Once a journal exists, no implicit retry is permitted. Recovery needs
    separate authenticated owner intervention and ownership inspection.
    """
    if isinstance(docker, host_docker.LocalDocker):
        raise ActivationBlocked("Live Docker deployment is not enabled")
    if not owner_confirmed:
        raise ActivationBlocked("Explicit owner approval required")
    root = tx._validate_workspace(workspace)
    if root.is_symlink() or not root.is_dir():
        raise ActivationBlocked("No safe managed workspace")
    lock = tx._acquire_lock(root)
    try:
        if (root / JOURNAL).exists() or (root / JOURNAL).is_symlink():
            raise ActivationBlocked("Prior start journal requires manual inspection")
        compose_file, manifest = _active_bundle(root)
        _readiness(report, manifest["gpu_vendor"])
        if docker.project_ids():
            raise ActivationBlocked("Existing Compose project: refuse adoption or restart")
        if not docker.has_image(manifest["image"]):
            raise ActivationBlocked("Pinned Wolf image not present locally")
        if (manifest["gpu_vendor"] == "nvidia"
                and not docker.has_driver_volume(host_stage.DRIVER_VOLUME)):
            raise ActivationBlocked("Version-matched NVIDIA driver volume is unverified")
        # A volume's name alone is not sufficient proof of version matching.
        if manifest["gpu_vendor"] == "nvidia":
            raise ActivationBlocked("NVIDIA driver-volume attestation not implemented")
        _journal(root, {
            "phase": "starting", "generation": tx._state(root)["active"],
            "container_id": None, "stream_verified": False,
        }, new=True)
        try:
            docker.start_once(compose_file)
            identifiers = docker.project_ids()
            if len(identifiers) != 1:
                raise ActivationBlocked("Expected exactly one new managed Wolf container")
            container = docker.inspect_owned(identifiers[0])
            if not container.get("running") or container.get("health") == "unhealthy":
                raise ActivationBlocked("New Wolf container did not enter running state")
            # Running is not healthy and is never equivalent to real streaming.
            _journal(root, {
                "phase": "started_unverified_stream",
                "generation": tx._state(root)["active"],
                "container_id": identifiers[0],
                "stream_verified": False,
                "container_health": container.get("health", "not_configured"),
            })
            return {
                "result": "simulated_start_only",
                "container_id": identifiers[0],
                "stream_verified": False,
            }
        except Exception:
            # Cleanup is permitted only when exactly one newly created ID is
            # positively identified through immutable Compose/service labels.
            # Ambiguity leaves everything untouched for manual recovery.
            cleaned = False
            try:
                ids = docker.project_ids()
                if len(ids) == 1:
                    docker.inspect_owned(ids[0])
                    docker.remove_owned(ids[0])
                    cleaned = True
            except Exception:
                pass
            _journal(root, {
                "phase": "failed_cleaned" if cleaned else "manual_recovery_required",
                "generation": tx._state(root)["active"],
                "container_id": None,
                "stream_verified": False,
            })
            raise
    finally:
        tx._release_lock(root, lock)
