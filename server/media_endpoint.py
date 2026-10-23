"""Read-only, host-local Jellyfin detection for the NOW media integration.

This is inventory, NOT a public discovery listener or trusted client response.
Only probes the fixed loopback endpoint; host-bound publication and client
reachability/authentication must be implemented separately.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOOPBACK_INFO = "http://127.0.0.1:8096/System/Info/Public"
MAX_REPLY = 8192


def inspect_local_jellyfin(*, opener=urlopen):
    """Return a minimal allowlisted descriptor; never return API keys."""
    req = Request(LOOPBACK_INFO, headers={"Accept": "application/json"})
    try:
        with opener(req, timeout=3) as res:
            if res.status != 200:
                return {"service": "jellyfin", "available": False}
            data = res.read(MAX_REPLY + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        return {"service": "jellyfin", "available": False}
    if len(data) > MAX_REPLY:
        return {"service": "jellyfin", "available": False}
    try:
        obj = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return {"service": "jellyfin", "available": False}
    if not isinstance(obj, dict):
        return {"service": "jellyfin", "available": False}
    identifier = obj.get("Id")
    name = obj.get("ServerName")
    if not isinstance(identifier, str) or not 1 <= len(identifier) <= 128:
        return {"service": "jellyfin", "available": False}
    result = {"service": "jellyfin", "available": True}
    if isinstance(name, str) and 0 < len(name) <= 128:
        result["name"] = name
    return result
