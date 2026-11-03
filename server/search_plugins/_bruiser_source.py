"""Shared, bounded HTTP and magnet normalization for Bruiser Nova engines.

These engines only search public indexes. They do not access the downloader
queue, its WebUI or credentials. The qBittorrent Nova runner handles SOCKS
proxy setup before invoking an engine; standard-library HTTP uses that socket.
"""
import json
import re
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

TIMEOUT_SECONDS = 4
MAX_BODY_BYTES = 1_048_576
MAX_QUERY_LENGTH = 96
HASH = re.compile(r"[0-9a-fA-F]{40}\Z")
TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
)


def search_terms(what):
    if not isinstance(what, str):
        return None
    # qBittorrent's nova2.py encodes spaces before invoking search().
    query = unquote(what).strip()
    if not 2 <= len(query) <= MAX_QUERY_LENGTH or any(ord(c) < 32 for c in query):
        return None
    return query


def read_json(url):
    request = Request(url, headers={
        "User-Agent": "BruiserSearch/1.0",
        "Accept": "application/json",
    })
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            # Providers may change redirects. Refuse to follow a non-HTTPS
            # final URL; qBittorrent's configured proxy still applies.
            original = urlsplit(url)
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != original.hostname:
                return None
            content = response.read(MAX_BODY_BYTES + 1)
        if len(content) > MAX_BODY_BYTES:
            return None
        return json.loads(content)
    except (OSError, ValueError, UnicodeError, TimeoutError):
        return None


def as_int(value, default=-1):
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (ValueError, TypeError, OverflowError):
        return default
    return number if 0 <= number <= 2**63-1 else default


def validated_title(value):
    if not isinstance(value, str):
        return None
    title = " ".join(value.split())
    if not title or len(title) > 160 or any(ord(c) < 32 for c in title):
        return None
    return title


def build_magnet(info_hash, name):
    if not isinstance(info_hash, str) or not HASH.fullmatch(info_hash):
        return None
    if not name:
        return None
    magnet = "magnet:?xt=urn:btih:" + info_hash.lower() + "&dn=" + quote(name, safe="")
    for tracker in TRACKERS:
        magnet += "&tr=" + quote(tracker, safe="")
    return magnet if len(magnet) <= 1024 else None
