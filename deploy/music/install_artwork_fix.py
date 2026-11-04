#!/usr/bin/env python3
"""Install the Bruiser Music artwork resolver without touching music data.

Requires an existing approved DroppedNeedle/Discover installation at
~/music-vpn/compose.json. The new image starts from the exact container image
currently running (including the known-good Discover budget fix). We replace
only the Subsonic cover endpoint and add one read-only resolver module.

Usage from repo root on the host:
    python3 deploy/music/install_artwork_fix.py
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
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
import time

CONTAINER = "droppedneedle"
ROUTER = "/app/api/compat/subsonic/router.py"
RESOLVER = "/app/services/compat/bruiser_cover_resolver.py"
COMPOSE = Path.home() / "music-vpn/compose.json"
VERSION = "bruiser-artwork-v1"

EXACT_ORIGINAL = """        if await c.services.view.get_album(internal, user=c.user) is None:
            raise SubsonicError(70, "Album not found")
        result = await c.services.coverart.get_release_group_cover(
            internal, size, is_disconnected=disc
        )
"""
EXACT_REPLACEMENT = """        album = await c.services.view.get_album(internal, user=c.user)
        if album is None:
            raise SubsonicError(70, "Album not found")
        # Local folder and embedded art remain first in native CoverArtRepository.
        result = await c.services.coverart.get_release_group_cover(
            internal, size, is_disconnected=disc
        )
        if result is None:
            # Synthetic UUIDv5 identities are local keys, not MusicBrainz IDs.
            # Preserve authorization above and consult only verified candidates.
            from services.compat.bruiser_cover_resolver import missing_album_cover
            result = await missing_album_cover(
                album, internal, c.services.coverart, size, is_disconnected=disc
            )
