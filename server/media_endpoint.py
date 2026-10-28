"""Read-only, host-local Jellyfin detection for the NOW media integration.

This is inventory, NOT a public discovery listener or trusted client response.
Only probes the fixed loopback endpoint; host-bound publication and client
reachability/authentication must be implemented separately.
"""
import json
import os
from pathlib import Path
import re
import stat
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)

LOOPBACK_INFO = "http://127.0.0.1:8096/System/Info/Public"
MAX_REPLY = 8192
MAX_OWNER_ENDPOINT = 2048
ENDPOINT_RELATIVE = re.compile(r"/(?:[A-Za-z0-9_-]{1,48})?\\Z")


def _no_duplicate_keys(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("Duplicate endpoint setting")
        data[key] = value
    return data


def owner_approved_endpoint(path=None):
    """Read owner-only, optional public SAME-HOST routing info (no URLs).

    This is not autodiscovery or permission to publish a new route. The host
    operator must deliberately configure a reachable Jellyfin listener.
    """
    path = Path(path) if path is not None else (
        Path.home() / ".config/optiplex-now/media-public-endpoint.json")
    try:
        details = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(details.st_mode) or
            details.st_uid != os.geteuid() or details.st_nlink != 1 or
            stat.S_IMODE(details.st_mode) != 0o600 or
            details.st_size > MAX_OWNER_ENDPOINT):
        raise ValueError("Unsafe owner media endpoint configuration")
    raw = path.read_bytes()
    if len(raw) > MAX_OWNER_ENDPOINT:
        raise ValueError("Owner media endpoint configuration too large")
    try:
        record = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Invalid media endpoint configuration") from exc
    if not isinstance(record, dict) or set(record) != {
            "version", "scheme", "port", "base_path"}:
        raise ValueError("Invalid media endpoint keys")
    if (type(record["version"]) is not int or record["version"] != 1 or
            record["scheme"] not in ("http", "https") or
            type(record["port"]) is not int or
            not 1 <= record["port"] <= 65535 or
            not isinstance(record["base_path"], str) or
            not ENDPOINT_RELATIVE.fullmatch(record["base_path"])):
        raise ValueError("Invalid host-approved media endpoint")
    return {"scheme": record["scheme"], "port": record["port"],
            "base_path": record["base_path"]}




class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The trusted host probes one fixed local URL, never a redirect
        # to another container, LAN peer or Internet service.
        return None


def _local_urlopen(request, timeout):
    # Do not let proxy environment variables redirect this local inventory.
    return build_opener(ProxyHandler({}), _NoRedirect()).open(
        request, timeout=timeout)


def inspect_local_jellyfin(*, opener=_local_urlopen, endpoint_path=None):
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
    # A malformed explicit owner configuration must never silently revert to
    # some other endpoint. No owner file means legacy same-host 8096 only.
    try:
        endpoint = owner_approved_endpoint(endpoint_path)
    except (OSError, ValueError):
        return {"service": "jellyfin", "available": False}
    if endpoint is not None:
        result["endpoint"] = endpoint
    return result
