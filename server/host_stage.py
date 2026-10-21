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
DRIVER_VOLUME = "now-nvidia-driver-vol"
GPU_CHOICES = ("nvidia", "amd", "intel")
GPU_VENDORS = {"nvidia": "0x10de", "amd": "0x1002", "intel": "0x8086"}
PROTECTED_ROOTS = ("/etc", "/var", "/usr", "/run", "/dev", "/proc", "/sys", "/boot")


def validate_digest(digest: str) -> str:
    if not isinstance(digest, str) or not IMAGE_RE.fullmatch(digest):
        raise ValueError("Wolf image requires sha256: followed by 64 lowercase hex digits")
    return "ghcr.io/games-on-whales/wolf@" + digest


def validate_render_node(device: str) -> str:
    if not isinstance(device, str) or not RENDER_RE.fullmatch(device):
        raise ValueError("Specify an explicit /dev/dri/renderD### device; do not guess")
    return device


def check_render_vendor(gpu_vendor: str, render_node: str,
                        sysfs_root: Path = Path("/sys")) -> None:
    """Reject a known wrong GPU-to-render-node selection on a live machine.

    The node path MUST be chosen by the operator. Unknown sysfs mapping remains
    unverified, not automatically accepted for deployment (deployment disabled).
    """
    validate_render_node(render_node)
    if gpu_vendor not in GPU_CHOICES:
        raise ValueError("Invalid GPU vendor")
    name = Path(render_node).name
    id_file = sysfs_root / "class" / "drm" / name / "device" / "vendor"
    vendor_id = host_preflight.read_small(id_file)
    if vendor_id is not None and vendor_id.strip().lower() != GPU_VENDORS[gpu_vendor]:
        raise ValueError(
            "Selected render node is not associated with the selected GPU vendor")


def make_bundle(plan: dict, *, digest: str, render_node: str,
                gpu_vendor: str = "nvidia") -> dict[str, str]:
    """Build inert review artifacts based on a blocked planner result."""
    image = validate_digest(digest)
    render = validate_render_node(render_node)
    if gpu_vendor not in GPU_CHOICES:
        raise ValueError("GPU backend must be nvidia, amd or intel")
    if (not isinstance(plan, dict) or plan.get("tool") != "now-host-plan"
            or plan.get("schema_version") != host_plan.PLAN_SCHEMA
            or plan.get("mode") != "read_only_preview"
            or plan.get("decision") != "blocked"
            or plan.get("may_apply") is not False
            or plan.get("changes_performed") is not False):
        raise ValueError("Only a blocked NOW Host plan can be staged")

    # JSON syntax is valid YAML 1.2; Compose parses compose.yaml.
    # The inactive profile and pull_policy=never prevent accidental default
    # startup/pull. These are not a security boundary against deliberate use.
    # No container_name: avoid collision with existing host installations.
    wolf = {
        "profiles": [PROFILE],
        "image": image,
        "pull_policy": "never",
        "network_mode": "host",
        "restart": "no",
        "environment": {"WOLF_RENDER_NODE": render},
        "volumes": [
            "./wolf:/etc/wolf:rw",
            "/var/run/docker.sock:/var/run/docker.sock:rw",
            "/dev:/dev:rw",
            "/run/udev:/run/udev:rw",
        ],
        "devices": [
            "/dev/dri:/dev/dri",
            "/dev/uinput:/dev/uinput",
            "/dev/uhid:/dev/uhid",
        ],
        "device_cgroup_rules": ["c 13:* rmw"],
        "labels": {
            "io.optiplex-now.managed": "prototype",
            "io.optiplex-now.role": "streaming",
        },
    }
    compose = {"name": "optiplex-now-host-pilot", "services": {"wolf": wolf}}
    if gpu_vendor == "nvidia":
        wolf["environment"]["NVIDIA_DRIVER_VOLUME_NAME"] = DRIVER_VOLUME
        wolf["volumes"].append(DRIVER_VOLUME + ":/usr/nvidia:rw")
        wolf["devices"].extend([
            "/dev/nvidia0:/dev/nvidia0",
            "/dev/nvidiactl:/dev/nvidiactl",
            "/dev/nvidia-modeset:/dev/nvidia-modeset",
            "/dev/nvidia-uvm:/dev/nvidia-uvm",
            "/dev/nvidia-uvm-tools:/dev/nvidia-uvm-tools",
            "/dev/nvidia-caps/nvidia-cap1:/dev/nvidia-caps/nvidia-cap1",
            "/dev/nvidia-caps/nvidia-cap2:/dev/nvidia-caps/nvidia-cap2",
        ])
        compose["volumes"] = {DRIVER_VOLUME: {"external": True}}
    manifest = {
        "schema_version": STAGE_SCHEMA,
        "tool": "now-host-stage",
        "mode": "review_only",
        "deploy_supported": False,
        "changes_to_host_services": False,
        "image": image,
        "render_node": render,
        "gpu_vendor": gpu_vendor,
        "nvidia_method": ("manual_external_driver_volume"
                          if gpu_vendor == "nvidia" else None),
        "driver_volume": DRIVER_VOLUME if gpu_vendor == "nvidia" else None,
        "driver_volume_prepared": False,
        "managed_compose_project": compose["name"],
        "managed_paths": ["./wolf"],
        "unmanaged_containers_may_be_adopted": False,
        "existing_data_may_be_deleted": False,
        "approval": "not_granted",
        "reason": "No clean-host install/rollback or least-privilege pairing acceptance",
    }
    method = ("NVIDIA manual driver volume (not populated)"
              if gpu_vendor == "nvidia" else
              "standard Linux DRM render nodes (no NVIDIA driver volume)")
    readme = f"""# NOW Host staged Wolf container (NOT INSTALLED)

GPU profile: {gpu_vendor.upper()}
Container method: {method}
Render node selected: {render}
All GPU profiles are UNVALIDATED on clean physical host hardware.

Staging does not install Docker, start containers, modify drivers or ports,
change credentials, authorize devices, adopt containers or touch user services.
The Docker socket would grant host-administrative power if Wolf were started.
DO NOT run docker compose up, pull, start, or enable the inactive profile.

The image digest must be separately verified against the upstream registry.
A digest-shaped placeholder is NOT proof of origin or image correctness.
For Intel/AMD, GPU render nodes and compatible hardware encoders still need
a real-device streaming test. On multi-GPU machines, verify the render node
actually belongs to the selected vendor.

For NVIDIA, an independent and driver-version-matched image and external
Docker volume {DRIVER_VOLUME} must be prepared and safely refreshed when the
host NVIDIA driver changes. This program does not create or overwrite it.

Wolf persistent config is empty. The owner authorization broker is unfinished.
This is a review-only prototype, not a 15-minute production installer.

Non-mutating Compose syntax check: docker compose -f compose.yaml config --quiet
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
                        help="Explicit /dev/dri/renderD### associated with the GPU")
    parser.add_argument("--gpu", required=True, choices=GPU_CHOICES,
                        help="GPU family for Wolf container devices; selection is never automatic")
    args = parser.parse_args()
    try:
        scan = host_preflight.evaluate(host_preflight.collect_snapshot())
        plan = host_plan.plan_from_preflight(scan)
        check_render_vendor(args.gpu, args.render_node)
        files = make_bundle(plan, digest=args.image_digest,
                            render_node=args.render_node, gpu_vendor=args.gpu)
        result = stage(args.output, files)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Staged offline review at {result}. No Docker services changed.")
    print("Still blocked: real host validation, image provenance, owner authorization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
