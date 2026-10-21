#!/usr/bin/env python3
"""Stage a Wolf Compose configuration for review. NEVER deploy host services.

Writes only to a new explicit output directory, refuses all overwrites,
requires an immutable Wolf digest, and has NO apply, start or uninstall API.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import host_plan
import host_preflight

STAGE_SCHEMA = 1
IMAGE_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
RENDER_RE = re.compile(r"^/dev/dri/renderD[0-9]{3,5}$")
PROFILE = "now-manual-review-required"
PROTECTED_ROOTS = ("/etc", "/var", "/usr", "/run", "/dev", "/proc", "/sys", "/boot")


def validate_digest(digest: str) -> str:
    if not isinstance(digest, str) or not IMAGE_RE.fullmatch(digest):
        raise ValueError("Wolf image requires sha256: followed by 64 lowercase hex digits")
    return "ghcr.io/games-on-whales/wolf@" + digest


def validate_render_node(device: str) -> str:
    if not isinstance(device, str) or not RENDER_RE.fullmatch(device):
        raise ValueError("Specify an explicit /dev/dri/renderD### device; do not guess")
    return device


def make_bundle(plan: dict, *, digest: str, render_node: str) -> dict[str, str]:
    """Build inert review artifacts based on a blocked planner result."""
    image = validate_digest(digest)
    render = validate_render_node(render_node)
    if (not isinstance(plan, dict) or plan.get("tool") != "now-host-plan"
            or plan.get("schema_version") != host_plan.PLAN_SCHEMA
            or plan.get("mode") != "read_only_preview"
            or plan.get("decision") != "blocked"
            or plan.get("may_apply") is not False
            or plan.get("changes_performed") is not False):
        raise ValueError("Only a blocked NOW Host plan can be staged")

    # JSON syntax is valid YAML 1.2; Docker Compose parses compose.yaml.
    # Profile and pull_policy=never prevent accidental default startup/pull.
    # No container_name: avoid colliding with unrelated 'wolf' installations.
    compose = {
        "name": "optiplex-now-host-pilot",
        "services": {"wolf": {
            "profiles": [PROFILE],
            "image": image,
            "pull_policy": "never",
            "network_mode": "host",
            "restart": "no",
            "environment": {
                "NVIDIA_DRIVER_CAPABILITIES": "all",
                "NVIDIA_VISIBLE_DEVICES": "all",
                "WOLF_RENDER_NODE": render,
            },
            "volumes": [
                "./wolf:/etc/wolf:rw",
                "/var/run/docker.sock:/var/run/docker.sock:rw",
                "/dev:/dev:rw",
                "/run/udev:/run/udev:rw",
            ],
            "devices": [
                "/dev/dri:/dev/dri", "/dev/uinput:/dev/uinput",
                "/dev/uhid:/dev/uhid",
            ],
            "device_cgroup_rules": ["c 13:* rmw"],
            "deploy": {"resources": {"reservations": {"devices": [
                {"driver": "nvidia", "count": "all", "capabilities": ["gpu"]}
            ]}}},
            "labels": {
                "io.optiplex-now.managed": "prototype",
                "io.optiplex-now.role": "streaming",
            },
        }},
    }
    manifest = {
        "schema_version": STAGE_SCHEMA,
        "tool": "now-host-stage",
        "mode": "review_only",
        "deploy_supported": False,
        "changes_to_host_services": False,
        "image": image,
        "render_node": render,
        "managed_compose_project": compose["name"],
        "managed_paths": ["./wolf"],
        "unmanaged_containers_may_be_adopted": False,
        "existing_data_may_be_deleted": False,
        "approval": "not_granted",
        "reason": "No clean-host install/rollback or least-privilege pairing acceptance",
    }
    readme = """# NOW Host staged Wolf container (NOT INSTALLED)

This directory contains a review-only Docker Compose prototype.
Staging does not pull images, install Docker or Wolf, start containers,
modify drivers, manage networks, change user credentials or approve devices.

Only stage on a machine you own and NEVER launch this template on the
working reference server or a host with unrelated services.

The digest is supplied by the operator: staging validates its shape but
DOES NOT verify its registry provenance, platform or integrity.
A trusted operator must verify the exact upstream digest, hardware encoder,
render node, NVIDIA Container Toolkit, input devices and open ports separately.

To validate Compose syntax only:
    docker compose -f compose.yaml config --quiet

Do NOT run compose up, start, pull, or an active profile yet.
Wolf requires write access to the host Docker socket to spawn applications:
such access is effectively host-administrative power and remains a security
review blocker. The owner-approved restricted enrollment broker is unfinished.

The ./wolf directory is intentionally empty. A production-ready Wolf config,
game application, profile persistence, backups and rollback are NOT provided.
This is not a validated 15-minute host installer.
"""
    return {
        "compose.yaml": "# OFFLINE REVIEW ONLY; NOT APPROVED FOR DEPLOYMENT\n"
                        + json.dumps(compose, indent=2, sort_keys=True) + "\n",
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "README.txt": readme,
    }


def _validate_output(output: Path) -> Path:
    if not output.is_absolute() or str(output) == "/" or output.name in ("", ".", ".."):
        raise ValueError("Output must name a new absolute directory")
    parent = output.parent.resolve(strict=True)
    if str(parent) in PROTECTED_ROOTS or any(
        str(parent).startswith(protected + "/") for protected in PROTECTED_ROOTS
    ):
        raise ValueError("Refusing to write staged files under system directories")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Output already exists; no overwrite or adoption")
    return parent / output.name


def stage(output: Path, files: dict[str, str]) -> Path:
    destination = _validate_output(output)
    destination.mkdir(mode=0o700, exist_ok=False)
    try:
        (destination / "wolf").mkdir(mode=0o700)
        for name in ("compose.yaml", "manifest.json", "README.txt"):
            with (destination / name).open("x", encoding="utf-8") as handle:
                handle.write(files[name])
        return destination
    except Exception:
        shutil.rmtree(destination)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage a review-only Wolf Compose bundle")
    parser.add_argument("--output", required=True, type=Path,
                        help="New absolute directory for generated review files")
    parser.add_argument("--image-digest", required=True,
                        help="Externally verified Wolf sha256 digest, not a tag")
    parser.add_argument("--render-node", required=True,
                        help="Explicit NVIDIA /dev/dri/renderD###")
    args = parser.parse_args()
    try:
        scan = host_preflight.evaluate(host_preflight.collect_snapshot())
        plan = host_plan.plan_from_preflight(scan)
        files = make_bundle(plan, digest=args.image_digest,
                            render_node=args.render_node)
        result = stage(args.output, files)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Staged offline review at {result}. No Docker services changed.")
    print("Still blocked: real host validation, image provenance, owner authorization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
