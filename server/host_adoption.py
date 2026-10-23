#!/usr/bin/env python3
"""Non-executable adoption and setup decision from the local service census.

This is a planning aid, NOT an authorization to attach to containers, adopt
profiles, install packages, or change Docker configuration. A Docker candidate
is not proof of an owned/service-authenticated or safely configured service.
"""
from __future__ import annotations

import argparse
import json

import host_services

SCHEMA = 1
SERVICE_KEYS = ("wolf", "jellyfin", "qbittorrent", "gluetun")
COUNT_LIMIT = host_services.MAX_ITEMS
CANDIDATE_STATES = {
    "running_candidate", "stopped_candidate", "ambiguous_multiple",
    "not_detected_in_docker", "unknown",
}


def plan(report: dict) -> dict:
    """Return fixed-enum decisions with no copied names, paths or secrets."""
    if (not isinstance(report, dict) or
            report.get("schema_version") != host_services.SCHEMA or
            report.get("tool") != "now-host-services" or
            report.get("read_only") is not True or
            report.get("changes_performed") is not False or
            report.get("may_adopt") is not False or
            report.get("docker_access") not in ("available", "unavailable") or
            not isinstance(report.get("services"), dict) or
            set(report["services"]) != set(SERVICE_KEYS)):
        raise ValueError("Invalid read-only local service census")

    states = {}
    for name in SERVICE_KEYS:
        entry = report["services"][name]
        if not isinstance(entry, dict):
            raise ValueError("Invalid service finding")
        state = entry.get("status")
        count = entry.get("docker_count")
        if (state not in CANDIDATE_STATES or type(count) is not int
                or not 0 <= count <= COUNT_LIMIT or
                (state in ("running_candidate", "stopped_candidate") and count != 1)
                or (state == "ambiguous_multiple" and count < 2)
                or (state in ("not_detected_in_docker", "unknown") and count != 0)
                or (report["docker_access"] == "unavailable"
                    and state != "unknown")
                or (report["docker_access"] == "available"
                    and state == "unknown")):
            raise ValueError("Contradictory service census")
        states[name] = state

    downloads = report.get("downloads")
    if (not isinstance(downloads, dict) or
            downloads.get("topology") not in
            ("not_verified", "shared_gluetun_namespace") or
            downloads.get("gateway_health") not in
            ("unknown", "healthy", "unhealthy", "starting") or
            downloads.get("vpn_egress_verified") is not False or
            downloads.get("killswitch_verified") is not False or
            report.get("vuetorrent") != "not_verified" or
            report.get("storage_paths") != "not_inspected"):
        raise ValueError("Missing mandatory safety limits")
    if (downloads["topology"] == "shared_gluetun_namespace"
            and not (states["qbittorrent"] in
                     ("running_candidate", "stopped_candidate")
                     and states["gluetun"] in
                     ("running_candidate", "stopped_candidate"))):
        raise ValueError("Unverifiable downloader topology")

    def recommendation(status: str) -> str:
        return {
            "running_candidate": "review_existing_without_changes",
            "stopped_candidate": "review_stopped_existing_without_restart",
            "ambiguous_multiple": "blocked_multiple_cannot_choose",
            "not_detected_in_docker": "inspect_native_services_before_new_setup",
            "unknown": "blocked_cannot_inspect_host",
        }[status]

    services = {key: recommendation(states[key]) for key in SERVICE_KEYS}
    if states["qbittorrent"] == states["gluetun"] == "running_candidate":
        services["downloader_network"] = (
            "review_topology_and_verify_vpn_fail_closed"
            if downloads["topology"] == "shared_gluetun_namespace"
            else "blocked_downloader_vpn_binding_unverified")
    else:
        services["downloader_network"] = "blocked_until_services_reviewed"

    blockers = [
        key for key in SERVICE_KEYS if states[key] in
        ("unknown", "ambiguous_multiple")
    ]
    if "blocked" in services["downloader_network"]:
        blockers.append("downloader_network")
    if report["docker_access"] == "unavailable":
        outcome = "cannot_inspect"
    elif blockers:
        outcome = "manual_review_required"
    elif any(states[k] == "not_detected_in_docker" for k in SERVICE_KEYS):
        outcome = "native_service_scan_required"
    else:
        outcome = "existing_services_need_authorized_review"

    return {
        "schema_version": SCHEMA,
        "tool": "now-host-adoption-plan",
        "read_only": True,
        "may_adopt": False,
        "may_install": False,
        "changes_performed": False,
        "decision": outcome,
        "services": services,
        "required_before_adoption": [
            "authenticated_owner_authorization",
            "existing_data_and_container_mount_review",
            "service_endpoint_and_account_verification",
            "media_storage_mapping",
            "downloader_vpn_egress_and_killswitch_proof",
            "restricted_viewer_denial",
        ],
        "note": (
            "No service was adopted, configured or installed. A running "
            "container is not proof of safe adoption or authorization. "
            "Native installs and configured VueTorrent remain uninspected."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = plan(host_services.collect())
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("ADOPT EXISTING / SET UP NEW | READ-ONLY PLAN")
        print("DECISION:", result["decision"])
        for service, suggestion in result["services"].items():
            print(f"{service.upper():20} {suggestion}")
        print("INSTALL OR ADOPT PERMISSION: NOT GRANTED")
        print(result["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
