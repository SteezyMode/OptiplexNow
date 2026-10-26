#!/usr/bin/env python3
"""Opt-in, local-only Docker/Compose dependency installation for clean NOW hosts.

Uses distro packages on Ubuntu/Pop!_OS 24.04. Never adds apt sources, removes
packages, replaces a Docker runtime, grants docker-group membership, or
provisions Wolf. --check is read-only; --install requires local root via pkexec
and explicit confirmation. Existing/ambiguous runtimes always require review.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

import host_preflight

PACKAGES = ("docker.io", "docker-compose-v2")
CONFLICTS = (
    "docker-ce", "docker-ce-cli", "docker-compose-plugin", "containerd.io",
    "docker.io", "docker-compose-v2", "docker-compose", "podman-docker",
    "containerd", "runc",
)
LOCK = Path("/run/optiplex-now-docker-dependencies.lock")
APT = "/usr/bin/apt-get"
DPKG_QUERY = "/usr/bin/dpkg-query"
DOCKER = "/usr/bin/docker"
MAX_OUTPUT = 262144


class DependencyError(RuntimeError):
    pass


def command(args: list[str], *, timeout: int = 20) -> str:
    """Fixed argv only; capture output so apt errors cannot flood a GUI."""
    try:
        cp = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout, check=False,
                            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                                 "DEBIAN_FRONTEND": "noninteractive",
                                 "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DependencyError("Required package command unavailable or timed out") from exc
    if cp.returncode != 0:
        raise DependencyError("Package check/action failed; inspect APT or dpkg logs")
    if len(cp.stdout) > MAX_OUTPUT:
        raise DependencyError("Package command returned excessive output")
    try:
        return cp.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DependencyError("Invalid package command output") from exc


def installed_packages() -> set[str]:
    """Query each relevant package without guessing from binary names."""
    found = set()
    for name in CONFLICTS:
        try:
            # Do not use command() here: dpkg-query exits nonzero for absent names.
            cp = subprocess.run(
                [DPKG_QUERY, "-W", "-f=${Status}", name],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=5, check=False,
                env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"})
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DependencyError("Cannot safely inspect installed packages") from exc
        if cp.returncode == 0 and cp.stdout.strip() == b"install ok installed":
            found.add(name)
    return found


def clean_candidate() -> tuple[bool, str]:
    release = host_preflight.parse_os_release(
        host_preflight.read_small(Path("/etc/os-release")))
    if (platform.machine().lower() not in ("x86_64", "amd64")
            or release.get("ID", "").lower() not in ("ubuntu", "pop")
            or release.get("VERSION_ID") != "24.04"):
        return False, "Only Ubuntu/Pop!_OS 24.04 amd64 clean hosts are supported"
    if not Path(APT).is_file() or not Path(DPKG_QUERY).is_file():
        return False, "System APT/dpkg tools are unavailable"
    if Path(DOCKER).exists() or Path(DOCKER).is_symlink():
        return False, "Docker command already exists; validate/adopt without reinstalling"
    for path in (Path("/var/run/docker.sock"), Path("/run/docker.sock"),
                 Path("/var/lib/docker"), Path("/var/lib/containerd")):
        if path.exists() or path.is_symlink():
            return False, "Existing container socket or data; refusing an automatic install"
    if installed_packages():
        return False, "Container runtime packages already installed; manual review required"
    return True, ""


def simulate() -> None:
    """APT must be able to add packages without removals or upgrades.

    The exact package/dependency list remains APT's responsibility and is
    re-evaluated immediately before the privileged install.
    """
    output = command(
        [APT, "--simulate", "--no-remove", "--no-install-recommends",
         "install", *PACKAGES], timeout=45)
    lines = output.splitlines()
    if (any(line.startswith(("Remv ", "Conflicts:")) for line in lines)
            or not any(line.startswith("Inst docker.io ") for line in lines)
            or not any(line.startswith("Inst docker-compose-v2 ") for line in lines)):
        raise DependencyError("APT plan is incomplete or changes existing packages")
    # Do not silently upgrade anything installed before this transaction.
    for line in lines:
        if line.startswith("Inst "):
            name = line.split(maxsplit=2)[1]
            # APT renders upgrades as 'Inst package [old-version] (...)'.
            if re.match(r"^Inst \S+ \[[^]]+\]", line):
                raise DependencyError("APT wants to upgrade existing packages")


def inspect() -> dict:
    clean, reason = clean_candidate()
    if not clean:
        return {"state": "existing_or_unsupported", "installable": False,
                "reason": reason, "packages": list(PACKAGES), "changes_performed": False}
    try:
        simulate()
    except DependencyError as exc:
        return {"state": "package_plan_blocked", "installable": False,
                "reason": str(exc), "packages": list(PACKAGES),
                "changes_performed": False}
    return {"state": "installable_clean_host", "installable": True,
            "reason": "Only distro APT packages will be installed after local OS approval",
            "packages": list(PACKAGES), "changes_performed": False}


def install(confirmation: str) -> dict:
    if os.geteuid() != 0:
        raise DependencyError("Root authorization required")
    if confirmation != "INSTALL-DOCKER":
        raise DependencyError("Explicit local installation approval missing")
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = inspect()  # Recheck after elevation; no preflight authorization token.
        if not plan["installable"]:
            raise DependencyError(plan["reason"])
        # Do not apt update, add repositories, purge packages or join docker group.
        command([APT, "--yes", "--no-remove", "--no-install-recommends",
                 "install", *PACKAGES], timeout=600)
        # APT may automatically start the daemon and create firewall rules.
        # Return incomplete rather than changing existing network settings.
        if not Path(DOCKER).is_file():
            raise DependencyError("APT finished without the Docker command; inspect system")
        command([DOCKER, "compose", "version"], timeout=15)
        daemon = command([DOCKER, "--host", "unix:///var/run/docker.sock",
                          "info", "--format", "{{.ServerVersion}}"], timeout=15)
        if not re.fullmatch(r"[0-9][0-9A-Za-z.+-]*", daemon.strip()):
            raise DependencyError("Docker daemon version unverified")
        return {"result": "docker_compose_ready", "engine_version": daemon.strip(),
                "packages": list(PACKAGES),
                "note": "Run Check This PC again before starting Wolf"}
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description="NOW clean-host Docker dependencies")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--install", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    try:
        result = inspect() if args.check else install(args.confirm)
    except (DependencyError, OSError, BlockingIOError) as exc:
        print("NOW Docker dependencies: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
