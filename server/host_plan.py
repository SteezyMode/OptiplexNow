#!/usr/bin/env python3
"""Deterministic, non-executable NOW Host installation planning preview.

This module cannot install, adopt, repair, remove or configure any host service.
It consumes the redacted output of host_preflight.py, never Docker credentials,
and intentionally keeps all installation approval gates closed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import host_preflight

PLAN_SCHEMA = 1
REQUIRED_CHECKS = (
    "architecture", "operating_system", "gpu_detection", "hardware_encoder",
    "nvidia_driver", "nvidia_drm_modeset", "virtual_controller_devices",
    "udev", "container_runtime", "wolf_ports", "disk_space", "memory",
)
VALID_STATES = {"pass", "attention", "unknown", "unsupported"}
# These paths are proposed ownership conventions, not automatically created.
CONFIG_ROOT = "/etc/optiplex-now/host"
STATE_ROOT = "/var/lib/optiplex-now/host"

# Wolf's documented default listening ports. Must be checked again against
# a pinned upstream deployment and the actual intended host network mode.
PORTS = (
    {"protocol": "tcp", "port": 47984},
    {"protocol": "tcp", "port": 47989},
    {"protocol": "tcp", "port": 48010},
    {"protocol": "udp", "port": 47999},
    {"protocol": "udp", "port": 48100},
    {"protocol": "udp", "port": 48200},
)


def _validate_preflight(report: dict) -> dict[str, str]:
    """Accept only the scanner's bounded status contract, never its prose."""
    if (not isinstance(report, dict)
            or report.get("schema_version") != host_preflight.SCHEMA_VERSION
            or report.get("tool") != "now-host-preflight"
            or report.get("read_only") is not True
            or report.get("verified_streaming") is not False
            or not isinstance(report.get("checks"), list)
            or len(report["checks"]) > 64):
        raise ValueError("Expected a versioned, read-only NOW Host Preflight report.")
    observed = {}
    for item in report["checks"]:
        if not isinstance(item, dict):
            raise ValueError("Malformed preflight check.")
        name, state = item.get("id"), item.get("status")
        if not isinstance(name, str) or not isinstance(state, str):
            raise ValueError("Malformed preflight check ID/status.")
        if name in observed or name not in REQUIRED_CHECKS or state not in VALID_STATES:
            raise ValueError("Unexpected, repeated or invalid preflight check.")
        observed[name] = state
    # Older/future reports with missing checks cannot silently pass a gate.
    for name in REQUIRED_CHECKS:
        observed.setdefault(name, "unknown")
    return observed


