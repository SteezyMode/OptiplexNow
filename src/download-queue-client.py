#!/usr/bin/env python3
"""Minimal, owner-bound queue display transport; prints no raw qBittorrent JSON."""
import json
from pathlib import Path
import re
import subprocess
import sys

KEY = Path.home() / ".local/share/optiplex-now/games-client/id_ed25519"

def valid_host(s):
    return bool(re.fullmatch(r"[A-Za-z0-9.:-]{1,253}", s)) and not s.startswith("-")

def valid_user(s):
    return bool(re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_-]{0,31}", s))

def fetch(host, user, runner=subprocess.run):
    if not valid_host(host) or not valid_user(user) or not KEY.is_file():
        raise ValueError("Approved NOW host or device key unavailable")
    cmd = ["ssh", "-F", "/dev/null", "-T", "-i", str(KEY),
           "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
           "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=6",
           f"{user}@{host}"]
    p = runner(cmd, input=b'{"version":1,"action":"downloads_queue"}\n',
               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
               timeout=12, check=False)
    if p.returncode or len(p.stdout) > 65536:
        raise ValueError("Authorized queue request failed")
    obj = json.loads(p.stdout)
    if not isinstance(obj, dict) or obj.get("success") is not True or (
            obj.get("service") != "qbittorrent"):
        raise ValueError("Queue unavailable")
    items = obj.get("queue")
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError("Malformed queue")
    lines = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Malformed queue")
        name, state, progress = (item.get("name"), item.get("state"),
                                 item.get("progress_percent"))
        if not isinstance(name, str) or not isinstance(state, str) or (
                type(progress) not in (int, float)) or not 0 <= progress <= 100:
            raise ValueError("Malformed queue")
        clean_name = "".join(ch if ch.isprintable() else " " for ch in name)[:160]
        clean_state = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in state)[:48]
        lines.append(f"{progress:5.1f}%   {clean_state:<16}   {clean_name}")
    return "\n".join(lines) if lines else "No downloads in queue."

if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("Expected server and SSH user")
        print(fetch(sys.argv[1], sys.argv[2]))
    except (ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError):
        print("Queue unavailable. Check approved host and downloader.")
        sys.exit(1)
