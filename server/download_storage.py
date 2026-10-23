"""Pure qBittorrent Docker bind-mount path translation for owner file management.

This module executes NO host or container commands and grants NO permissions.
A trusted host service may use it to translate a verified qBittorrent save
location into a corresponding host-side SFTP/file-manager path.

A match is only an advisory mapping, not proof of filesystem existence,
writability or safety. Before ANY file write, an authenticated host broker
must independently resolve paths against approved roots, guard symlinks and
mount changes, and enforce ordinary Linux permissions and owner identity.
Never return raw host paths to an unapproved viewer/device.
"""
from __future__ import annotations

from pathlib import PurePosixPath

MAX_PATH = 4096
MAX_MOUNTS = 128


class StorageMappingError(ValueError):
    pass


def _path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not (1 <= len(value) <= MAX_PATH):
        raise StorageMappingError("Invalid absolute path")
    if not value.startswith("/") or value.startswith("//") or (
            any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        raise StorageMappingError("Unsupported path")
    raw_parts = value.split("/")
    if any(part in (".", "..") for part in raw_parts):
        raise StorageMappingError("Unnormalized path")
    if any(not part for part in raw_parts[1:-1]):
        raise StorageMappingError("Ambiguous path separators")
    return PurePosixPath(value)


def bind_mounts(container: dict, *, writable_only: bool = False) -> list[dict]:
    """Return normalized bind source/destination pairs from Docker inspect.

    Only inspect records already selected for an authenticated, unique
    qBittorrent container; this helper does not prove ownership.
    Reject ambiguity rather than guessing a host path.
    """
    if not isinstance(container, dict):
        raise StorageMappingError("Invalid Docker container record")
    mounts = container.get("Mounts")
    if not isinstance(mounts, list) or len(mounts) > MAX_MOUNTS:
        raise StorageMappingError("Unavailable Docker bind mounts")
    items = []
    destinations = set()
    for entry in mounts:
        if not isinstance(entry, dict):
            raise StorageMappingError("Malformed Docker mount")
        if entry.get("Type") != "bind":
            continue
        if type(entry.get("RW")) is not bool:
            raise StorageMappingError("Bind mount write state unknown")
        src, dest = _path(entry.get("Source")), _path(entry.get("Destination"))
        # Root-bound host mounts can expose the whole host. Do not turn
        # them into a downloader write target, even if Docker allows one.
        if src == PurePosixPath("/") or dest == PurePosixPath("/"):
            raise StorageMappingError("Root bind mount is unsupported")
        if str(dest) in destinations:
            raise StorageMappingError("Duplicate container mount destinations")
        destinations.add(str(dest))
        items.append({"host_root": src, "container_root": dest,
                      "writable": entry["RW"]})
    if writable_only:
        items = [entry for entry in items if entry["writable"]]
    return items


def _translate(path: object, mounts: list[dict], *, reverse: bool,
               write: bool) -> str:
    needle = _path(path)
    candidates = []
    for entry in mounts:
        source = entry["host_root"] if reverse else entry["container_root"]
        dest = entry["container_root"] if reverse else entry["host_root"]
        if source == needle or source in needle.parents:
            rel = needle.relative_to(source)
            candidates.append((len(source.parts), dest / rel, entry["writable"]))
    if not candidates:
        raise StorageMappingError("Path is not under a bound storage volume")
    deepest = max(length for length, _, _ in candidates)
    matches = [(translated, writable) for length, translated, writable
               in candidates if length == deepest]
    if len(matches) != 1:
        raise StorageMappingError("Ambiguous overlapping mounts")
    translated, writable = matches[0]
    if write and not writable:
        raise StorageMappingError("Selected destination is read-only")
    # A non-writable nested mount must not inherit an outer writable match.
    if write and not reverse:
        for entry in mounts:
            root = entry["container_root"]
            if root == needle or root in needle.parents:
                if not entry["writable"]:
                    raise StorageMappingError("Path crosses read-only mount")
    return str(translated)


def container_to_host(path: str, container: dict,
                      *, require_writable: bool = False) -> str:
    """Map a qBittorrent container save path to an owner's host path."""
    return _translate(path, bind_mounts(container),
                      reverse=False, write=require_writable)


def host_to_container(path: str, container: dict) -> str:
    """Map a chosen host folder to a qBittorrent-writable container folder.

    No mkdir, chmod, writes or Docker operations occur. Host filesystem
    existence/permissions and symlink containment need separate verification.
    """
    return _translate(path, bind_mounts(container),
                      reverse=True, write=True)