def plan_from_preflight(report: dict) -> dict:
    """Return an immutable-in-spirit plan preview from validated check states.

    Even a hypothetical all-PASS inventory cannot authorize an installation.
    An image digest, GPU encoder stream test, host broker and explicit owner
    approval are separate blockers, not implied by free ports or Docker.
    """
    findings = _validate_preflight(report)
    gates = []
    for check in REQUIRED_CHECKS:
        state = findings[check]
        gates.append({
            "id": check,
            "state": "needs_review" if state == "pass" else "blocked",
            "observation": state,
            "reason_code": ("observation_only" if state == "pass" else
                            "unsupported" if state == "unsupported" else
                            "conflict_or_missing_dependency" if state == "attention"
                            else "insufficient_evidence"),
        })
    gates.extend([
        {"id": "pinned_wolf_image", "state": "blocked",
         "reason_code": "upstream_digest_not_selected"},
        {"id": "verified_gpu_stream", "state": "blocked",
         "reason_code": "physical_video_audio_input_test_pending"},
        {"id": "owner_enrollment", "state": "blocked",
         "reason_code": "restricted_host_broker_not_implemented"},
        {"id": "separate_clean_host", "state": "blocked",
         "reason_code": "disposable_install_and_rollback_not_tested"},
    ])
    return {
        "schema_version": PLAN_SCHEMA,
        "tool": "now-host-plan",
        "mode": "read_only_preview",
        "decision": "blocked",
        "may_apply": False,
        "changes_performed": False,
        "pilot": {
            "os": "Ubuntu 24.04",
            "architecture": "x86_64",
            "gpu": "NVIDIA candidate, exact GPU/encoder support pending verification",
            "topology": "one owner, one Wolf application, one Moonlight client",
        },
        "ownership_proposal": {
            "configuration_root": CONFIG_ROOT,
            "state_root": STATE_ROOT,
            "compose_project": "optiplex-now-host",
            "labels": {"manager": "optiplex-now", "role": "streaming"},
            "adopt_unmanaged_containers": False,
            "delete_existing_user_data": False,
        },
        "service_proposal": [{
            "id": "wolf-streaming",
            "required": True,
            "image_digest": None,
            "image_source": "upstream Wolf (must pin and verify before apply)",
            "runtime": "Docker with GPU encoder and constrained device access",
            "ports": list(PORTS),
            "config_under": CONFIG_ROOT,
            "state_under": STATE_ROOT,
            "depends_on": ["GPU encoder validation", "Docker", "controller devices",
                           "owner-approved enrollment"],
            "provisionable": False,
        }],
        "optional_services": ["Jellyfin (independent authentication, separate opt-in)"],
        "future_steps": [
            {"id": "preflight", "action": "collect and review evidence",
             "would_modify_host": False},
            {"id": "review_conflicts", "action": "owner reviews occupied ports and existing services",
             "would_modify_host": False},
            {"id": "pin_dependencies", "action": "choose and validate immutable upstream image versions",
             "would_modify_host": False},
            {"id": "authorize", "action": "obtain explicit owner approval on a supported clean host",
             "would_modify_host": False},
            {"id": "apply", "action": "install only owned services (not implemented)",
             "would_modify_host": True, "implemented": False},
            {"id": "verify", "action": "check real video, audio, input and reconnect",
             "would_modify_host": False, "implemented": False},
            {"id": "rollback", "action": "undo managed changes without deleting user data",
             "would_modify_host": True, "implemented": False},
        ],
        "gates": gates,
        "note": "Preview only. Occupied Wolf ports are a conflict to investigate, not "
                "permission to adopt or replace an existing server. No installation "
                "is possible through this tool.",
    }


def _render_text(plan: dict) -> str:
    lines = [
        "NOW Host Installation Plan | BLOCKED | NO CHANGES",
        "Target: Ubuntu 24.04 x86-64 / NVIDIA candidate / one Wolf stream",
        "Components: Wolf container; Jellyfin optional and separate",
        "Proposed config: " + plan["ownership_proposal"]["configuration_root"],
        "Proposed state: " + plan["ownership_proposal"]["state_root"],
        "Proposed ports: " + ", ".join(
            str(item["port"]) + "/" + item["protocol"]
            for item in plan["service_proposal"][0]["ports"]),
        "Required reviews:",
    ]
    for gate in plan["gates"]:
        if gate["state"] == "blocked":
            lines.append("  - " + gate["id"] + ": " + gate["reason_code"])
    lines.append("Nothing was installed, configured, adopted or removed.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview a blocked NOW Host installation plan without changing the machine.")
    parser.add_argument("--preflight-json", type=Path,
                        help="Use a saved read-only host_preflight.py --json report.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable plan.")
    args = parser.parse_args()
    try:
        if args.preflight_json:
            # Bound source size and suppress potentially sensitive source data
            # from diagnostics; only known statuses are copied into the plan.
            if args.preflight_json.stat().st_size > 65536:
                raise ValueError("Preflight report too large.")
            report = json.loads(args.preflight_json.read_text(encoding="utf-8"))
        else:
            report = host_preflight.evaluate(host_preflight.collect_snapshot())
        plan = plan_from_preflight(report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error("Invalid preflight report or unreadable file.")
    print(json.dumps(plan, indent=2) if args.json else _render_text(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
