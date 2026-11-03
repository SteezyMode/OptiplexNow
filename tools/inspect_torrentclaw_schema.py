#!/usr/bin/env python3
"""Read-only TorrentClaw API schema diagnostic; never print hashes or magnets.

Run inside the downloader network namespace. Sends one bounded search query
to the public, unauthenticated endpoint using the exact candidate plugin's
headers and records only response shape and aggregate validity statistics.
"""
import json
import re
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

URL = "https://torrentclaw.com/api/v1/search?" + urlencode({
    "q": "south park s29e04",
    "limit": 50,
})
MAX_BYTES = 1024 * 1024
VALID_HASH = re.compile(r"^[A-Fa-f0-9]{40}$")


def main():
    begin = time.monotonic()
    try:
        request = Request(URL, headers={
            "User-Agent": "BruiserSearch/1.0",
            "Accept": "application/json",
        })
        with urlopen(request, timeout=6) as response:
            final = response.geturl()
            body = response.read(MAX_BYTES + 1)
            status = response.status
        print("HTTP:", status, "| elapsed:", round(time.monotonic() - begin, 2), "s")
        print("Final host:", urlsplit(final).hostname)
        if len(body) > MAX_BYTES:
            print("ERROR: Body exceeded 1 MiB")
            return
        obj = json.loads(body)
    except Exception as exc:
        print("ERROR:", type(exc).__name__)
        return

    print("Response type:", type(obj).__name__)
    if not isinstance(obj, dict):
        return
    print("Top-level fields:", sorted(obj))
    groups = obj.get("results")
    print("Results field:", type(groups).__name__,
          "| groups:", len(groups) if isinstance(groups, list) else "n/a")
    if not isinstance(groups, list):
        return

    items = []
    for group in groups[:50]:
        if not isinstance(group, dict):
            continue
        for item in group.get("torrents") or []:
            if isinstance(item, dict):
                items.append(item)
    print("Nested torrents:", len(items))
    if not items:
        return

    print("Example field names:", sorted(items[0]))
    print("Example field types:",
          {key: type(value).__name__ for key, value in items[0].items()
           if key.lower() in ("infohash", "info_hash", "magneturl", "rawtitle",
                               "sizebytes", "seeders", "uploadedat")})
    for key in ("infoHash", "info_hash", "hash", "btih", "magnetUrl"):
        available = sum(item.get(key) not in (None, "") for item in items)
        hex40 = sum(isinstance(item.get(key), str) and
                    bool(VALID_HASH.fullmatch(item[key])) for item in items)
        print(f"{key}: present={available}, valid_40_hex={hex40}")
    print("No titles, magnet links, infohash values, credentials, or torrent",
          "files were retrieved or printed.")


if __name__ == "__main__":
    main()