"""

class InstallError(Exception):
    pass

def run(*args: str, output: bool = False) -> str:
    result = subprocess.run(args, check=False, text=True,
                            stdout=subprocess.PIPE if output else None,
                            stderr=subprocess.PIPE if output else None)
    if result.returncode:
        detail = (result.stderr or "")[-700:] if output else ""
        raise InstallError(f"Command failed ({result.returncode}): {args[0]} {args[1] if len(args)>1 else ''} {detail}")
    return result.stdout if output else ""

def docker_info() -> dict:
    results = json.loads(run("docker", "inspect", CONTAINER, output=True))
    if len(results) != 1:
        raise InstallError("Expected one DroppedNeedle container")
    return results[0]

def mounts(info: dict) -> list[tuple]:
    return sorted(
        (m["Type"], m["Source"], m["Destination"], bool(m["RW"]))
        for m in info["Mounts"]
    )

def load_compose() -> dict:
    try:
        content = json.loads(COMPOSE.read_text())
        service = content["services"][CONTAINER]
        if not isinstance(service, dict) or not isinstance(service.get("image"), str):
            raise ValueError("Missing DroppedNeedle Compose image")
        return content
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise InstallError(f"Missing/invalid host music Compose: {exc}") from exc

def write_atomic(data: dict, mode: int) -> None:
    fd, path = tempfile.mkstemp(prefix=".bruiser-music-", dir=COMPOSE.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            os.fchmod(handle.fileno(), mode)
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(path, COMPOSE)
    finally:
        if os.path.exists(path):
            os.unlink(path)

def patch_router(source: str) -> str:
    if source.count(EXACT_ORIGINAL) != 1:
        raise InstallError("Unexpected Subsonic source version; no patch applied")
    result = source.replace(EXACT_ORIGINAL, EXACT_REPLACEMENT)
    ast.parse(result, filename=ROUTER)
    return result

def is_healthy() -> bool:
    for _ in range(30):
        status = subprocess.run(
            ["docker", "exec", CONTAINER, "sh", "-c",
             'curl -fsS --max-time 4 "http://127.0.0.1:${PORT:-8688}${BASE_PATH:-}/health" >/dev/null'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if status.returncode == 0:
            return True
        time.sleep(3)
    return False

def install() -> None:
    if not shutil.which("docker"):
        raise InstallError("Docker is not installed")
    if not COMPOSE.is_file():
        raise InstallError(f"Host Compose not found: {COMPOSE}")
    root = Path(__file__).resolve().parent
    resolver = (root / "bruiser_cover_resolver.py").read_text(encoding="utf-8")
    ast.parse(resolver, filename=RESOLVER)
    run("docker", "compose", "-f", str(COMPOSE), "config", "--quiet")
    original = load_compose()
    old_image = original["services"][CONTAINER]["image"]
    info = docker_info()
    if info["State"]["Status"] != "running":
        raise InstallError("DroppedNeedle must be running before patching")
    if (info["Config"].get("Labels") or {}).get("com.docker.compose.service") != CONTAINER:
        raise InstallError("Unexpected DroppedNeedle Compose service")
    if old_image.startswith("bruiser/droppedneedle-artwork:"):
        if info["Config"]["Image"] == old_image:
            print(f"ALREADY INSTALLED: {old_image}")
            return
        raise InstallError("Artwork Compose image does not match active container")
    if not old_image.startswith("bruiser/droppedneedle-discover:"):
        raise InstallError("Expected approved Discover patched base; refusing to replace unknown image")
    if info["Config"]["Image"] != old_image:
        raise InstallError("Running image differs from Compose configuration")
    original_mounts = mounts(info)
    expected = {"/data","/app/config","/app/cache","/app/plugins","/app/imports"}
    if not expected.issubset({x[2] for x in original_mounts}):
        raise InstallError("Unexpected persistent mount destinations")
    source_image = info["Image"]
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", source_image):
        raise InstallError("Unrecognized running Docker image digest")
    # Confirm this build contains the Discover fix. Never regress it.
    discover = run("docker", "exec", CONTAINER, "/bin/cat",
                   "/app/services/discover/homepage_service.py", output=True)
    if "optional_work_budget(OptionalWorkBudget(remaining=64))" not in discover:
        raise InstallError("Existing working Discover fix is missing; refusing upgrade")
    original_router = run("docker", "exec", CONTAINER,
                          "/bin/cat", ROUTER, output=True)
    patched_router = patch_router(original_router)
    image_id = source_image.split(":",1)[1][:12]
    base = f"bruiser/droppedneedle-artbase:{image_id}"
    image = f"bruiser/droppedneedle-artwork:{image_id}-v1"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = Path.home() / "bruiser-repairs" / ("artwork-persistent-" + stamp)
    directory.mkdir(parents=True,mode=0o700,exist_ok=False)
    (directory/"compose.before.json").write_bytes(COMPOSE.read_bytes())
    (directory/"original_router.py").write_text(original_router)
    (directory/"router.py").write_text(patched_router)
    (directory/"bruiser_cover_resolver.py").write_text(resolver)
    (directory/".dockerignore").write_text(
        "*\n!Dockerfile\n!router.py\n!bruiser_cover_resolver.py\n")
    (directory/"Dockerfile").write_text(
        f"FROM {base}\n"
        f"COPY --chown=1000:1000 router.py {ROUTER}\n"
        f"COPY --chown=1000:1000 bruiser_cover_resolver.py {RESOLVER}\n"
        f'LABEL io.bruiser.fix="{VERSION}"\n'
        "RUN python -c \"import ast; ast.parse(open('"
        + ROUTER + "').read()); ast.parse(open('"
        + RESOLVER + "').read())\"\n"
    )
    (directory/"manifest.json").write_text(json.dumps({
        "version":VERSION,
        "base":old_image,"image":image,"image_sha256":source_image,
        "router_before_sha256":hashlib.sha256(original_router.encode()).hexdigest(),
        "router_after_sha256":hashlib.sha256(patched_router.encode()).hexdigest(),
        "resolver_sha256":hashlib.sha256(resolver.encode()).hexdigest(),
    },indent=2)+"\n")
    for item in directory.iterdir():
        if item.is_file():
            item.chmod(0o600)
    print(f"Rollback backup: {directory}",flush=True)
    run("docker", "tag", source_image, base)
    print(f"Building persistent artwork image from pinned Discover image {image_id}...",flush=True)
    run("docker", "build", "--pull=false", "-t", image, str(directory))
    updated = json.loads(json.dumps(original))
    updated["services"][CONTAINER]["image"] = image
    changed = False
    try:
        if load_compose() != original:
            raise InstallError("Compose was modified during the build; refusing")
        write_atomic(updated,stat.S_IMODE(COMPOSE.stat().st_mode))
        changed = True
        run("docker", "compose", "-f", str(COMPOSE), "config", "--quiet")
        run("docker", "compose", "-f", str(COMPOSE),
            "up", "-d", "--no-deps", "--force-recreate", CONTAINER)
        after = docker_info()
        if after["Config"]["Image"] != image:
            raise InstallError("New container did not use artwork image")
        if mounts(after) != original_mounts:
            raise InstallError("Persistent mounts changed unexpectedly")
        if not is_healthy():
            raise InstallError("DroppedNeedle failed health check")
        installed = run("docker", "exec", CONTAINER,
                        "/bin/cat", RESOLVER, output=True)
        if installed != resolver:
            raise InstallError("Installed artwork resolver differs from source")
    except Exception:
        if changed:
            print("Deployment error: rolling back original image...",file=sys.stderr,flush=True)
            try:
                write_atomic(original,stat.S_IMODE(COMPOSE.stat().st_mode))
                run("docker", "compose", "-f", str(COMPOSE),
                    "up", "-d", "--no-deps", "--force-recreate", CONTAINER)
            except Exception as exc:
                print(f"ROLLBACK FAILED: {exc}; restore from {directory}",
                      file=sys.stderr)
        raise
    print("SUCCESS: persistent artwork resolver installed.")
    print(f"Image: {image}")
    print(f"Compose: {COMPOSE}")
    print(f"Backup: {directory}")
    print("Next: verify Blue Sky Noise / Man on the Moon from a client; a health check alone does not verify their images.")

if __name__ == "__main__":
    try:
        install()
    except (OSError, InstallError, ValueError) as e:
        print(f"ERROR: {e}",file=sys.stderr)
        sys.exit(1)
