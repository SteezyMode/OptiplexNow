#!/usr/bin/env python3
"""Read-only temporary qBittorrent Nova test of API Bay with duplication audit.

Runs inside the existing qBittorrent container. All candidate Python sources
are fetched from an immutable commit and verified against SHA-256. Copies
Nova runtime files into an automatically deleted temporary directory. Never
installs/enables a plugin or interacts with the qBittorrent Web API, downloads,
credentials, filesystem outside the temporary directory, or VPN configuration.
"""
from collections import Counter
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import Request, urlopen

NOVA_ROOT = Path("/config/qBittorrent/nova3")
PINNED_REF = "394def2d9a2eaa3eb6f429fd423f984adab328f1"
SOURCE_BASE = (
    "https://raw.githubusercontent.com/SteezyMode/OptiplexNow/"
    + PINNED_REF + "/server/search_plugins/"
)
SOURCES = {
    "_bruiser_source.py":
        "5a6a0c7c9103a018fb135f8f1dcddb00c1626841b94e2d8d86de63a8037472d8",
    "bruiser_apibay.py":
        "84b029d799ef403f232d7576a3bcd5d518be5b7bdc82118c755bdfb76338b42e",
}
VALID_HASH = re.compile(r"[0-9A-Fa-f]{40}\Z")


def fetch_verified(name, digest):
    req = Request(SOURCE_BASE + name,
                  headers={"User-Agent": "BruiserNovaProbe/1.0"})
    with urlopen(req, timeout=8) as response:
        body = response.read(65537)
    if len(body) > 65536 or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("Pinned plugin source SHA-256 check failed")
    return body


def normalize_title(value):
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def summarize(output):
    rows = []
    invalid = 0
    webpage = 0
    for line in output.splitlines():
        fields = line.split("|")
        if len(fields) != 8:
            invalid += 1
            continue
        link, encoded, size, seeds, leechers, site, desc, published = fields
        if link.startswith("http://") or link.startswith("https://"):
            webpage += 1
            continue
        try:
            xt = parse_qs(urlsplit(link).query).get("xt", [])
            digest = xt[0].removeprefix("urn:btih:") if len(xt) == 1 else ""
            if (not link.startswith("magnet:?xt=urn:btih:")
                    or not VALID_HASH.fullmatch(digest)
                    or len(link) > 1024):
                invalid += 1
                continue
            name = unquote(encoded)
            if not name or len(name) > 160:
                invalid += 1
                continue
            seed_count = int(seeds)
        except (ValueError, IndexError, TypeError):
            invalid += 1
            continue
        rows.append((digest.lower(), name, size, seed_count))

    unique = set(row[0] for row in rows)
    by_title = Counter((normalize_title(row[1]), row[2]) for row in rows)
    by_hash = Counter(row[0] for row in rows)
    print("Raw Nova lines:", len(output.splitlines()))
    print("Valid magnet results:", len(rows))
    print("Unique infohashes:", len(unique))
    print("Repeated infohash entries:", sum(count - 1 for count in by_hash.values()))
    print("Repeated normalized title+size entries:",
          sum(count - 1 for count in by_title.values()))
    print("Webpage links:", webpage)
    print("Other invalid rows:", invalid)

    examples = []
    seen = set()
    for digest, title, size, seeds in sorted(rows, key=lambda x: -x[3]):
        if digest in seen:
            continue
        seen.add(digest)
        examples.append((title, seeds))
        if len(examples) >= 12:
            break
    print("Top distinct results by reported seeders:")
    for title, seeders in examples:
        print(f"  {seeders:5} seeds | {title[:110]}")
    return len(rows), len(unique), webpage, invalid


def main():
    query = " ".join(sys.argv[1:]).strip() or "resident evil"
    if not 2 <= len(query) <= 96 or any(ord(c) < 32 or ord(c) == 127 for c in query):
        raise ValueError("Query must be 2–96 printable characters")
    print("API BAY ONLY — TEMPORARY NOVA SEARCH", flush=True)
    print("Query:", query, flush=True)
    with tempfile.TemporaryDirectory(prefix="bruiser-apibay-audit-") as directory:
        work = Path(directory)
        for name in ("nova2.py", "helpers.py", "novaprinter.py"):
            shutil.copy2(NOVA_ROOT / name, work / name)
        engines = work / "engines"
        engines.mkdir()
        (engines / "__init__.py").write_text("", encoding="utf-8")
        for name, expected in SOURCES.items():
            (engines / name).write_bytes(fetch_verified(name, expected))
        started = time.monotonic()
        try:
            result = subprocess.run(
                [sys.executable, str(work / "nova2.py"),
                 "bruiser_apibay", "all", *query.split()],
                cwd=work, capture_output=True, text=True,
                timeout=8, check=False)
        except subprocess.TimeoutExpired:
            print("Timed out after 8 seconds. No plugins were installed.")
            return 2
        print("Elapsed seconds:", round(time.monotonic() - started, 2))
        print("Nova exit:", result.returncode)
        summarize(result.stdout)
        if result.returncode:
            print("Nova diagnostic:", result.stderr[-300:].replace("\n", " "))
        print("No installed plugins, torrent transfers or configuration changed.")
        return 0 if result.returncode == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print("Probe failed:", type(exc).__name__)
        raise SystemExit(1)
