#!/usr/bin/env python3
"""Host-local Downloads transport for the actual logged-in owner.

This is never a remote listener or SSH forced command. The OS account
running the existing host broker and owning its configuration is the
authority. No Wolf identity is invented or enrolled.
"""
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
sys.path.insert(0, str(BASE / "server"))

from owner_access import PolicyError
from owner_enrollment import _read_private_config
from owner_games_request import _validated_request, handle_download_request

MAX_INPUT = 2048


def main():
    # An owner already has normal shell access to the same local downloader.
    # Never turn this into a root, setuid, or another-account access path.
    if os.getuid() == 0 or os.getuid() != os.geteuid():
        raise PolicyError("Local owner account required")
    config = _read_private_config()
    if config.get("enabled") is not True or config.get("legacy_links_reviewed") is not True:
        raise PolicyError("Host owner broker not enabled")
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT or not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise PolicyError("Invalid bounded local request")
    request = json.loads(raw)
    action = _validated_request(request)
    if not action.startswith("downloads_"):
        raise PolicyError("Games and administrative actions unavailable")
    def emit(data):
        print(json.dumps(data, ensure_ascii=True, separators=(",", ":")), flush=True)
    if request.get("stream") is True:
        def authorized_emit(snapshot):
            emit({"success": True, "service": "qbittorrent", **snapshot})
        result = handle_download_request(action, request, search_emitter=authorized_emit)
    else:
        result = handle_download_request(action, request)
    if result is not None:
        emit(result)


if __name__ == "__main__":
    try:
        main()
    except (PolicyError, OSError, ValueError, TypeError, KeyError, RuntimeError):
        print('{"success":false,"status":"denied"}')
        sys.exit(1)
