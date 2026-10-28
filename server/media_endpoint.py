"""Read-only, host-local Jellyfin detection for the NOW media integration.

This is inventory, NOT a public discovery listener or trusted client response.
Only probes the fixed loopback endpoint; host-bound publication and client
reachability/authentication must be implemented separately.
"""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)

LOOPBACK_INFO = "http://127.0.0.1:8096/System/Info/Public"
MAX_REPLY = 8192


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The trusted host probes one fixed local URL, never a redirect
        # to another container, LAN peer or Internet service.
        return None


def _local_urlopen(request, timeout):
    # Do not let proxy environment variables redirect this local inventory.
    return build_opener(ProxyHandler({}), _NoRedirect()).open(
        request, timeout=timeout)


def inspect_local_jellyfin(*, opener=_local_urlopen):
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
    # The public Jellyfin server ID is not a credential, but it binds the
    # authenticated host declaration to the endpoint the client can actually
    # reach. Never relay arbitrary URLs, API keys, headers or session data.
    if not isinstance(identifier, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", identifier):
        return {"service": "jellyfin", "available": False}
    result = {"service": "jellyfin", "available": True,
              "server_id": identifier}
    if isinstance(name, str) and 0 < len(name) <= 128:
        result["name"] = name
    return result
