#!/usr/bin/env python3
"""Prove the API Bay qBittorrent Nova engine WITHOUT installing it.

Run this from inside the existing qBittorrent container. It fetches only
SHA-256-pinned, reviewed plugin sources from an immutable GitHub commit, makes a
private temporary copy of qBittorrent's Nova runner and runs one search per
candidate against the public APIs. No WebUI, torrents, plugin registry or
live configuration is accessed or modified.
"""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote
from urllib.request import Request, urlopen

NOVA_ROOT = Path("/config/qBittorrent/nova3")
SOURCE_REF = "394def2d9a2eaa3eb6f429fd423f984adab328f1"
SOURCE_BASE = (
    "https://raw.githubusercontent.com/SteezyMode/OptiplexNow/"
    + SOURCE_REF + "/server/search_plugins/"
)
SOURCES = {
    "_bruiser_source.py": "5a6a0c7c9103a018fb135f8f1dcddb00c1626841b94e2d8d86de63a8037472d8",
    "bruiser_apibay.py": "84b029d799ef403f232d7576a3bcd5d518be5b7bdc82118c755bdfb76338b42e",
}
SEARCH_PHRASE = "south park s29e04"


def obtain_source(name, sha256):
    req = Request(SOURCE_BASE + name, headers={"User-Agent": "BruiserNovaProbe/1.0"})
    with urlopen(req, timeout=8) as response:
        data = response.read(64 * 1024 + 1)
    if len(data) > 64 * 1024 or hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("Candidate source SHA-256 verification failed")
    return data


def main():
    print("TEMPORARY NOVA PLUGIN TEST — installed qBittorrent plugins unchanged", flush=True)
    with tempfile.TemporaryDirectory(prefix="bruiser-nova-test-") as temp:
        sandbox = Path(temp)
        for filename in ("nova2.py", "helpers.py", "novaprinter.py"):
            source = NOVA_ROOT / filename
            if not source.is_file():
                raise ValueError("Missing existing qBittorrent Nova runner")
            shutil.copy2(source, sandbox / filename)
        directory = sandbox / "engines"
        directory.mkdir()
        (directory / "__init__.py").write_text("", encoding="utf-8")
        for name, sha256 in SOURCES.items():
            (directory / name).write_bytes(obtain_source(name, sha256))

        for engine in ("bruiser_apibay",):
            started = time.monotonic()
            try:
                result = subprocess.run(
                    [sys.executable, str(sandbox / "nova2.py"),
                     engine, "all", *SEARCH_PHRASE.split(" ")],
                    cwd=sandbox, capture_output=True, text=True, timeout=10)
            except subprocess.TimeoutExpired:
                print(f"{engine}: TIMEOUT >10 seconds", flush=True)
                continue
            rows = []
            for line in result.stdout.splitlines():
                fields = line.split("|")
                if len(fields) == 8 and fields[0].startswith("magnet:?xt=urn:btih:"):
                    rows.append(fields)
            titles = [unquote(item[1]) for item in rows]
            matches = [title for title in titles if re.search(r"(?i)\bs29[._ -]*e04\b", title)]
            print(f"{engine}: exit={result.returncode} "
                  f"elapsed={time.monotonic()-started:.2f}s "
                  f"valid_magnets={len(rows)} episode_matches={len(matches)}", flush=True)
            for title in matches[:2]:
                print("  title:", title[:120], flush=True)
            if result.returncode != 0:
                print("  Nova error:", result.stderr[-250:].replace("\n", " "), flush=True)
    print("Temporary files deleted. No installed plugin or download was modified.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        print("Candidate probe could not complete:", type(exc).__name__, flush=True)
        sys.exit(1)
