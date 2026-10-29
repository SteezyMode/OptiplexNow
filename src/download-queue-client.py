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

def fetch(host, user, runner=subprocess.run, include_port=False, native=False):
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
    if native and not include_port:
        raise ValueError("Native queue requires approved port metadata")
    lines = []
    native_lines = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Malformed queue")
        name, state, progress = (item.get("name"), item.get("state"),
                                 item.get("progress_percent"))
        torrent_hash=item.get("torrent_hash")
        speed, eta, seeds=(item.get("download_bps"),item.get("eta_seconds"),
                            item.get("seeders"))
        if (not isinstance(torrent_hash,str) or
                not re.fullmatch(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?",torrent_hash)
                or any(type(v) is not int or not -1<=v<=2**31-1
                       for v in (speed,eta,seeds))):
            raise ValueError("Malformed torrent status")
        if not isinstance(name, str) or not isinstance(state, str) or (
                type(progress) not in (int, float)) or not 0 <= progress <= 100:
            raise ValueError("Malformed queue")
        clean_name = "".join(ch if ch.isprintable() else " " for ch in name)[:160]
        clean_state = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in state)[:48]
        lines.append(f"{progress:5.1f}%   {clean_state:<16}   {clean_name}")
        # Printable, bounded, tab-free wire format for the native GTK queue.
        # Only torrent content hashes (opaque selectors), no paths, credentials or raw JSON.
        native_lines.append(f"ITEM\t{progress:.1f}\t{clean_state}\t{clean_name}\t{torrent_hash.lower()}\t{speed}\t{eta}\t{seeds}")
    display = "\n".join(lines) if lines else "No downloads in queue."
    if not include_port:
        return display
    # Bounded host-derived metadata only; never return credentials or Docker paths.
    port = obj.get("webui_port", 0)
    if type(port) is not int or not (port == 0 or 1024 <= port <= 65535):
        raise ValueError("Unusable download endpoint")
    if native:
        return f"WEBUI_PORT={port}\n" + (
            "\n".join(native_lines) if native_lines else "EMPTY")
    return f"WEBUI_PORT={port}\n{display}"

if __name__ == "__main__":
    try:
        if len(sys.argv) not in (3, 4) or (len(sys.argv) == 4 and
                sys.argv[3] not in ("--with-port", "--native")):
            raise ValueError("Expected server and SSH user")
        native = len(sys.argv) == 4 and sys.argv[3] == "--native"
        print(fetch(sys.argv[1], sys.argv[2], include_port=len(sys.argv) == 4,
                    native=native))
    except (ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError):
        print("Queue unavailable. Check approved host and downloader.")
        sys.exit(1)
