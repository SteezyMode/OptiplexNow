#!/usr/bin/env python3
"""Persist the tested DroppedNeedle Discover fix in an existing Bruiser host.

Targets only the existing music-vpn Compose service `droppedneedle`. Pins the
currently running upstream image by local image ID, builds a tiny derived image,
and changes only the one Compose image field. No Docker/Compose service other
than DroppedNeedle is ever recreated. No image pulls or library writes.

Use on the OptiPlex host, not on a client:
    python3 install_discover_hotfix.py
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

SOURCE_PATH = "/app/services/discover/homepage_service.py"
CONTAINER = "droppedneedle"
SERVICE = "droppedneedle"
OLD_IMPORT = "import OptionalWorkDeferred, optional_work_budget,"
NEW_IMPORT = "import OptionalWorkBudget, OptionalWorkDeferred, optional_work_budget,"
OLD_BUDGET = "with optional_work_budget(), optional_dispatch_guard("
NEW_BUDGET = (
    "with optional_work_budget(OptionalWorkBudget(remaining=64)), "
    "optional_dispatch_guard("
)
PATCH_ID = "discover-budget64-v1"


class RepairError(Exception):
    pass


def call(*args: str, capture: bool = False, input: str | None = None) -> str:
    cmd = list(args)
    result = subprocess.run(cmd, input=input, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None,
                            check=False)
    if result.returncode:
        detail = (result.stderr or "").strip()[-900:] if capture else ""
        raise RepairError(f"Command failed ({result.returncode}): {' '.join(cmd[:6])} {detail}")
    return result.stdout if capture else ""


def docker_info() -> dict[str, Any]:
    raw = call("docker", "inspect", CONTAINER, capture=True)
    data = json.loads(raw)
    if len(data) != 1:
        raise RepairError("Expected exactly one DroppedNeedle container")
    return data[0]


def mount_fingerprint(data: dict[str, Any]) -> list[tuple[str, str, str, bool]]:
    return sorted(
        (m["Type"], m["Source"], m["Destination"], bool(m["RW"]))
        for m in data["Mounts"]
    )


def make_patch(source: str) -> str:
    for fragment in (OLD_IMPORT, OLD_BUDGET):
        if source.count(fragment) != 1:
            raise RepairError("Unexpected DroppedNeedle source version: refusing to patch")
    result = source.replace(OLD_IMPORT, NEW_IMPORT).replace(OLD_BUDGET, NEW_BUDGET)
    compile(result, SOURCE_PATH, "exec")
    return result


def load_compose(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("services"), dict):
        raise RepairError("Expected JSON Docker Compose file with services")
    service = data["services"].get(SERVICE)
    if not isinstance(service, dict):
        raise RepairError("DroppedNeedle service absent from Compose")
    return data


def compose_image(data: dict[str, Any]) -> str:
    image = data["services"][SERVICE].get("image")
    if not isinstance(image, str) or not image:
        raise RepairError("DroppedNeedle Compose service has no image")
    return image


def write_compose_atomic(path: Path, data: dict[str, Any]) -> None:
    st = path.stat()
    fd, name = tempfile.mkstemp(prefix=".compose-discover-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            os.fchmod(file.fileno(), stat.S_IMODE(st.st_mode))
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def restore_compose(path: Path, backup: Path) -> None:
    # Safe because the script only mutates the Compose file during this single
    # guarded operation, not across an unattended/background transaction.
    original = json.loads(backup.read_text(encoding="utf-8"))
    write_compose_atomic(path, original)


def health_check(attempts: int = 30) -> bool:
    import time
    for _ in range(attempts):
        result = subprocess.run(
            ["docker", "exec", CONTAINER, "sh", "-c",
             'curl -fsS --max-time 4 "http://127.0.0.1:${PORT:-8688}${BASE_PATH:-}/health" >/dev/null'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if result.returncode == 0:
            return True
        time.sleep(3)
    return False


def execute(compose: Path) -> None:
    if not compose.is_file():
        raise RepairError(f"Expected deployed Compose file not found: {compose}")
    if not shutil.which("docker"):
        raise RepairError("Docker is not installed")
    call("docker", "compose", "-f", str(compose), "config", "--quiet")
    original_compose = load_compose(compose)
    original_image = compose_image(original_compose)
    if original_image.startswith("bruiser/droppedneedle-discover:"):
        info = docker_info()
        if info["Config"]["Image"] == original_image:
            print(f"ALREADY PERSISTENT: {original_image}")
            return
        raise RepairError("Bruiser-patched Compose image does not match running container")
    if not original_image.startswith(("droppedneedle/droppedneedle:", "droppedneedle/droppedneedle@")):
        raise RepairError(f"Unexpected upstream image: {original_image}")

    before = docker_info()
    labels = before["Config"].get("Labels") or {}
    if labels.get("com.docker.compose.service") != SERVICE:
        raise RepairError("Running container isn't managed by expected Compose service")
    if before["State"]["Status"] != "running":
        raise RepairError("Original DroppedNeedle container isn't running")
    mounts_before = mount_fingerprint(before)
    required_mounts = {"/data", "/app/config", "/app/cache", "/app/plugins", "/app/imports"}
    if not required_mounts.issubset({m[2] for m in mounts_before}):
        raise RepairError("Expected DroppedNeedle persistent mounts missing; refusing replacement")

    source_image_id = before["Image"]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", source_image_id):
        raise RepairError("Unexpected Docker image digest")
    short = source_image_id.split(":", 1)[1][:12]
    base_tag = f"bruiser/droppedneedle-base:{short}"
    derived_tag = f"bruiser/droppedneedle-discover:{short}-b64-v1"

    # Create the derived image from the exact image used by the live container,
    # not the mutable :latest tag. No unexpected upgrades/pulls.
    directory = Path.home() / "bruiser-repairs" / (
        "discover-persistent-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    (directory / "compose.before.json").write_bytes(compose.read_bytes())
    os.chmod(directory / "compose.before.json", 0o600)
    print(f"Rollback backup: {directory}", flush=True)
    print(f"Base image pinned to running digest: {source_image_id}", flush=True)
    call("docker", "tag", source_image_id, base_tag)
    source = call("docker", "run", "--rm", "--network", "none", "--entrypoint",
                  "/bin/cat", base_tag, SOURCE_PATH, capture=True)
    (directory / "homepage.original.py").write_text(source, encoding="utf-8")
    patched = make_patch(source)
    live = call("docker", "exec", CONTAINER, "/bin/cat", SOURCE_PATH, capture=True)
    if live not in (source, patched):
        raise RepairError("Live Discover module differs from the upstream or tested hotfix; aborting")
    (directory / "homepage_service.py").write_text(patched, encoding="utf-8")
    (directory / "Dockerfile").write_text(
        f"FROM {base_tag}\n"
        f"COPY --chown=1000:1000 homepage_service.py {SOURCE_PATH}\n"
        f'LABEL io.bruiser.fix="{PATCH_ID}"\n'
        "RUN python -c \"import ast; ast.parse(open('"
        + SOURCE_PATH
        + "', encoding='utf-8').read())\"\n",
        encoding="utf-8",
    )
    # Keep backups (which may contain Compose secrets) out of Docker build context.
    (directory / ".dockerignore").write_text("*\n!Dockerfile\n!homepage_service.py\n", encoding="utf-8")
    print("Building persistent, versioned DroppedNeedle image...", flush=True)
    call("docker", "build", "--pull=false", "-t", derived_tag, str(directory))
    (directory / "patch-manifest.json").write_text(json.dumps({
        "patch": PATCH_ID,
        "upstream_compose_image": original_image,
        "source_image_id": source_image_id,
        "base_tag": base_tag,
        "patched_image": derived_tag,
        "original_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "patched_source_sha256": hashlib.sha256(patched.encode()).hexdigest(),
    }, indent=2) + "\n", encoding="utf-8")

    updated_compose = json.loads(json.dumps(original_compose))
    updated_compose["services"][SERVICE]["image"] = derived_tag
    changed = False
    try:
        # Only one field is altered. Any existing service mounts/env/ports,
        # neighboring containers and Docker networks remain as deployed.
        current = load_compose(compose)
        if current != original_compose:
            raise RepairError("Compose file changed during preparation; aborting safely")
        write_compose_atomic(compose, updated_compose)
        changed = True
        call("docker", "compose", "-f", str(compose), "config", "--quiet")
        print("Recreating only droppedneedle; persistent volumes are preserved...", flush=True)
        call("docker", "compose", "-f", str(compose), "up", "-d", "--no-deps", "--force-recreate", SERVICE)
        after = docker_info()
        if after["Config"]["Image"] != derived_tag:
            raise RepairError("Recreated container didn't use the patched image")
        if mount_fingerprint(after) != mounts_before:
            raise RepairError("Container mounts changed unexpectedly")
        if not health_check():
            raise RepairError("Recreated DroppedNeedle failed the HTTP health check")
    except Exception:
        if changed:
            print("Deployment failed: restoring original Compose image...", file=sys.stderr, flush=True)
            try:
                restore_compose(compose, directory / "compose.before.json")
                call("docker", "compose", "-f", str(compose), "up", "-d", "--no-deps", "--force-recreate", SERVICE)
                print("Original DroppedNeedle restored.", file=sys.stderr)
            except Exception as rollback_error:
                print(f"ROLLBACK FAILED: {rollback_error}; backup: {directory}", file=sys.stderr)
        raise

    print("SUCCESS: DroppedNeedle Discover fix is persistent.")
    print(f"Compose: {compose}")
    print(f"Pinned image: {derived_tag}")
    print(f"Backup: {directory}")
    print("Survives Docker restarts, Compose recreation and unrelated image updates.")
    print("Future upstream DroppedNeedle upgrades require an intentional rebase/retest.")


def main() -> int:
    # Keep default constrained to the actual host's music-vpn stack. Alternative
    # paths are opt-in for integration testing or future compatible deployments.
    compose = Path(os.environ.get("BRUISER_MUSIC_COMPOSE", "~/music-vpn/compose.json")).expanduser()
    try:
        execute(compose)
    except (RepairError, OSError, ValueError, KeyError, json.JSONDecodeError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
