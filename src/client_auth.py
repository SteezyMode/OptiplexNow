#!/usr/bin/env python3
"""Read-only Tailscale authentication readiness for the existing NOW wizard.

This helper never logs in, starts services, changes tailnet policy, or outputs
account/node/secret data. Only fixed non-sensitive state names leave the process.
"""
import argparse
import json
import shutil
import subprocess

STATES = frozenset(("connected", "login_required", "disconnected",
                    "missing", "unavailable"))


def classify(status):
    if not isinstance(status, dict):
        return "unavailable"
    state = status.get("BackendState")
    if state == "Running" and isinstance(status.get("Self"), dict):
        return "connected"
    if state == "NeedsLogin":
        return "login_required"
    if state in ("Stopped", "NoState"):
        return "disconnected"
    return "unavailable"


def tailscale_state(*, which=shutil.which, runner=subprocess.run):
    if not which("tailscale"):
        return "missing"
    try:
        proc = runner(["tailscale", "status", "--json"], check=False,
                      capture_output=True, text=True, timeout=3)
        if proc.returncode != 0 or len(proc.stdout) > 524288:
            return "unavailable"
        return classify(json.loads(proc.stdout))
    except (OSError, subprocess.TimeoutExpired, ValueError, UnicodeError):
        return "unavailable"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only NOW Tailscale state")
    parser.add_argument("service", choices=("tailscale",))
    parser.parse_args(argv)
    print(tailscale_state())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
