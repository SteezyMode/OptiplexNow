"""One bounded owner-only search against existing qBittorrent plugins.

This is a HOST-LOCAL transport module, not an endpoint or access grant.
Call only after the restricted per-device owner policy has authenticated the
requester. Never expose gateway container IDs, WebUI credentials or arbitrary
URLs to a client. Starting/deleting a search job changes only qBittorrent's
transient search state, NEVER the torrent queue.
"""
import json
import re
import subprocess
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from download_inventory import InventoryError
from download_queue import locate_verified_downloader

MAX_BYTES = 65536
MAX_RESULTS = 20
MAX_MAGNET = 1024
QUERY_LIMIT = 96


class SearchError(InventoryError):
    pass


def checked_query(value):
    if not isinstance(value, str) or not 2 <= len(value.strip()) <= QUERY_LIMIT:
        raise SearchError("Search must contain 2–96 characters")
    query = value.strip()
    if any(ord(c) < 32 or ord(c) == 127 for c in query):
        raise SearchError("Search contains a control character")
    return query


def checked_magnet(value):
    """Only directly usable magnet URIs; never return search-plugin page links.

    Torrents requiring qBittorrent's plugin-specific download handler are
    marked unsupported instead of accidentally added to /downloads.
    """
    if not isinstance(value, str) or not 10 <= len(value) <= MAX_MAGNET:
        return None
    try:
        parts = urlsplit(value)
        if (parts.scheme != "magnet" or parts.netloc or parts.path or
                parts.fragment or not parts.query):
            return None
        xt = parse_qs(parts.query, keep_blank_values=True).get("xt", [])
        if not any(re.fullmatch(r"urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", v)
                   or re.fullmatch(r"urn:btmh:1220[a-fA-F0-9]{64}", v)
                   for v in xt):
            return None
    except (ValueError, UnicodeError):
        return None
    if any(ord(c) < 33 or ord(c) > 126 for c in value):
        return None
    return value


def _api(runner, gateway, port, action, *, fields=None):
    """Fixed localhost API paths and subprocess argv; no caller-selected URL."""
    if action not in ("start", "results", "stop", "delete"):
        raise SearchError("Unsupported search API operation")
    url = f"http://127.0.0.1:{port}/api/v2/search/{action}"
    argv = ["docker", "exec", gateway, "wget", "-q", "-T", "5", "-O", "-"]
    if action == "start":
        argv += ["--post-data=" + urlencode(fields or {})]
    elif action in ("stop", "delete"):
        argv += ["--post-data=" + urlencode(fields or {})]
    else:
        url += "?" + urlencode(fields or {})
    argv.append(url)
    try:
        completed = runner(argv, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SearchError("Search service unavailable") from exc
    if (completed.returncode != 0 or not isinstance(completed.stdout, bytes)
            or len(completed.stdout) > MAX_BYTES):
        raise SearchError("Search API request failed")
    return completed.stdout


def _results(raw):
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise SearchError("Invalid search response") from exc
    if (not isinstance(payload, dict) or
            payload.get("status") not in ("Running", "Stopped") or
            type(payload.get("total")) is not int or payload["total"] < 0 or
            not isinstance(payload.get("results"), list) or
            len(payload["results"]) > MAX_RESULTS):
        raise SearchError("Invalid search result structure")
    sanitized = []
    for item in payload["results"]:
        if not isinstance(item, dict):
            raise SearchError("Invalid search result")
        title = item.get("fileName")
        size = item.get("fileSize")
        seeds = item.get("nbSeeders")
        if (not isinstance(title, str) or not title or len(title) > 512
                or type(size) is not int or size < -1
                or type(seeds) is not int or seeds < -1):
            raise SearchError("Search result has invalid fields")
        safe_title = "".join(c if c.isprintable() else " " for c in title)[:160]
        magnet = checked_magnet(item.get("fileUrl"))
        sanitized.append({"name": safe_title, "bytes": size, "seeders": seeds,
                          "can_add": bool(magnet), "magnet": magnet})
    return {"status": payload["status"], "total": payload["total"],
            "results": sanitized}


def search_once(query, *, runner=subprocess.run, sleeper=time.sleep):
    """Gather a small snapshot, then tear down ONLY the newly created search job.

    No continuous background worker; a future broker can call this with an
    explicit timeout, and surface partial=True if plugins are still searching.
    The returned magnet is metadata, NOT a request to enqueue anything.
    """
    pattern = checked_query(query)
    gateway, port = locate_verified_downloader(runner=runner)
    raw = _api(runner, gateway, port, "start",
               fields={"pattern": pattern, "plugins": "enabled",
                       "category": "all"})
    try:
        started = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise SearchError("Search job did not start") from exc
    if (not isinstance(started, dict) or type(started.get("id")) is not int
            or not 0 <= started["id"] < 2**31):
        raise SearchError("Invalid search job ID")
    job_id = started["id"]
    last = None
    try:
        for _ in range(3):
            sleeper(1)
            last = _results(_api(runner, gateway, port, "results",
                                 fields={"id": job_id, "limit": MAX_RESULTS,
                                         "offset": 0}))
            if last["status"] == "Stopped":
                break
        if last is None:
            raise SearchError("Search produced no response")
        last["partial"] = last["status"] == "Running"
        return last
    finally:
        # Job IDs always come from qBittorrent's checked start reply.
        # Cleanup errors may leave an orphaned search, not a torrent transfer.
        for action in ("stop", "delete"):
            try:
                _api(runner, gateway, port, action, fields={"id": job_id})
            except SearchError:
                pass
