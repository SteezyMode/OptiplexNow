"""Create a unique Wolf NVIDIA userspace volume on a clean host.

No host driver install, kernel change, Docker volume reuse or deletion. The
official NVIDIA .run must match an owner-provided SHA256 before it executes
inside the pinned-recipe build. Caller owns host-state journaling and locks.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

import host_preflight

DRIVER_RE = re.compile(r"^[0-9]{3}\.[0-9]{1,3}\.[0-9]{1,3}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
RECIPE = Path(__file__).with_name("nvidia-driver.Dockerfile")
VERSION_MINIMUM = (530, 30, 2)


class DriverError(ValueError):
    pass


def validate_installer_sha(value: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise DriverError("NVIDIA installer SHA256 must be exactly 64 lowercase hex digits")
    return value


def validate_driver_version(value: str) -> str:
    if not isinstance(value, str) or not DRIVER_RE.fullmatch(value):
        raise DriverError("NVIDIA kernel driver version cannot be verified")
    if tuple(int(x) for x in value.split(".")) < VERSION_MINIMUM:
        raise DriverError("NVIDIA driver is too old for Wolf")
    return value


def current_driver_version(root: Path = Path("/")) -> str:
    value = host_preflight.read_small(root / "sys/module/nvidia/version")
    return validate_driver_version((value or "").strip())


def volume_name(driver_version: str, installer_sha: str) -> str:
    version = validate_driver_version(driver_version)
    digest = validate_installer_sha(installer_sha)
    return "now-nvidia-" + version.replace(".", "-") + "-" + digest[:16]


def prepare_volume(docker, *, driver_version: str, installer_sha: str,
                   build_context: Path, progress) -> dict:
    """Use *real* Docker on a new volume only. Return verified volume identity.

    Docker's documented volume copy-up populates /usr/nvidia at create time.
    The temporary container is never started, preserving the host.
    """
    version = validate_driver_version(driver_version)
    sha = validate_installer_sha(installer_sha)
    name = volume_name(version, sha)
    if not RECIPE.is_file() or RECIPE.is_symlink():
        raise DriverError("Packaged NVIDIA driver recipe is missing or untrusted")
    if not build_context.is_dir() or build_context.is_symlink():
        raise DriverError("Dedicated empty Docker build context is unavailable")
    if any(build_context.iterdir()):
        raise DriverError("Driver build context must be empty")
    existing = docker(["volume", "ls", "--quiet", "--filter", "name=^" + name + "$"])
    if existing:
        raise DriverError("NVIDIA driver volume already exists; never adopt or overwrite")
    image = "now-nvidia-driver:" + version + "-" + sha[:16]
    progress("building_nvidia_driver")
    # The recipe downloads only the exact version of NVIDIA's official .run
    # and checks the FULL SHA256 before executing it in a build container.
    docker([
        "build", "--quiet", "--no-cache", "--file", str(RECIPE),
        "--tag", image, "--build-arg", "NV_VERSION=" + version,
        "--build-arg", "NV_SHA256=" + sha, str(build_context),
    ], timeout=1800)
    progress("creating_nvidia_volume")
    result = docker([
        "volume", "create",
        "--label", "io.optiplex-now.managed=host-install-pilot",
        "--label", "io.optiplex-now.nvidia.version=" + version,
        "--label", "io.optiplex-now.nvidia.installer-sha256=" + sha,
        name,
    ])
    if result != name:
        raise DriverError("Docker created an unexpected volume; refusing startup")
    labels_raw = docker([
        "volume", "inspect", "--format", "{{json .Labels}}", name])
    try:
        labels = json.loads(labels_raw)
    except (ValueError, TypeError) as exc:
        raise DriverError("Cannot verify created driver volume") from exc
    if not isinstance(labels, dict) or any(
        labels.get(key) != expected for key, expected in (
            ("io.optiplex-now.managed", "host-install-pilot"),
            ("io.optiplex-now.nvidia.version", version),
            ("io.optiplex-now.nvidia.installer-sha256", sha),
        )
    ):
        raise DriverError("Created driver volume ownership does not match")

    progress("populating_nvidia_volume")
    created = docker([
        "create", "--mount", "type=volume,source=" + name + ",target=/usr/nvidia",
        image, "/bin/sh",
    ])
    if not re.fullmatch(r"[a-f0-9]{64}", created):
        raise DriverError("Could not identify driver-copy container; manual review required")
    # 'docker create' populates a fresh named volume from image content.
    # Do NOT start the container or remove any volume.
    docker(["rm", created])
    progress("driver_volume_ready")
    return {"name": name, "version": version, "installer_sha256": sha}
