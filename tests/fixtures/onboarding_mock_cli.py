#!/usr/bin/env python3
"""Disposable fake CLI endpoints for integrated NOW onboarding tests.

This file is invoked through symlinks named tailscale, ssh-copy-id, ssh, and
docker inside a TemporaryDirectory. Never run it as part of a real client.
No network connections, host account changes, or real Docker access.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(os.environ["NOW_TEST_FIXTURE_ROOT"])
PROGRAM = Path(sys.argv[0]).name


def load(name, default):
    path = ROOT / name
    return json.loads(path.read_text()) if path.exists() else default


def save(name, value):
    (ROOT / name).write_text(json.dumps(value))


def append_log(name, value):
    with (ROOT / name).open("a") as file:
        file.write(json.dumps(value) + "\n")


def mock_tailscale():
    if sys.argv[1:] != ["status", "--json"]:
        return 2
    if os.environ.get("NOW_MOCK_TAILSCALE_FAIL") == "1":
        return 1
    print(json.dumps(load("tailnet.json", {})))
    return 0


def mock_copy_id():
    # Never accepts an arbitrary remote command, only a public key and an
    # explicitly named host. The host fingerprint/password dialogs are
    # simulated by this executable, not proved by the test.
    args = sys.argv[1:]
    if ("StrictHostKeyChecking=ask" not in args or
            os.environ.get("SSH_ASKPASS_REQUIRE") != "force" or
            not os.environ.get("SSH_ASKPASS") or
            not Path(os.environ["SSH_ASKPASS"]).is_file() or
            len(args) < 4):
        return 2
    try:
        key = Path(args[args.index("-i") + 1])
    except (ValueError, IndexError):
        return 2
    if not key.is_file() or not key.read_text().startswith("ssh-ed25519 "):
        return 2
    append_log("copy-id.jsonl", {"host": args[-1], "key": key.name,
                                  "strict": "StrictHostKeyChecking=ask"})
    if os.environ.get("NOW_MOCK_AUTH_DENIED") == "1":
        return 1
    save("authorized.json", {"host": args[-1], "pub": key.read_text()})
    return 0


def mock_ssh():
    args = sys.argv[1:]
    if (os.environ.get("NOW_MOCK_SSH_UNREACHABLE") == "1" or
            "StrictHostKeyChecking=yes" not in args or
            "--" not in args):
        return 255
    if len(args) < 3 or args[-1] not in ("pending", "pair"):
        return 2
    # The real client sends a PIN to SSH stdin, not argv.
    if any("0123" in part or "9876" in part for part in args):
        return 2
    append_log("ssh.jsonl", {"action": args[-1], "strict": True})
    result = subprocess.run(
        [sys.executable, os.environ["NOW_TEST_HOST_HELPER"], args[-1]],
        input=sys.stdin.buffer.read(), capture_output=True, timeout=9,
        env=os.environ.copy(), check=False
    )
    sys.stdout.buffer.write(result.stdout)
    return result.returncode


def mock_docker():
    if len(sys.argv) < 8 or sys.argv[1:5] != ["exec", "-i", "wolf", "python3"]:
        return 2
    method, endpoint = sys.argv[-2:]
    pending = load("pending.json", [])
    if method == "GET" and endpoint == "/api/v1/pair/pending":
        print(json.dumps({"success": True, "requests": pending}))
        return 0
    if method == "POST" and endpoint == "/api/v1/pair/client":
        try:
            payload = json.loads(sys.stdin.buffer.read())
        except ValueError:
            return 2
        append_log("wolf-post.jsonl", {"pin": payload.get("pin")})
        authorized = any(
            p.get("pair_secret") == payload.get("pair_secret")
            and len(payload.get("pin", "")) == 4 for p in pending
        ) and os.environ.get("NOW_MOCK_WOLF_DENIED") != "1"
        if authorized:
            save("pending.json", [])
        print(json.dumps({"success": authorized}))
        return 0
    return 2


if __name__ == "__main__":
    result = {"tailscale": mock_tailscale,
              "ssh-copy-id": mock_copy_id,
              "ssh": mock_ssh,
              "docker": mock_docker}.get(PROGRAM)
    if result is None:
        raise SystemExit(2)
    raise SystemExit(result())
