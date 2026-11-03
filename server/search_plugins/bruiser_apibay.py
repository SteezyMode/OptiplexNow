# VERSION: 1.2
# AUTHORS: Bruiser contributors
"""Fast, bounded API Bay search plugin for qBittorrent Nova.

One JSON request per search. No external dependencies, API keys, torrent
queue operations, local configuration writes, or secondary page requests.
"""
import json
import re
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen
from novaprinter import prettyPrinter

TIMEOUT_SECONDS = 4
MAX_BODY_BYTES = 1_048_576
HASH = re.compile(r"[0-9a-fA-F]{40}\Z")
TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
)


def _query(what):
    if not isinstance(what, str):
        return None
    # qBittorrent Nova already URL-encodes the search terms.
    value = unquote(what).strip()
    if not 2 <= len(value) <= 96 or any(ord(char) < 32 or ord(char) == 127
                                      for char in value):
        return None
    return value


def _int(value):
    if isinstance(value, bool):
        return -1
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return -1
    return number if 0 <= number <= 2**63 - 1 else -1


def _magnet(infohash, title):
    if not isinstance(infohash, str) or not HASH.fullmatch(infohash):
        return None
    link = "magnet:?xt=urn:btih:" + infohash.lower() + "&dn=" + quote(title, safe="")
    for tracker in TRACKERS:
        link += "&tr=" + quote(tracker, safe="")
    return link if len(link) <= 1024 else None


def _fetch(url):
    try:
        request = Request(url, headers={
            "User-Agent": "BruiserSearch/1.2",
            "Accept": "application/json",
        })
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            # Never accept an HTTP downgrade or redirect to an unrelated host.
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "apibay.org":
                return None
            content = response.read(MAX_BODY_BYTES + 1)
        if len(content) > MAX_BODY_BYTES:
            return None
        value = json.loads(content)
        return value if isinstance(value, list) else None
    except (OSError, UnicodeError, ValueError, TimeoutError):
        return None


class bruiser_apibay:
    name = "Bruiser - API Bay"
    url = "https://apibay.org"
    # Nova category keys map to API Bay category IDs; filtering happens
    # before the provider's 100-result response limit.
    supported_categories = {
        "all": "0",
        "movies": "201,202,207,209,210,211",
        "tv": "205,208,212",
        "games": "401",
        "music": "101,104",
        "software": "301,302,303,304,305,306,399",
    }

    def search(self, what, cat="all"):
        query = _query(what)
        if query is None or cat not in self.supported_categories:
            return

        endpoint = self.url + "/q.php?" + urlencode({"q": query, "cat": self.supported_categories[cat]})
        rows = _fetch(endpoint)
        if rows is None:
            return

        for item in rows[:100]:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str):
                continue
            name = " ".join(name.split())
            if not 1 <= len(name) <= 160 or any(ord(c) < 32 for c in name):
                continue
            magnet = _magnet(item.get("info_hash"), name)
            if magnet is None:
                continue
            prettyPrinter({
                "link": magnet,
                "name": name,
                "size": str(_int(item.get("size"))) + " B",
                "seeds": str(_int(item.get("seeders"))),
                "leech": str(_int(item.get("leechers"))),
                "engine_url": self.url,
                "desc_link": self.url,
                "pub_date": _int(item.get("added")),
            })
