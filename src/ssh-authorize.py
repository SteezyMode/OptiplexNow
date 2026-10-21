#!/usr/bin/env python3
"""Authorize a user's existing SSH account without starting a terminal.

A user-initiated operation only. Installs the local public key using the
upstream ssh-copy-id utility, with OpenSSH's host-key verification retained.
Passwords and passphrases are handled by an independent GTK SSH_ASKPASS
helper; they are never passed as argv, stored, or written to NOW logs.
"""
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys

ASKPASS = "/usr/lib/optiplex-now/now-ssh-askpass"
SSH_TIMEOUT = 120
_child = None


def validate(host, user):
    if not host or host.startswith("-") or len(host) > 250 or not re.fullmatch(r"[A-Za-z0-9._:-]+", host):
        raise ValueError("Invalid SSH host")
    if not user or len(user) > 100 or not re.fullmatch(r"[A-Za-z0-9._-]+", user):
        raise ValueError("Invalid SSH user")
    if user.startswith("-"):
        raise ValueError("Invalid SSH user")
    return host, user


def select_key(home):
    sshdir = Path(home) / ".ssh"
    if sshdir.is_symlink():
        raise ValueError("SSH directory must not be a symlink")
    sshdir.mkdir(mode=0o700, exist_ok=True)
    if not sshdir.is_dir() or sshdir.stat().st_mode & 0o022:
        raise ValueError("SSH directory has unsafe permissions")

    private = sshdir / "id_ed25519"
    public = sshdir / "id_ed25519.pub"
    if private.is_symlink() or public.is_symlink():
        raise ValueError("SSH key paths must not be symlinks")
    if private.exists() and not public.exists():
        raise ValueError("Existing SSH key has no public key")
    if public.exists() and not private.exists():
        raise ValueError("SSH public key has no matching private key")

    if not private.exists():
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private)],
            check=True, timeout=15, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    if not private.is_file() or not public.is_file():
        raise ValueError("SSH key pair unavailable")
    return public


def interrupt(signum, frame):
    del frame
    if _child is not None and _child.poll() is None:
        try:
            os.killpg(_child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    raise SystemExit(128 + signum)


def authorize(host, user, pubkey):
    global _child
    if not shutil.which("ssh-copy-id"):
        raise ValueError("SSH key installer not available")
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise ValueError("A graphical desktop is required")
    if not Path(ASKPASS).is_file() or not os.access(ASKPASS, os.X_OK):
        raise ValueError("Graphical SSH password dialog is unavailable")

    env = os.environ.copy()
    env["SSH_ASKPASS"] = ASKPASS
    env["SSH_ASKPASS_REQUIRE"] = "force"
    command = [
        "ssh-copy-id", "-i", str(pubkey),
        "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1",
        "-o", "StrictHostKeyChecking=ask",
        "-o", "NumberOfPasswordPrompts=3",
        f"{user}@{host}",
    ]
    _child = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, env=env, start_new_session=True
    )
    child = _child
    try:
        output, _ = child.communicate(timeout=SSH_TIMEOUT)
        return_code = child.returncode
    except subprocess.TimeoutExpired:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)
        child.communicate()
        raise ValueError("SSH authorization timed out")
    finally:
        _child = None
    if len(output) > 128 * 1024:
        raise ValueError("Unexpected SSH output")
    # Do not emit ssh-copy-id output: it can contain host/user details.
    return return_code


def main():
    if len(sys.argv) != 3:
        raise ValueError("Expected host and SSH account")
    host, user = validate(sys.argv[1], sys.argv[2])
    home = os.environ.get("HOME")
    if not home or home == "/tmp":
        raise ValueError("A real home directory is required")
    if not shutil.which("ssh-keygen"):
        raise ValueError("OpenSSH tools not installed")
    key = select_key(home)
    success = authorize(host, user, key)
    if success != 0:
        raise ValueError("SSH key was not authorized")
    print("AUTHORIZED")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as error:
        # Never log a password, key material, remote output or credential prompt.
        print("AUTHORIZATION_FAILED: " + type(error).__name__)
        sys.exit(1)
