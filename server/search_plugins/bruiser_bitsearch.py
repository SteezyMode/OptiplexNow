# VERSION: 1.2
# AUTHORS: Bruiser contributors
"""Bitsearch qBittorrent Nova engine supporting all selected categories.

One bounded public API request per search; independent of API Bay's request.
No tracker scraping, browser automation, API key, torrent download, local files
or changes to qBittorrent configuration.
"""
import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen
from novaprinter import prettyPrinter

MAX_BYTES = 1_048_576
TIMEOUT = 4
HASH = re.compile(r"[a-fA-F0-9]{40}\Z")
TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
)


def _integer(value):
    if isinstance(value, bool):
        return -1
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return -1
    return number if 0 <= number <= 2**63 - 1 else -1


def _date(value):
    if not isinstance(value, str) or len(value) > 40:
        return -1
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return -1
        seconds = int(parsed.astimezone(timezone.utc).timestamp())
        return seconds if 0 <= seconds <= 253402300799 else -1
    except (TypeError, OverflowError, ValueError):
        return -1


def _magnet(value, name):
    if not isinstance(value, str) or not HASH.fullmatch(value) or set(value.lower()) == {"0"}:
        return None
    magnet = "magnet:?xt=urn:btih:" + value.lower() + "&dn=" + quote(name, safe="")
    for tracker in TRACKERS:
        magnet += "&tr=" + quote(tracker, safe="")
    return magnet if len(magnet) <= 1024 else None


def _query(what):
    if not isinstance(what, str):
        return None
    value = unquote(what).strip()
    if not 2 <= len(value) <= 96 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value


def _fetch(url):
    try:
        request = Request(url, headers={
            "User-Agent": "BruiserSearch/1.2", "Accept": "application/json",
        })
        with urlopen(request, timeout=TIMEOUT) as response:
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "bitsearch.eu":
                return None
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return None
        data = json.loads(body)
        if not isinstance(data, dict) or data.get("success") is not True:
            return None
        rows = data.get("results")
        return rows if isinstance(rows, list) else None
    except (OSError, ValueError, UnicodeError, TimeoutError):
        return None


class bruiser_bitsearch:
    name = "Bruiser - Bitsearch"
    url = "https://bitsearch.eu"
    # qBittorrent's Nova keys. Bitsearch supports these numeric categories
    # at its API endpoint (https://bitsearch.eu/api).
    supported_categories = {
        "all": "0", "movies": "2", "tv": "3",
        "games": "6", "music": "7", "software": "5",
    }

    def search(self, what, cat="all"):
        if not isinstance(cat, str) or cat not in self.supported_categories:
            return
        query = _query(what)
        if query is None:
            return
        params = {"q": query, "sort": "seeders", "limit": 100}
        if cat != "all":
            params["category"] = int(self.supported_categories[cat])
        if cat == "games":
            params["subCategory"] = 1
        endpoint = self.url + "/api/v1/search?" + urlencode(params)
        entries = _fetch(endpoint)
        if entries is None:
            return
        seen = set()
        for item in entries[:100]:
            if not isinstance(item, dict):
                continue
            name = item.get("title")
            if not isinstance(name, str):
                continue
            name = " ".join(html.unescape(name).split())
            if not 1 <= len(name) <= 160 or any(ord(c) < 32 for c in name):
                continue
            infohash = item.get("infohash")
            link = _magnet(infohash, name)
            if not link or infohash.lower() in seen:
                continue
            seen.add(infohash.lower())
            prettyPrinter({
                "link": link,
                "name": name,
                "size": str(_integer(item.get("size"))) + " B",
                "seeds": str(_integer(item.get("seeders"))),
                "leech": str(_integer(item.get("leechers"))),
                "engine_url": self.url,
                "desc_link": self.url,
                "pub_date": _date(item.get("createdAt")),
            })
