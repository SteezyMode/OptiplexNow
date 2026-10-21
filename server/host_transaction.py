#!/usr/bin/env python3
"""Transactional, local-only management of NOW Host configuration generations.

This deliberately does NOT install packages, create Docker volumes or start Wolf.
The operations below manage only a named workspace and retain all user state.
Future Docker activation needs a separate, explicitly authorized backend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import host_stage

OWNER_FILE = ".now-host-owner.json"
CURRENT_FILE = "current.json"
LOCK_FILE = ".now-host.lock"
GEN_DIR = "generations"
SCHEMA = 1
INPUT_FILES = ("compose.yaml", "manifest.json", "README.txt")
MAX_FILE = 128 * 1024


def _read_bounded_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Not a regular, non-symlink input: {path.name}")
    if path.stat().st_size > MAX_FILE:
        raise ValueError("Bundle file is too large")
    with path.open("rb") as handle:
        data = handle.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError("Bundle file is too large")
    return data


def _input_bundle(source: Path) -> dict[str, bytes]:
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Staged bundle must be a real directory")
    raw = {name: _read_bounded_regular(source / name) for name in INPUT_FILES}
    try:
        manifest = json.loads(raw["manifest.json"])
        lines = raw["compose.yaml"].split(b"\n", 1)
        compose = json.loads(lines[1] if len(lines) == 2 and lines[0].startswith(b"#") else raw["compose.yaml"])
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Malformed staged manifest/Compose JSON") from exc
    if (manifest.get("tool") != "now-host-stage"
            or manifest.get("schema_version") != host_stage.STAGE_SCHEMA
            or manifest.get("mode") != "review_only"
            or manifest.get("deploy_supported") is not False
            or manifest.get("changes_to_host_services") is not False
            or manifest.get("approval") != "not_granted"
            or manifest.get("nvidia_method") != "manual_external_driver_volume"
            or manifest.get("driver_volume") != host_stage.DRIVER_VOLUME
            or manifest.get("driver_volume_prepared") is not False
            or manifest.get("unmanaged_containers_may_be_adopted") is not False
            or manifest.get("existing_data_may_be_deleted") is not False):
        raise ValueError("Unsafe or unknown staging manifest")
    service = compose.get("services", {}).get("wolf", {})
    if (compose.get("name") != manifest.get("managed_compose_project")
            or set(compose.get("services", {})) != {"wolf"}
            or compose.get("volumes") != {host_stage.DRIVER_VOLUME: {"external": True}}
            or service.get("image") != manifest.get("image")
            or service.get("profiles") != [host_stage.PROFILE]
            or service.get("pull_policy") != "never"
            or service.get("restart") != "no"
            or service.get("environment", {}).get("NVIDIA_DRIVER_VOLUME_NAME") != host_stage.DRIVER_VOLUME
            or service.get("network_mode") != "host"):
        raise ValueError("Unrecognized or unsafe Compose staging contract")
    # Re-render from our validated template instead of trusting arbitrary
    # executable Compose fields supplied in a bundle or modified by a user.
    digest = manifest["image"].removeprefix("ghcr.io/games-on-whales/wolf@")
    clean = host_stage.make_bundle(
        {"tool": "now-host-plan", "schema_version": 1, "mode": "read_only_preview",
         "decision": "blocked", "may_apply": False, "changes_performed": False},
        digest=digest, render_node=manifest["render_node"])
    for name in INPUT_FILES:
        if raw[name] != clean[name].encode("utf-8"):
            raise ValueError("Staged files do not match the known safe template")
    return raw


def _validate_workspace(workspace: Path) -> Path:
    if not workspace.is_absolute():
        raise ValueError("Workspace must be absolute")
    if workspace == Path("/") or workspace.name in ("", ".", ".."):
        raise ValueError("Refusing a filesystem root")
    # This preliminary engine is permitted only under a private /tmp fixture,
    # and cannot modify /etc, /var/lib or user data on a real server.
    root = Path("/tmp")
    parent = workspace.parent
    if parent != root or workspace.name.startswith("."):
        raise ValueError("Prototype workspace must be a new direct child of /tmp")
    if workspace.is_symlink():
        raise ValueError("Refusing a symlink workspace")
    return workspace


def _write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _write_current(root: Path, current: dict) -> None:
    descriptor, tempfile_path = tempfile.mkstemp(prefix=".current-", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(current, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tempfile_path, root / CURRENT_FILE)
        dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(tempfile_path):
            os.unlink(tempfile_path)


def _state(root: Path) -> dict | None:
    marker = root / OWNER_FILE
    state_path = root / CURRENT_FILE
    if not marker.exists() and not state_path.exists():
        return None
    if marker.is_symlink() or state_path.is_symlink():
        raise ValueError("Managed workspace metadata is a symlink")
    try:
        owner = json.loads(_read_bounded_regular(marker))
        state = json.loads(_read_bounded_regular(state_path))
    except (OSError, ValueError) as exc:
        raise ValueError("Corrupt managed workspace; refusing changes") from exc
    if (owner != {"tool": "now-host-transaction", "schema_version": SCHEMA}
            or state.get("tool") != "now-host-transaction"
            or state.get("schema_version") != SCHEMA
            or state.get("runtime") != "not_started"):
        raise ValueError("Unowned or incompatible workspace")
    for field in ("active", "previous"):
        value = state.get(field)
        if value is not None and (not isinstance(value, str)
                                  or len(value) != 64
                                  or any(c not in "0123456789abcdef" for c in value)
                                  or not (root / GEN_DIR / value).is_dir()
                                  or (root / GEN_DIR / value).is_symlink()):
            raise ValueError("Corrupt managed generation reference")
    return state


def _acquire_lock(root: Path) -> int:
    return os.open(root / LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)


def _release_lock(root: Path, lock_fd: int) -> None:
    os.close(lock_fd)
    (root / LOCK_FILE).unlink(missing_ok=True)


def prepare(source: Path, workspace: Path) -> dict:
    """Activate a NEW local configuration generation, never running Compose."""
    files = _input_bundle(source)
    root = _validate_workspace(workspace)
    # The generated Compose file must bind the SAME persistent Wolf state
    # on every generation. A relative ./wolf would point to each release.
    raw_compose = files["compose.yaml"].decode("utf-8")
    header, payload = raw_compose.split("\n", 1)
    compose = json.loads(payload)
    mounts = compose["services"]["wolf"]["volumes"]
    if mounts.count("./wolf:/etc/wolf:rw") != 1:
        raise ValueError("Missing expected persistent Wolf mount")
    mounts[mounts.index("./wolf:/etc/wolf:rw")] = str(root / "wolf") + ":/etc/wolf:rw"
    files["compose.yaml"] = (header + "\n" + json.dumps(
        compose, indent=2, sort_keys=True) + "\n").encode("utf-8")
    created_root = False
    if not root.exists():
        root.mkdir(mode=0o700)
        created_root = True
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Workspace is not a real directory")
    lock = _acquire_lock(root)
    new_generation = None
    try:
        state = _state(root)
        if state is None:
            if not created_root or list(p.name for p in root.iterdir()) != [LOCK_FILE]:
                raise ValueError("Refusing to take ownership of an existing directory")
            (root / GEN_DIR).mkdir(mode=0o700)
            (root / "wolf").mkdir(mode=0o700)
            _write_exclusive(root / OWNER_FILE, json.dumps(
                {"tool": "now-host-transaction", "schema_version": SCHEMA}).encode())
            state = {"tool": "now-host-transaction", "schema_version": SCHEMA,
                     "runtime": "not_started", "active": None, "previous": None}
            # A failure writing a later generation must leave a valid,
            # recognizable workspace that can be safely retried.
            _write_current(root, state)
        if state.get("active") is not None:
            # Never follow a swapped data-directory symlink during updates.
            if (root / "wolf").is_symlink() or not (root / "wolf").is_dir():
                raise ValueError("Persistent Wolf directory cannot be trusted")
        else:
            if (root / "wolf").is_symlink() or not (root / "wolf").is_dir():
                raise ValueError("Persistent Wolf directory cannot be trusted")
        content_hash = hashlib.sha256()
        for name in INPUT_FILES:
            content_hash.update(name.encode() + b"\x00" + files[name] + b"\x00")
        generation = content_hash.hexdigest()
        generations = root / GEN_DIR
        if generations.is_symlink() or not generations.is_dir():
            raise ValueError("Invalid generation storage")
        path = generations / generation
        if path.exists() or path.is_symlink():
            for name in INPUT_FILES:
                if _read_bounded_regular(path / name) != files[name]:
                    raise ValueError("Existing generation has been changed")
        else:
            path.mkdir(mode=0o700)
            new_generation = path
            for name in INPUT_FILES:
                _write_exclusive(path / name, files[name])
        if state["active"] != generation:
            update = dict(state)
            update["previous"] = state["active"]
            update["active"] = generation
            _write_current(root, update)
            state = update
        return {"result": "prepared_not_deployed", "workspace": str(root),
                "generation": generation, "replaced_existing": not created_root,
                "runtime": "not_started"}
    except Exception:
        if new_generation is not None:
            shutil.rmtree(new_generation)
        raise
    finally:
        _release_lock(root, lock)


def rollback(workspace: Path) -> dict:
    """Rollback only the active configuration pointer; never remove data."""
    root = _validate_workspace(workspace)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("No managed workspace")
    lock = _acquire_lock(root)
    try:
        state = _state(root)
        if not state or not state.get("previous"):
            raise ValueError("No known previous generation for rollback")
        updated = dict(state)
        updated["active"], updated["previous"] = state["previous"], state["active"]
        _write_current(root, updated)
        return {"result": "configuration_rolled_back", "workspace": str(root),
                "generation": updated["active"], "runtime": "not_started"}
    finally:
        _release_lock(root, lock)


def main() -> int:
    parser = argparse.ArgumentParser(description="NOW Host configuration transaction prototype; never starts Wolf")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", type=Path, help="Review bundle from host_stage.py")
    group.add_argument("--rollback", action="store_true")
    parser.add_argument("--workspace", type=Path, required=True,
                        help="Managed test directory, direct child of /tmp only")
    args = parser.parse_args()
    try:
        result = rollback(args.workspace) if args.rollback else prepare(args.prepare, args.workspace)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    print("No Docker operation was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
