#!/usr/bin/env python3
"""Durable, reversible synthetic-ID album-art recovery for existing Bruiser host.

Run *on the host* under the Docker-capable account. Rebuilds FROM the exact
currently running, already-patched DroppedNeedle image. Changes only the
OpenSubsonic cover route and its own new helper. No audio file/tag writes and
no unrelated Docker services. Works with the previous Discover-budget fix.
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

CONTAINER = "droppedneedle"
SERVICE = "droppedneedle"
ROUTER = "/app/api/compat/subsonic/router.py"
HELPER = "/app/api/compat/subsonic/bruiser_cover_recovery.py"
PATCH_LABEL = "bruiser-synthetic-art-v1"
EXPECTED = '''    if kind == "album":
        if await c.services.view.get_album(internal, user=c.user) is None:
            raise SubsonicError(70, "Album not found")
        result = await c.services.coverart.get_release_group_cover(
            internal, size, is_disconnected=disc
        )
    elif kind == "track":'''
REPLACEMENT = '''    if kind == "album":
        album = await c.services.view.get_album(internal, user=c.user)
        if album is None:
            raise SubsonicError(70, "Album not found")
        if is_local_album_id(internal):
            # Never send a synthetic UUIDv5 to Cover Art Archive. For a local
            # album: folder/embedded first, then exact artist+album+year MBID.
            # Cache only verified raster under the LOCAL ID, across restarts.
            result = await recover_album_cover(c.services, album, internal, size)
            if result is None:
                return Response(
                    content=_PLACEHOLDER_SVG, media_type="image/svg+xml",
                    headers={"Cache-Control": "private, no-store"},
                )
        else:
            result = await c.services.coverart.get_release_group_cover(
                internal, size, is_disconnected=disc
            )
    elif kind == "track":'''
IMPORT = '''from api.compat.subsonic.bruiser_cover_recovery import (
    is_local_album_id,
    recover_album_cover,
)
'''
INSERT_BEFORE = "from api.compat.subsonic.auth import resolve_subsonic_user\n"


class InstallError(Exception):
    pass


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(args, text=True, check=False,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if result.returncode:
        detail = result.stderr.strip()[-900:] if capture and result.stderr else ""
        raise InstallError(f"Command failed: {' '.join(args[:6])} {detail}")
    return result.stdout if capture else ""


def inspect() -> dict:
    data = json.loads(run("docker", "inspect", CONTAINER, capture=True))
    if len(data) != 1:
        raise InstallError("Expected exactly one running DroppedNeedle container")
    return data[0]


def mounts(info: dict) -> list[tuple[str, str, str, bool]]:
    return sorted((m["Type"], m["Source"], m["Destination"], bool(m["RW"]))
                  for m in info["Mounts"])


def patch_router(source: str) -> str:
    if source.count(EXPECTED) != 1 or source.count(INSERT_BEFORE) != 1:
        raise InstallError("DroppedNeedle route version differs; no files changed")
    if "bruiser_cover_recovery" in source:
        raise InstallError("An art recovery patch is already in this route")
    patched = source.replace(EXPECTED, REPLACEMENT, 1).replace(
        INSERT_BEFORE, IMPORT + INSERT_BEFORE, 1)
    compile(patched, ROUTER, "exec")
    return patched


def atomic_json(path: Path, data: dict) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, filename = tempfile.mkstemp(prefix=".bruiser-art-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            os.fchmod(f.fileno(), mode)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(filename, path)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def healthcheck() -> bool:
    import time
    for _ in range(30):
        result = subprocess.run(["docker", "exec", CONTAINER, "sh", "-c",
            'curl -fsS --max-time 4 "http://127.0.0.1:${PORT:-8688}${BASE_PATH:-}/health" >/dev/null'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if result.returncode == 0:
            return True
        time.sleep(3)
    return False


def install(compose: Path, helper_file: Path) -> None:
    if not compose.is_file() or not helper_file.is_file():
        raise InstallError("Compose file or bundled cover helper missing")
    run("docker", "compose", "-f", str(compose), "config", "--quiet")
    original = json.loads(compose.read_text(encoding="utf-8"))
    service = original.get("services", {}).get(SERVICE, {})
    original_image = service.get("image", "")
    before = inspect()
    if before["State"]["Status"] != "running":
        raise InstallError("DroppedNeedle must be running before upgrade")
    if (before["Config"].get("Labels") or {}).get("com.docker.compose.service") != SERVICE:
        raise InstallError("Container is not the expected Compose service")
    if not isinstance(original_image, str):
        raise InstallError("Invalid Compose image")
    if original_image.startswith("bruiser/droppedneedle-art:"):
        if before["Config"]["Image"] == original_image:
            print(f"ALREADY PERSISTENT: {original_image}")
            return
        raise InstallError("Compose art image does not match running container")
    if not original_image.startswith("bruiser/droppedneedle-discover:"):
        raise InstallError(
            "Requires the existing permanent Discover image first; "
            "use deploy/music/install_discover_hotfix.py on the host"
        )
    original_mounts = mounts(before)
    if not {"/data", "/app/config", "/app/cache", "/app/plugins", "/app/imports"}.issubset(
        {m[2] for m in original_mounts}
    ):
        raise InstallError("Expected persistent music volumes are missing")
    source_id = before["Image"]
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", source_id):
        raise InstallError("Unexpected local image ID")
    short = source_id[7:19]
    base_tag = f"bruiser/droppedneedle-art-base:{short}"
    art_tag = f"bruiser/droppedneedle-art:{short}-v1"
    # Only COPY a tested module patch into the exact running image (not latest).
    run("docker", "tag", source_id, base_tag)
    route_source = run("docker", "run", "--rm", "--network", "none",
                       "--entrypoint", "/bin/cat", base_tag, ROUTER, capture=True)
    patched_route = patch_router(route_source)
    live_route = run("docker", "exec", CONTAINER, "/bin/cat", ROUTER, capture=True)
    if live_route != route_source:
        raise InstallError("Running router differs from pinned image: aborting")
    discover = run("docker", "exec", CONTAINER, "/bin/cat",
                   "/app/services/discover/homepage_service.py", capture=True)
    if "OptionalWorkBudget(remaining=64)" not in discover:
        raise InstallError("Would lose the proven Discover fix: refusing to deploy")
    helper_source = helper_file.read_text(encoding="utf-8")
    compile(helper_source, HELPER, "exec")
    directory = Path.home() / "bruiser-repairs" / (
        "album-art-persistent-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    backup = directory / "compose.before.json"
    backup.write_bytes(compose.read_bytes())
    backup.chmod(0o600)
    (directory / "router.before.py").write_text(route_source, encoding="utf-8")
    (directory / "router.py").write_text(patched_route, encoding="utf-8")
    (directory / "bruiser_cover_recovery.py").write_text(helper_source, encoding="utf-8")
    (directory / "Dockerfile").write_text(
        f"FROM {base_tag}\n"
        f"COPY --chown=1000:1000 router.py {ROUTER}\n"
        f"COPY --chown=1000:1000 bruiser_cover_recovery.py {HELPER}\n"
        f'LABEL io.bruiser.fix="{PATCH_LABEL}"\n'
        "RUN python -c \"import ast; ast.parse(open('"
        + ROUTER + "', encoding='utf8').read()); ast.parse(open('"
        + HELPER + "', encoding='utf8').read())\"\n",
        encoding="utf-8",
    )
    (directory / ".dockerignore").write_text(
        "*\n!Dockerfile\n!router.py\n!bruiser_cover_recovery.py\n",
        encoding="utf-8",
    )
    print(f"Rollback backup: {backup}", flush=True)
    print("Building persistent album-art image from pinned Discover image...", flush=True)
    run("docker", "build", "--pull=false", "-t", art_tag, str(directory))
    (directory / "manifest.json").write_text(json.dumps({
        "fix": PATCH_LABEL, "original_image": original_image,
        "base_image_id": source_id, "patched_image": art_tag,
        "router_source_sha256": hashlib.sha256(route_source.encode()).hexdigest(),
        "helper_source_sha256": hashlib.sha256(helper_source.encode()).hexdigest(),
    }, indent=2) + "\n", encoding="utf-8")
    updated = json.loads(json.dumps(original))
    updated["services"][SERVICE]["image"] = art_tag
    changed = False
    try:
        if json.loads(compose.read_text(encoding="utf-8")) != original:
            raise InstallError("Compose changed during build; refusing to overwrite")
        atomic_json(compose, updated)
        changed = True
        run("docker", "compose", "-f", str(compose), "config", "--quiet")
        run("docker", "compose", "-f", str(compose), "up", "-d", "--no-deps",
            "--force-recreate", SERVICE)
        after = inspect()
        if after["Config"]["Image"] != art_tag:
            raise InstallError("Recreated service did not use patched art image")
        if mounts(after) != original_mounts:
            raise InstallError("Music volumes changed during recreation")
        if not healthcheck():
            raise InstallError("DroppedNeedle health check failed")
    except Exception:
        if changed:
            print("Deployment failed: restoring original Compose/service.", file=sys.stderr)
            try:
                atomic_json(compose, json.loads(backup.read_text(encoding="utf-8")))
                run("docker", "compose", "-f", str(compose), "up", "-d",
                    "--no-deps", "--force-recreate", SERVICE)
            except Exception as error:
                print(f"ROLLBACK FAILED: {error}; backup: {backup}", file=sys.stderr)
        raise
    print("SUCCESS: Persistent library artwork recovery installed.")
    print(f"Image: {art_tag}")
    print(f"Compose: {compose}")
    print("This includes the existing Discover-budget fix.")
    print(f"Rollback backup: {backup}")


def main() -> int:
    try:
        install(Path(os.environ.get(
            "BRUISER_MUSIC_COMPOSE", "~/music-vpn/compose.json"
        )).expanduser(), Path(__file__).resolve().with_name("bruiser_cover_recovery.py"))
    except (InstallError, OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
