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

MAX_BUFFER = 131072
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


class JSONMessageStream:
    """Read consecutive pretty-printed CLI JSON documents safely.

    Tailscale's 'up --json' outputs two *multiline* objects, not JSONL.
    Individual reads can stop in the middle of a JSON token or object.
    """
    def __init__(self):
        self.pending = ""

    def feed(self, chunk):
        if not isinstance(chunk, (bytes, bytearray)):
            raise ValueError("Expected CLI output bytes")
        # CLI JSON is UTF-8. Keep a bounded buffer; tolerate a split non-ASCII
        # diagnostic without letting a decoding exception crash setup.
        self.pending += chunk.decode("utf-8", errors="replace")
        if len(self.pending) > MAX_BUFFER:
            raise ValueError("Tailscale output exceeded safe buffer limit")
        messages = []
        decoder = json.JSONDecoder()
        while True:
            self.pending = self.pending.lstrip()
            if not self.pending:
                return messages
            if not self.pending.startswith("{"):
                raise ValueError("Unexpected Tailscale CLI output")
            try:
                value, end = decoder.raw_decode(self.pending)
            except json.JSONDecodeError:
                # A complete object has not arrived yet.
                return messages
            if not isinstance(value, dict):
                raise ValueError("Expected Tailscale JSON object")
            messages.append(value)
            self.pending = self.pending[end:]


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
        parser = JSONMessageStream()
        opened = False
        while time.monotonic() < deadline:
            if process.stdout is None:
                break
            ready, _, _ = select.select([process.stdout], [], [], 0.25)
            if ready:
                data = os.read(process.stdout.fileno(), 4096)
                if data:
                    for payload in parser.feed(data):
                        url = payload.get("AuthURL")
                        if not opened and valid_login_url(url):
                            if not browser(url):
                                return 1
                            opened = True
                        if payload.get("BackendState") == "Running":
                            return 0
                        if payload.get("Error"):
                            return 1
                elif process.poll() is not None:
                    break
            # Don't discard buffered JSON if the child exited between polls.
            # All readable data above is processed before considering exit.
            if process.poll() is not None and not ready:
                break
        if process.poll() is not None and process.returncode == 0:
            # The CLI completed successfully, but a clean client also checks
            # actual Tailscale state separately before claiming 'connected'.
            return 0
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
