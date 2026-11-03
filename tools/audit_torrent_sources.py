#!/usr/bin/env python3
"""Read-only search-source latency/coverage audit from a downloader namespace.

No torrent is added, no search plugin is installed, no host or container
configuration is modified, and no secrets are read. Use only for candidate
selection; this does not certify a qBittorrent plugin or its VPN kill switch.
"""
import concurrent.futures
from datetime import datetime, timezone
import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 1024 * 1024
USER_AGENT = "BruiserSourceAudit/1.0"
QUERIES = ("south park s29e04", "south park")
EPISODE_RE = re.compile(r"(?i)(?:^|\W)(?:s29[ ._-]*e04|29x04)(?:$|\W)")
SHOW_RE = re.compile(r"(?i)south[ ._-]*park")


def source_url(provider, query):
    if provider == "TorrentsCSV":
        return "https://torrents-csv.com/service/search?" + urlencode(
            {"size": 25, "q": query})
    if provider == "TorrentClaw":
        return "https://torrentclaw.com/api/v1/search?" + urlencode(
            {"limit": 50, "q": query})
    if provider == "API Bay":
        return "https://apibay.org/q.php?" + urlencode(
            {"q": query, "cat": 0})
    if provider == "EZTV API":
        # A show-specific lookup, not a keyword-search API.
        return "https://eztvx.to/api/get-torrents?" + urlencode(
            {"limit": 100, "page": 1, "imdb_id": "0121955"})
    raise ValueError("Unknown source")


def title_entries(provider, payload):
    if provider == "TorrentsCSV":
        data = payload.get("torrents", []) if isinstance(payload, dict) else []
        return [(str(x.get("name", "")), x.get("created_unix"))
                for x in data if isinstance(x, dict)]
    if provider == "TorrentClaw":
        result = payload.get("results", []) if isinstance(payload, dict) else []
        rows = []
        for content in result:
            if not isinstance(content, dict):
                continue
            for item in content.get("torrents") or []:
                if isinstance(item, dict):
                    rows.append((
                        str(item.get("rawTitle") or content.get("title") or ""),
                        item.get("uploadedAt")))
        return rows
    if provider == "API Bay":
        if not isinstance(payload, list):
            return []
        return [(str(x.get("name", "")), x.get("added"))
                for x in payload if isinstance(x, dict)
                and x.get("name") != "No results returned"]
    if provider == "EZTV API":
        data = payload.get("torrents", []) if isinstance(payload, dict) else []
        return [(str(x.get("title", "")), x.get("date_released_unix"))
                for x in data if isinstance(x, dict)]
    return []


def timestamp(value):
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)) or (
                isinstance(value, str) and value.isdigit()):
            epoch = int(value)
            if 946684800 <= epoch <= 4102444800:
                return datetime.fromtimestamp(epoch, timezone.utc)
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        pass
    return None


def audit(provider, query):
    begin = time.monotonic()
    try:
        request = Request(source_url(provider, query), headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ValueError("Response too large")
        payload = json.loads(content)
        rows = title_entries(provider, payload)
        candidates = [
            (name, stamp) for name, stamp in rows
            if SHOW_RE.search(name) and EPISODE_RE.search(name)
        ]
        times = [timestamp(stamp) for _, stamp in rows]
        times = [dt for dt in times if dt is not None]
        newest = max(times).strftime("%Y-%m-%d") if times else "unknown"
        return (provider, query, time.monotonic() - begin,
                len(rows), len(candidates), newest, "OK",
                [name[:100] for name, _ in candidates[:2]])
    except Exception as exc:
        return (provider, query, time.monotonic() - begin,
                0, 0, "-", type(exc).__name__, [])


def main():
    print("READ-ONLY source audit — no plugin, torrent, or config changes",
          flush=True)
    print("One 5-second network timeout per source; elapsed time measured",
          flush=True)
    work = [(provider, query) for provider in
            ("TorrentsCSV", "TorrentClaw", "API Bay")
            for query in QUERIES]
    work.append(("EZTV API", "south park (IMDb show lookup)"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
        futures = [executor.submit(audit, *job) for job in work]
        results = [f.result() for f in futures]
    for provider, query, seconds, count, exact, newest, outcome, examples in results:
        print(f"{provider:12} | {seconds:5.2f}s | {query:32} "
              f"| rows={count:3} | S29E04={exact:2} "
              f"| newest={newest} | {outcome}", flush=True)
        for example in examples:
            print("   matching title:", example, flush=True)
    print("Note: direct HTTP from downloader's network namespace; plugin behavior",
          "and actual search performance still require separate validation.",
          flush=True)


if __name__ == "__main__":
    main()
