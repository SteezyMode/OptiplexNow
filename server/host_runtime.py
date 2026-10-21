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
import host_owner
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
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
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


def _read_journal(root: Path) -> dict:
    path = root / JOURNAL
    try:
        if path.is_symlink():
            raise ValueError("Journal is a symlink")
        value = json.loads(tx._read_bounded_regular(path))
    except (OSError, ValueError, TypeError) as exc:
        raise ActivationBlocked("Missing or corrupt deployment journal") from exc
    if (not isinstance(value, dict)
            or value.get("schema_version") != JOURNAL_SCHEMA
            or value.get("tool") != "now-host-runtime"
            or value.get("mode") != "simulation_only"
            or value.get("phase") not in (
                "starting", "container_identified",
                "started_unverified_stream", "failed_cleaned",
                "manual_recovery_required")
            or value.get("stream_verified") is not False):
        raise ActivationBlocked("Invalid deployment journal")
    identifier = value.get("container_id")
    if identifier is not None:
        try:
            host_docker.valid_id(identifier)
        except host_docker.DockerError as exc:
            raise ActivationBlocked("Invalid recorded container ID") from exc
    generation = value.get("generation")
    if (not isinstance(generation, str) or len(generation) != 64
            or any(c not in "0123456789abcdef" for c in generation)):
        raise ActivationBlocked("Invalid journal generation")
    return value


def review_attempt(workspace: Path, docker: object) -> dict:
    """Read-only reconciliation for interrupted/finished simulated attempts.

    Does not retry, stop, remove, restart or authorize a container.
    Any ambiguity is surfaced as manual recovery, never silently repaired.
    """
    if isinstance(docker, host_docker.LocalDocker):
        raise ActivationBlocked("Live Docker access is not enabled")
    root = tx._validate_workspace(workspace)
    if root.is_symlink() or not root.is_dir():
        raise ActivationBlocked("No managed workspace")
    lock = tx._acquire_lock(root)
    try:
        journal = _read_journal(root)
        project_ids = tuple(docker.project_ids())
        recorded = journal.get("container_id")
        result = {
            "phase": journal["phase"],
            "recorded_container_id": recorded,
            "observed_container_ids": list(project_ids),
            "stream_verified": False,
            "action": "manual_review_only",
            "matches_recorded_identity": False,
        }
        if recorded is not None and project_ids == (recorded,):
            # Without a recorded image and a live matching Docker identity,
            # this remains an unresolved operator task.
            image = journal.get("image")
            if isinstance(image, str):
                try:
                    candidate = docker.inspect_owned(recorded, image)
                    result["matches_recorded_identity"] = (
                        candidate.get("id") == recorded
                        and candidate.get("image") == image)
                    if result["matches_recorded_identity"]:
                        result["running"] = candidate.get("running")
                        result["health"] = candidate.get("health")
                except host_docker.DockerError:
                    pass
        return result
    finally:
        tx._release_lock(root, lock)


def simulate_first_start(workspace: Path, report: dict, docker: object,
                         *, approval: str | None,
                         authority: host_owner.OwnerAuthority | None,
                         owner_connection) -> dict:
    """Test-only startup and narrowly identified cleanup via a fake Docker.

    No real Docker adapter is accepted. A one-use ticket must be generated
    by the host-local authority from Unix kernel peer credentials and trusted
    owner confirmation. This simulator still cannot run production Docker.
    """
    if isinstance(docker, host_docker.LocalDocker):
        raise ActivationBlocked("Live Docker deployment is not enabled")
    root = tx._validate_workspace(workspace)
    if root.is_symlink() or not root.is_dir():
        raise ActivationBlocked("No safe managed workspace")
    lock = tx._acquire_lock(root)
    try:
        if (root / JOURNAL).exists() or (root / JOURNAL).is_symlink():
            raise ActivationBlocked("Prior start journal requires manual inspection")
        compose_file, manifest = _active_bundle(root)
        generation = tx._state(root)["active"]
        if authority is None or owner_connection is None:
            raise ActivationBlocked("Owner authorization service is not connected")
        try:
            authority.consume(owner_connection, approval,
                              operation="start_wolf",
                              workspace=root, generation=generation)
        except host_owner.AuthorizationError as exc:
            raise ActivationBlocked("Owner authorization refused or stale") from exc
        _readiness(report, manifest["gpu_vendor"])
        if docker.project_ids():
            raise ActivationBlocked("Existing Compose project: refuse adoption or restart")
        if not docker.has_image(manifest["image"]):
            raise ActivationBlocked("Pinned Wolf image not present locally")
        if (manifest["gpu_vendor"] == "nvidia"
                and not docker.has_driver_volume(host_stage.DRIVER_VOLUME)):
            raise ActivationBlocked("Version-matched NVIDIA driver volume is unverified")
        if manifest["gpu_vendor"] == "nvidia":
            raise ActivationBlocked("NVIDIA driver-volume attestation not implemented")

        base = {
            "generation": generation, "image": manifest["image"],
            "container_id": None, "stream_verified": False,
        }
        _journal(root, {"phase": "starting", **base}, new=True)
        recorded_id = None
        try:
            docker.start_once(compose_file)
            identifiers = tuple(docker.project_ids())
            if len(identifiers) != 1:
                raise ActivationBlocked("Expected exactly one new managed Wolf container")
            candidate_id = host_docker.valid_id(identifiers[0])
            container = docker.inspect_owned(candidate_id, manifest["image"])
            if (container.get("id") != candidate_id
                    or container.get("image") != manifest["image"]):
                raise ActivationBlocked("Container identity or image mismatch")
            # Record the exact created ID *before* any later failure can
            # authorize targeted cleanup. Crash before this point is review-only.
            _journal(root, {
                "phase": "container_identified", **base,
                "container_id": candidate_id,
            })
            recorded_id = candidate_id
            if not container.get("running") or container.get("health") == "unhealthy":
                raise ActivationBlocked("New Wolf container did not enter running state")
            _journal(root, {
                "phase": "started_unverified_stream", **base,
                "container_id": recorded_id,
                "container_health": container.get("health", "not_configured"),
            })
            return {
                "result": "simulated_start_only",
                "container_id": recorded_id,
                "stream_verified": False,
            }
        except Exception:
            # A failed Compose command might have created a container.
            # Without a durable, precisely recorded ID we must NEVER guess.
            cleaned = False
            if recorded_id is not None:
                try:
                    if tuple(docker.project_ids()) == (recorded_id,):
                        current = docker.inspect_owned(recorded_id, manifest["image"])
                        if (current.get("id") == recorded_id
                                and current.get("image") == manifest["image"]):
                            docker.remove_owned(recorded_id, manifest["image"])
                            cleaned = not docker.project_ids()
                except Exception:
                    pass
            _journal(root, {
                "phase": "failed_cleaned" if cleaned else "manual_recovery_required",
                **base,
                "container_id": recorded_id,
            })
            raise
    finally:
        tx._release_lock(root, lock)
