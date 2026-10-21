#!/usr/bin/env python3
"""Opt-in Debian-family Tailscale installation for NOW.

Only called after user confirmation through pkexec, using a fixed root-owned
helper path. No shell pipelines, untrusted command arguments or tokens.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

KEYRING = Path("/usr/share/keyrings/tailscale-archive-keyring.gpg")
REPOSITORY = Path("/etc/apt/sources.list.d/tailscale.list")
UPSTREAM = "https://pkgs.tailscale.com/stable"
SUPPORTED = {
    "ubuntu": {"jammy", "noble", "questing", "resolute"},
    "debian": {"bookworm", "trixie"},
}


def distro(os_release):
    """Choose upstream packages by actual compatible base, not Mint/Pop branding."""
    os_id = os_release.get("ID", "").lower()
    if os_id in {"ubuntu", "pop", "linuxmint"}:
        base = "ubuntu"
        codename = os_release.get("UBUNTU_CODENAME") or (
            os_release.get("VERSION_CODENAME") if os_id == "ubuntu" else None
        )
    elif os_id == "debian":
        base, codename = "debian", os_release.get("VERSION_CODENAME")
    else:
        raise ValueError("Automatic Tailscale install is not available for this distribution.")
    if codename not in SUPPORTED[base]:
        raise ValueError("This OS release is not yet validated for automatic installation.")
    return base, codename


def os_release_read(path="/etc/os-release"):
    data = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Z][A-Z_0-9]*", key):
            data[key] = value.strip().strip('"').strip("'")
    return data


def upstream_data(base, codename, suffix):
    url = f"{UPSTREAM}/{base}/{codename}.{suffix}"
    with urllib.request.urlopen(url, timeout=20) as response:
        result = response.read(256 * 1024 + 1)
    if not result or len(result) > 256 * 1024:
        raise ValueError("Invalid Tailscale repository download.")
    return result


def install_repository(base, codename):
    key = upstream_data(base, codename, "noarmor.gpg")
    if len(key) < 100 or b"-----BEGIN" in key:
        raise ValueError("Unexpected Tailscale signing key format.")

    vendor_list = upstream_data(base, codename, "tailscale-keyring.list").decode("utf-8")
    expected = (f"deb [signed-by={KEYRING}] "
                f"{UPSTREAM}/{base} {codename} main")
    active = [line.strip() for line in vendor_list.splitlines()
              if line.strip() and not line.lstrip().startswith("#")]
    if active != [expected]:
        raise ValueError("Unexpected Tailscale repository configuration.")

    KEYRING.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    tmpkey = KEYRING.with_suffix(".gpg.now-tmp")
    tmpkey.write_bytes(key)
    tmpkey.chmod(0o644)
    tmpkey.replace(KEYRING)
    tmplist = REPOSITORY.with_suffix(".list.now-tmp")
    tmplist.write_text(expected + "\n", encoding="utf-8")
    tmplist.chmod(0o644)
    tmplist.replace(REPOSITORY)


def run(*command, timeout=180):
    subprocess.run(command, timeout=timeout, check=True,
                   env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def main():
    if os.geteuid() != 0:
        raise PermissionError("Administrator authorization is required.")
    if shutil.which("tailscale"):
        print("ALREADY_INSTALLED")
        return
    if not shutil.which("apt-get") or not shutil.which("systemctl"):
        raise ValueError("Automatic installation requires apt and systemd.")

    base, codename = distro(os_release_read())
    install_repository(base, codename)
    run("apt-get", "update")
    run("apt-get", "install", "-y", "tailscale")
    run("systemctl", "enable", "--now", "tailscaled", timeout=30)
    print("INSTALLED")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, PermissionError, OSError, UnicodeError,
            urllib.error.URLError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError) as error:
        # Don't print private repository internals or command output.
        print("INSTALL_FAILED: " + type(error).__name__)
        sys.exit(1)
