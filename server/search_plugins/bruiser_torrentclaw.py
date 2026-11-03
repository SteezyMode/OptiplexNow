# VERSION: 1.0
# AUTHORS: Bruiser contributors
"""Public, no-key TorrentClaw JSON search; one API request, no account."""
from datetime import datetime, timezone
from urllib.parse import urlencode
from novaprinter import prettyPrinter
from engines._bruiser_source import as_int, build_magnet, read_json, search_terms, validated_title


def uploaded_epoch(value):
    if not isinstance(value, str) or len(value) > 40:
        return -1
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return -1
        stamp = int(dt.astimezone(timezone.utc).timestamp())
        return stamp if 0 <= stamp <= 253402300799 else -1
    except (OverflowError, ValueError, OSError):
        return -1


class bruiser_torrentclaw:
    name = "Bruiser - TorrentClaw"
    url = "https://torrentclaw.com"
    supported_categories = {"all": ""}

    def search(self, what, cat="all"):
        query = search_terms(what)
        if query is None or cat not in self.supported_categories:
            return
        address = self.url + "/api/v1/search?" + urlencode({"q": query, "limit": 50})
        body = read_json(address)
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            return
        count = 0
        for group in body["results"][:50]:
            if not isinstance(group, dict) or not isinstance(group.get("torrents"), list):
                continue
            for item in group["torrents"][:50]:
                if not isinstance(item, dict):
                    continue
                title = validated_title(item.get("rawTitle") or group.get("title"))
                magnet = build_magnet(item.get("infoHash"), title)
                if not magnet:
                    continue
                prettyPrinter({
                    "link": magnet,
                    "name": title,
                    "size": str(as_int(item.get("sizeBytes"))) + " B",
                    "seeds": str(as_int(item.get("seeders"))),
                    "leech": str(as_int(item.get("leechers"))),
                    "engine_url": self.url,
                    "desc_link": self.url,
                    "pub_date": uploaded_epoch(item.get("uploadedAt")),
                })
                count += 1
                if count >= 100:
                    return
