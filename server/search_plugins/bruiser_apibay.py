# VERSION: 1.0
# AUTHORS: Bruiser contributors
"""API Bay public JSON search; one request and no extra page crawling."""
from urllib.parse import urlencode
from novaprinter import prettyPrinter
from engines._bruiser_source import as_int, build_magnet, read_json, search_terms, validated_title


class bruiser_apibay:
    name = "Bruiser - API Bay"
    url = "https://apibay.org"
    supported_categories = {"all": "0"}

    def search(self, what, cat="all"):
        query = search_terms(what)
        if query is None or cat not in self.supported_categories:
            return
        address = self.url + "/q.php?" + urlencode({"q": query, "cat": "0"})
        entries = read_json(address)
        if not isinstance(entries, list):
            return
        for item in entries[:100]:
            if not isinstance(item, dict):
                continue
            name = validated_title(item.get("name"))
            magnet = build_magnet(item.get("info_hash"), name)
            if not magnet:
                continue
            published = as_int(item.get("added"))
            prettyPrinter({
                "link": magnet,
                "name": name,
                "size": str(as_int(item.get("size"))) + " B",
                "seeds": str(as_int(item.get("seeders"))),
                "leech": str(as_int(item.get("leechers"))),
                "engine_url": self.url,
                "desc_link": self.url,
                "pub_date": published,
            })
