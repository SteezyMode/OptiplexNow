#!/usr/bin/env python3
"""Install the opt-in owner-phone QR PILOT without modifying running services.

A source tree must be an exact Git checkout or GitHub commit tarball.
--check is read-only; --install copies a fixed module allowlist into a
private versioned directory and atomically publishes it; nothing runs.
--remove only removes this versioned pilot after explicit owner action.
No sudo, apt, systemd, Docker writes, or changes to SSH/Wolf settings.
"""
import argparse
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

MODULES = (
    "server/tailnet_enrollment.py",
    "server/tailnet_owner_identity.py",
    "server/tailnet_wolf_pair.py",
    "server/tailnet_wolf_fresh.py",
    "server/tailnet_wolf_review.py",
    "server/tailnet_pair_witness.py",
    "server/owner_enrollment.py",
    "server/owner_games_enroll.py",
    "server/owner_qr_approval.py",
    "server/owner_certificate_attestation.py",
    "server/moonlight_cert_identity.py",
    "src/owner_access.py",
    "src/wolf_docker_adapter.py",
    "src/wolf_socket_adapter.py",
)
REV = re.compile(r"[0-9a-f]{40}\Z")
MAX_MODULE = 200000
LAUNCHER = """#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
export PYTHONPATH="$HERE/server:$HERE/src"
exec /usr/bin/python3 "$HERE/server/tailnet_enrollment.py" \\
  --owner-id-file "$HOME/.config/optiplex-now/tailnet-owner-id" \\
  --approver-node-id-file "$HOME/.config/optiplex-now/owner-phone-node-id" \\
  --wolf-config /etc/wolf/cfg/config.toml \\
  --enable-remote-approval "$@"
"""


class InstallError(ValueError):
    pass


def check_revision(source, revision):
    """Allow exact git HEAD or untouched GitHub commit archive folder."""
    if not REV.fullmatch(revision or ""):
        raise InstallError("An exact 40-character commit revision is required")
    if source.name == "OptiplexNow-" + revision:
        return
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=5, check=False)
    if result.returncode or result.stdout.strip() != revision:
        raise InstallError("Source is not the requested Git commit")


def _module_bytes(source):
    result = {}
    for name in MODULES:
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise InstallError("Missing or linked QR module: " + name)
        meta = path.stat()
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= MAX_MODULE:
            raise InstallError("Unsafe QR module: " + name)
        data = path.read_bytes()
        if len(data) != meta.st_size:
            raise InstallError("Source module changed during copy")
        result[name] = data
    return result


def _private_dir(base):
    base = Path(base)
    if not base.is_absolute() or base.is_symlink():
        raise InstallError("Unsafe pilot directory")
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = base.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise InstallError("Pilot directory must be owner-only mode 0700")
    return base


def _write_exclusive(path, data, mode):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), mode)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def install_tree(source, base, revision):
    """Copy exact selected modules, with no executable server started."""
    check_revision(source, revision)
    modules = _module_bytes(source)
    root = _private_dir(base)
    dest = root / revision
    if dest.exists() or dest.is_symlink():
        raise InstallError("This QR pilot revision is already installed")
    stage = Path(tempfile.mkdtemp(prefix=".qr-stage-", dir=root))
    try:
        stage.chmod(0o700)
        sums = {}
        for name, data in modules.items():
            target = stage / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _write_exclusive(target, data, 0o600)
            sums[name] = hashlib.sha256(data).hexdigest()
        _write_exclusive(stage / "run-qr-pilot",
                         LAUNCHER.encode("ascii"), 0o700)
        _write_exclusive(stage / "manifest.json", json.dumps({
            "revision": revision, "files": sums,
            "status": "pilot-only-not-running"
        }, sort_keys=True).encode("ascii") + b"\n", 0o600)
        os.rename(stage, dest)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return dest


def remove_tree(base, revision):
    if not REV.fullmatch(revision or ""):
        raise InstallError("Invalid pilot revision")
    root = Path(base)
    if root.is_symlink() or not root.is_dir():
        raise InstallError("Unsafe pilot root")
    _private_dir(root)
    dest = root / revision
    if dest.is_symlink() or not dest.is_dir():
        raise InstallError("Pilot installation is missing or unsafe")
    manifest = dest / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise InstallError("Pilot manifest missing")
    data = json.loads(manifest.read_text("ascii"))
    if data.get("revision") != revision or set(data.get("files", {})) != set(MODULES):
        raise InstallError("Pilot manifest does not match expected installation")
    # Deliberate owner command; never stop a live server or system service here.
    shutil.rmtree(dest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--remove", action="store_true")
    parser.add_argument("--revision", required=True)
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[1]
    root = Path.home() / ".local/lib/optiplex-now-qr-pilot"
    try:
        if args.remove:
            remove_tree(root, args.revision)
            print("QR pilot files removed (no services touched).")
            return 0
        check_revision(source, args.revision)
        _module_bytes(source)
        if args.check:
            print("Pinned QR module inventory verified; no files installed.")
            return 0
        dest = install_tree(source, root, args.revision)
        print("Isolated owner QR pilot installed:", dest)
        print("Listener NOT started. Host-only preflight:")
        print(" ", dest / "run-qr-pilot")
        print("Explicit Tailnet-only start (interactive; Ctrl+C stops):")
        print(" ", dest / "run-qr-pilot --serve")
        return 0
    except (InstallError, OSError, UnicodeError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as exc:
        print("QR pilot unavailable:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
