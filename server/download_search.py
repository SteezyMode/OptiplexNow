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

MAX_BYTES = 262144
MAX_RESULTS = 100
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


def _api(runner, gateway, port, action, *, fields=None, session=None):
    """One localhost request within a single ephemeral qBittorrent search session.

    The host's local WebUI issues a new SID if no Cookie is supplied. A search
    job is scoped to the SID which created it: without reuse, results and
    cleanup report HTTP 404 even though starting the job succeeded. Capture
    the start response's Set-Cookie in memory only; never expose or log it.
    """
    if action not in ("start", "results", "stop", "delete"):
        raise SearchError("Unsupported search API operation")
    if action != "start" and (not isinstance(session, str) or
                                not re.fullmatch(r"[A-Za-z0-9+/_=-]{1,256}", session)):
        raise SearchError("Search session unavailable")
    url = f"http://127.0.0.1:{port}/api/v2/search/{action}"
    argv = ["docker", "exec", gateway, "wget", "-q", "-T", "5", "-O", "-",
            "--header", f"Referer: http://127.0.0.1:{port}/"]
    if action == "start":
        argv.append("-S")  # Headers to captured stderr, never to client.
    else:
        argv += ["--header", f"Cookie: SID={session}"]
    if action in ("start", "stop", "delete"):
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
    if action != "start":
        return completed.stdout, session
    # GNU wget -S emits HTTP response headers on stderr even with -q.
    headers = completed.stderr
    if not isinstance(headers, bytes) or len(headers) > 8192:
        raise SearchError("Search session unavailable")
    match = re.search(
        rb"(?im)^[ \t]*set-cookie:[ \t]*SID=([A-Za-z0-9+/_=-]{1,256})(?:;|[ \t]*\r?$)",
        headers)
    if not match:
        raise SearchError("Search session unavailable")
    return completed.stdout, match.group(1).decode("ascii")


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
    """Return the first usable bounded snapshot without a mandatory 12s wait.

    Still poll up to twelve times when the enabled plugins find nothing.
    Return partial=True when plugins are running; each search uses one fresh
    SID and cleans up only its own search job. Never enqueue torrent data.
    """
    pattern = checked_query(query)
    gateway, port = locate_verified_downloader(runner=runner)
    raw, session = _api(runner, gateway, port, "start",
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
        for _ in range(12):
            sleeper(1)
            reply, _ = _api(runner, gateway, port, "results",
                            fields={"id": job_id, "limit": MAX_RESULTS,
                                    "offset": 0}, session=session)
            last = _results(reply)
            # Show the first validated results without waiting for every
            # search plugin to finish its 12-second window. The response
            # explicitly marks partial=True if plugins are still running.
            # Cleanup remains restricted to this search job, never torrents.
            if last["status"] == "Stopped" or last["results"]:
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
                _api(runner, gateway, port, action, fields={"id": job_id},
                     session=session)
            except SearchError:
                pass
