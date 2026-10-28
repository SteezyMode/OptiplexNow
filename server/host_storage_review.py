"""Host-only, read-only relationship review for existing Jellyfin + qBittorrent.

This is NOT a file browser, root approval, path-mapping authority, service
adoption, or a permissions grant. Bind-source strings from Docker metadata are
compared lexically only; no paths are opened, resolved, returned, or modified.
Actual mount/symlink relationships, qBittorrent save destinations, ownership,
and Jellyfin library membership need subsequent explicit owner verification.
"""
from __future__ import annotations

import os
from pathlib import PurePosixPath
import subprocess

import host_services

MAX_MOUNTS = 32
MAX_PATH = 1024

UNKNOWN = "unknown_or_ambiguous"
NO_MOUNTS = "no_comparable_bind_mounts"
NO_OVERLAP = "no_bind_overlap_observed"
SHARED = "shared_bind_source_candidate"
NESTED = "nested_bind_source_candidate"
NATIVE = "native_jellyfin_library_mapping_unverified"


def _sources(record):
    mounts = record.get("Mounts")
    if not isinstance(mounts, list) or len(mounts) > MAX_MOUNTS:
        return None
    sources = set()
    for mount in mounts:
        if not isinstance(mount, dict):
            return None
        if mount.get("Type") != "bind":
            continue
        path = mount.get("Source")
        if not isinstance(path, str) or len(path) > MAX_PATH or (
                not path.startswith("/") or path == "/" or
                any(ord(c) < 32 or ord(c) == 127 for c in path) or
                os.path.normpath(path) != path or
                ".." in PurePosixPath(path).parts):
            return None
        # Only lexical hints; this cannot prove symlink-free containment or
        # that the mount maps to a Jellyfin library/qBittorrent save folder.
        sources.add(path)
    return sources


def native_jellyfin_active(*, runner=subprocess.run):
    """Only check whether the known systemd unit is active, no config access.

    This is a candidate hint, not proof of Jellyfin ownership, libraries,
    served paths, or an authorized media administration API.
    """
    try:
        proc = runner(
            ["/usr/bin/systemctl", "--system", "is-active", "--quiet",
             "jellyfin.service"],
            stdin=subprocess.DEVNULL, capture_output=True, check=False,
            timeout=4, env={"PATH": "/usr/bin:/bin", "SYSTEMD_PAGER": "cat"})
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def review(records, *, native_jellyfin=False):
    """Summarize only fixed-status hints, never host paths or container IDs."""
    status = UNKNOWN
    if isinstance(records, list) and len(records) <= host_services.MAX_ITEMS:
        candidates = {"jellyfin": [], "qbittorrent": []}
        for record in records:
            if not isinstance(record, dict):
                break
            config = record.get("Config")
            image = config.get("Image") if isinstance(config, dict) else None
            service = host_services.classify_image(image)
            if service in candidates:
                candidates[service].append(record)
        else:
            if (native_jellyfin is True and not candidates["jellyfin"] and
                    len(candidates["qbittorrent"]) == 1):
                # A native Jellyfin service cannot be tied to a Docker
                # bind source without reading its actual approved libraries.
                # A qBittorrent container alone cannot establish that link.
                status = NATIVE
            elif (native_jellyfin is not True and
                  len(candidates["jellyfin"]) ==
                  len(candidates["qbittorrent"]) == 1):
                jelly = _sources(candidates["jellyfin"][0])
                qbit = _sources(candidates["qbittorrent"][0])
                if jelly is not None and qbit is not None:
                    if not jelly or not qbit:
                        status = NO_MOUNTS
                    elif jelly & qbit:
                        status = SHARED
                    elif any(a.startswith(b + "/") or b.startswith(a + "/")
                             for a in jelly for b in qbit):
                        status = NESTED
                    else:
                        status = NO_OVERLAP

    return {
        "schema_version": 1,
        "status": status,
        "read_only": True,
        "changes_performed": False,
        "candidate_only": True,
        "may_manage_files": False,
        "may_change_mounts": False,
        "owner_confirmation_required": True,
        "note": (
            "Docker bind metadata is not a library root or file authorization. "
            "Native Jellyfin library roots, symlinks, download save paths and "
            "actual media visibility are not verified. No existing state changed."
        ),
    }
