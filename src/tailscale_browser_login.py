#!/usr/bin/env python3
"""User-invoked, privilege-brokered Tailscale browser login.

The CLI's official --json AuthURL is a sensitive short-lived authorization URL.
No URL is printed/logged or saved by NOW. Polkit prompts for privileges. The
unprivileged helper opens the URL in the user's own default browser.
"""
import json
import os
import select
import shutil
import subprocess
import sys
import time
import urllib.parse
import webbrowser

MAX_LINE = 32768
WAIT_SECONDS = 180
ALLOWED_HOST = "login.tailscale.com"


def valid_login_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parsed = urllib.parse.urlsplit(value)
        return (parsed.scheme == "https" and parsed.hostname == ALLOWED_HOST
                and parsed.port is None and not parsed.username
                and not parsed.password and parsed.path.startswith("/a/")
                and not parsed.fragment)
    except ValueError:
        return False


def start_login(popen=subprocess.Popen, browser=webbrowser.open, timeout=WAIT_SECONDS):
    if not shutil.which("pkexec") or not shutil.which("tailscale"):
        return 2
    # No shell or password handling. Privilege authorization belongs to polkit.
    cmd = ["pkexec", "/usr/bin/tailscale", "up", "--json"]
    if not os.path.isfile("/usr/bin/tailscale"):
        resolved = shutil.which("tailscale")
        if not resolved or not os.path.isabs(resolved):
            return 2
        cmd[1] = resolved
    process = None
    try:
        process = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL)
        deadline = time.monotonic() + timeout
        buffer = bytearray()
        opened = False
        while time.monotonic() < deadline:
            if process.poll() is not None and not opened:
                break
            if process.stdout is None:
                break
            ready, _, _ = select.select([process.stdout], [], [], 0.25)
            if not ready:
                if opened and process.poll() is not None:
                    return 0 if process.returncode == 0 else 1
                continue
            data = os.read(process.stdout.fileno(), 4096)
            if not data:
                break
            buffer.extend(data)
            if len(buffer) > MAX_LINE:
                break
            while b"\n" in buffer:
                line, _, rest = buffer.partition(b"\n")
                buffer = bytearray(rest)
                try:
                    payload = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                url = payload.get("AuthURL")
                if not opened and valid_login_url(url):
                    if not browser(url):
                        return 1
                    opened = True
                if payload.get("BackendState") == "Running":
                    return 0
                if payload.get("Error"):
                    return 1
        return 1
    except (OSError, ValueError):
        return 1
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def main():
    # This is launched by an explicit GUI click, never automatically on app open.
    return start_login()


if __name__ == "__main__":
    sys.exit(main())
