#!/usr/bin/env python3
"""Read-only OpenSubsonic client/stream transport for optional Bruiser Music.

Authentication is provided only via a bounded JSON object on stdin, never argv,
environment variables, URL query strings or command-line log output. The
caller must provide a dedicated, revocable *user* app password (not slskd admin
credentials). All upstream requests are POSTs. No automatic redirects or retries.
This is a tested transport foundation; it does not yet install a playback UI.
"""
from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import socket
import ssl
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, parse_qs, urlsplit, urlunsplit
from urllib.request import build_opener, HTTPRedirectHandler, HTTPSHandler, HTTPHandler, ProxyHandler, Request

CLIENT = "bruiser-music"
VERSION = "1.16.1"
MAX_REPLY = 8 * 1024 * 1024
MAX_COVER = 3 * 1024 * 1024
MAX_CATALOG = 1024 * 1024
MAX_STDIN = 8192
MAX_TEXT = 512
ALBUM_PAGE_SIZE = 200


class MusicTransportError(Exception):
    """Safe-to-display failure with no transport secrets or upstream HTML."""


class DenyRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MusicTransportError("Music server redirected the request; refusing to forward credentials.")


def endpoint_for(base_url: str, method: str) -> str:
    if not isinstance(base_url, str) or len(base_url) > 1024:
        raise MusicTransportError("Invalid music-server URL.")
    try:
        parts = urlsplit(base_url)
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise MusicTransportError("Invalid music-server URL.") from exc
    if not hostname or parts.scheme not in ("http", "https") or not parts.netloc:
        raise MusicTransportError("Music-server URL must use HTTP or HTTPS.")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise MusicTransportError("Music-server URL must not contain credentials or query parameters.")
    if any(ord(ch) < 33 for ch in base_url) or port == 0:
        raise MusicTransportError("Invalid music-server URL.")
    if parts.scheme == "http":
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError as exc:
            raise MusicTransportError("HTTP requires a numeric private/Tailnet host; use HTTPS for DNS names.") from exc
        if not (address.is_private or address.is_loopback or
                (address.version == 4 and address in ipaddress.ip_network("100.64.0.0/10"))):
            raise MusicTransportError("HTTP access is limited to private or Tailnet addresses.")
    if not method or not method.isascii() or not method.isalnum():
        raise MusicTransportError("Invalid music-server operation.")
    # Base paths are supported for reverse proxies; no client-supplied method
    # can inject a slash or redirect off the configured service.
    base = parts.path.rstrip("/")
    if any(segment in (".", "..") for segment in base.split("/")):
        raise MusicTransportError("Invalid music-server URL path.")
    return urlunsplit((parts.scheme, parts.netloc, base + "/subsonic/rest/" + method, "", ""))


def _bounded_text(value: object, name: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise MusicTransportError("Invalid " + name + ".")
    if any(ord(c) < 32 for c in value):
        raise MusicTransportError("Invalid " + name + ".")
    return value


def _auth_from_stdin(fmt: str = "json") -> dict[str, str]:
    # Credentials intentionally stay session-only; there is no write to disk.
    raw = sys.stdin.buffer.read(MAX_STDIN + 1)
    if len(raw) > MAX_STDIN:
        raise MusicTransportError("Music credentials were too large.")
    try:
        if fmt == "form":
            values = parse_qs(raw.decode("utf-8"), strict_parsing=True,
                              keep_blank_values=True, max_num_fields=3)
            if any(len(v) != 1 for v in values.values()) or set(values) - {"api_key", "username"}:
                raise ValueError("unexpected fields")
            auth = {k: v[0] for k, v in values.items()}
        else:
            auth = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise MusicTransportError("Missing or invalid music credentials.") from exc
    if not isinstance(auth, dict):
        raise MusicTransportError("Invalid music credentials.")
    key = _bounded_text(auth.get("api_key"), "app password", 1024)
    # The upstream accepts dedicated OpenSubsonic app passwords via apiKey.
    username = auth.get("username", "")
    if username:
        username = _bounded_text(username, "username", 128)
    # DroppedNeedle v2.15.0 rejects apiKey together with u (Subsonic 43).
    # Keep the optional username in the local vault for display only.
    return {"apiKey": key}


def _post(base: str, method: str, auth: dict[str, str],
          parameters: dict[str, str] | None = None):
    url = endpoint_for(base, method)
    fields = {"v": VERSION, "c": CLIENT, "f": "json"}
    fields.update(auth)
    if parameters:
        fields.update(parameters)
    payload = urlencode(fields).encode("utf-8")
    request = Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json, audio/*;q=0.8, */*;q=0.1"}
    )
    opener = build_opener(ProxyHandler({}), DenyRedirects(), HTTPHandler(), HTTPSHandler(context=ssl.create_default_context()))
    try:
        return opener.open(request, timeout=20)
    except MusicTransportError:
        raise
    except HTTPError as exc:
        raise MusicTransportError("Music server refused the request (HTTP %d)." % exc.code) from None
    except (URLError, OSError, socket.timeout) as exc:
        raise MusicTransportError("Could not contact the music server.") from None


def query(base: str, method: str, auth: dict[str, str],
          parameters: dict[str, str] | None = None) -> dict[str, Any]:
    with _post(base, method, auth, parameters) as response:
        data = response.read(MAX_REPLY + 1)
    if len(data) > MAX_REPLY:
        raise MusicTransportError("Music-server response was too large.")
    try:
        result = json.loads(data)
    except (UnicodeError, ValueError) as exc:
        raise MusicTransportError("Music server returned invalid JSON.") from exc
    if not isinstance(result, dict) or not isinstance(result.get("subsonic-response"), dict):
        raise MusicTransportError("Music server returned an unexpected response.")
    body = result["subsonic-response"]
    if body.get("status") != "ok":
        error = body.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        # Do not surface arbitrary upstream error strings, which can expose
        # internal paths or credentials.
        if code in (40, 41, 42, 43, 44):
            raise MusicTransportError("Music authorization failed; check the app password.")
        raise MusicTransportError("Music service refused the operation.")
    return body


def catalog_search(base: str, text: str) -> dict[str, Any]:
    """Read DroppedNeedle's existing artist/album search results.

    Discovery is NOT another download service. This route in DroppedNeedle
    v2.15.0 does not accept OpenSubsonic app keys, and the app key is NEVER
    attached here. Album requests require separately authorized REST access.
    """
    text = _bounded_text(text, "music discovery query", 200)
    # Reuse the strict network/address/path checks from the authenticated
    # transport, but DO NOT attach streaming app credentials to the REST API.
    validated = urlsplit(endpoint_for(base, "ping"))
    suffix = "/subsonic/rest/ping"
    if not validated.path.endswith(suffix):
        raise MusicTransportError("Invalid music discovery base path.")
    prefix = validated.path[:-len(suffix)]
    path = prefix + "/api/v1/search"
    uri = urlunsplit((
        validated.scheme, validated.netloc, path,
        urlencode({"q": text, "limit_artists": "10", "limit_albums": "25"}), ""
    ))
    req = Request(uri, method="GET", headers={"Accept": "application/json"})
    opener = build_opener(ProxyHandler({}), DenyRedirects(), HTTPHandler(),
                          HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(req, timeout=12) as response:
            data = response.read(MAX_CATALOG + 1)
    except MusicTransportError:
        raise
    except HTTPError:
        raise MusicTransportError("Music discovery is not available on this server.") from None
    except (URLError, OSError, socket.timeout):
        raise MusicTransportError("Music discovery is temporarily unavailable.") from None
    if len(data) > MAX_CATALOG:
        raise MusicTransportError("Music discovery results exceeded the size limit.")
    try:
        result = json.loads(data)
    except (UnicodeError, ValueError) as exc:
        raise MusicTransportError("Music discovery returned invalid results.") from exc
    if not isinstance(result, dict):
        raise MusicTransportError("Music discovery returned unexpected results.")
    return result


def stream(base: str, auth: dict[str, str], song_id: str) -> None:
    song_id = _bounded_text(song_id, "track ID")
    with _post(base, "stream", auth, {"id": song_id, "format": "raw"}) as response:
        # Fail closed if an upstream returns JSON containing an auth failure
        # rather than audio bytes (the compatibility API may reply with HTTP 200).
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" in content_type or "xml" in content_type or "html" in content_type:
            raise MusicTransportError("Music stream was unavailable or authorization failed.")
        while True:
            chunk = response.read(128 * 1024)
            if not chunk:
                break
            try:
                sys.stdout.buffer.write(chunk)
            except BrokenPipeError:
                return
    try:
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        return


def cover_art(base: str, auth: dict[str, str], cover_id: str) -> None:
    """Fetch a small authenticated raster cover by POST without exposing a URL.

    Do not accept SVG/HTML, redirect responses or unbounded image payloads.
    Missing artwork fails harmlessly; the native UI uses a local placeholder.
    """
    cover_id = _bounded_text(cover_id, "cover art ID")
    with _post(base, "getCoverArt", auth, {"id": cover_id, "size": "220"}) as response:
        mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            raise MusicTransportError("Music server returned no supported cover art.")
        data = response.read(MAX_COVER + 1)
        if not data or len(data) > MAX_COVER:
            raise MusicTransportError("Music cover image is empty or too large.")
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def _rows(operation: str, result: dict[str, Any]) -> str:
    """Base64-tabbed, bounded GTK transport; music titles never become delimiters."""
    def items(source: object) -> list[dict[str, Any]]:
        return [x for x in source if isinstance(x, dict)][:1000] if isinstance(source, list) else []

    if operation in ("albums", "home", "recent", "new"):
        found = [("album", x) for x in items(result.get("albums"))]
    elif operation == "liked":
        saved = result.get("starred") or {}
        found = [(kind, item) for kind in ("album", "song", "artist")
                 for item in items(saved.get(kind))][:1000]
    elif operation == "artists":
        found = [("artist", artist) for index in items(result.get("indexes"))
                 for artist in items(index.get("artist"))][:1000]
    elif operation == "playlists":
        found = [("playlist", x) for x in items(result.get("playlists"))]
    elif operation in ("album", "playlist"):
        key = "song" if operation == "album" else "entry"
        found = [("song", x) for x in items(result.get(operation, {}).get(key))]
    elif operation == "artist":
        found = [("album", x) for x in items(result.get("artist", {}).get("album"))]
    elif operation in ("search", "catalog"):
        payload = result.get("results") or {}
        found = [(kind, x) for kind in ("artist", "album", "song")
                 for x in items(payload.get(kind))][:1000]
        # Existing DroppedNeedle search is used verbatim for missing music.
        # Exclude already-owned albums; they are available above via search3.
        catalog = result.get("catalog") or {}
        found += [("catalog_" + kind, {
            "id": item.get("musicbrainz_id", ""),
            "title": item.get("title", ""),
            "artist": (
                (item.get("artist") or "") +
                (" · Requested" if item.get("requested") else " · Not in library")
            ),
        }) for kind in ("artist", "album")
            for item in items(catalog.get(kind + "s"))
            if item.get("in_library") is not True][:1000]
    else:
        found = []
    lines = []
    for kind, item in found:
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier:
            continue
        title = item.get("title") or item.get("name") or "Untitled"
        artist = item.get("artist") or item.get("artistName") or ""
        if not isinstance(title, str):
            title = "Untitled"
        if not isinstance(artist, str):
            artist = ""
        cover_id = item.get("coverArt") or item.get("id") or ""
        if not isinstance(cover_id, str):
            cover_id = ""
        fields = (kind, identifier[:512], title[:2048], artist[:1024], cover_id[:512])
        lines.append("\t".join(base64.b64encode(x.encode("utf-8")).decode("ascii")
                               for x in fields))
    return "\n".join(lines) + ("\n" if lines else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bruiser optional OpenSubsonic transport")
    parser.add_argument("base_url", help="Configured music-server URL; no credentials")
    parser.add_argument("operation", choices=("ping", "home", "albums", "recent", "new", "liked", "artists", "search", "album", "artist", "playlists", "playlist", "stream", "art", "catalog"))
    parser.add_argument("value", nargs="?")
    parser.add_argument("--format", choices=("json", "rows"), default="json")
    parser.add_argument("--auth-format", choices=("json", "form"), default="json")
    args = parser.parse_args(argv)
    try:
        # DroppedNeedle's read-only public catalog route is separate from its
        # per-user library playback API. Do not request, store or forward a
        # playback key for a basic search. The configured private host is
        # validated by catalog_search before the outbound request.
        if args.operation == "catalog":
            result = {"catalog": catalog_search(
                args.base_url, _bounded_text(args.value, "search query", 200))}
            if args.format == "rows":
                sys.stdout.write(_rows("catalog", result))
            else:
                json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"))
                sys.stdout.write("\n")
            return 0
        auth = _auth_from_stdin(args.auth_format)
        # Authenticate and validate before making any outbound request.
        endpoint_for(args.base_url, "ping")
        if args.operation in ("album", "artist", "playlist", "stream", "art", "search") and not args.value:
            raise MusicTransportError("This music operation needs a selection.")
        if args.operation == "stream":
            stream(args.base_url, auth, args.value)
            return 0
        if args.operation == "art":
            cover_art(args.base_url, auth, args.value)
            return 0
        if args.operation == "ping":
            data = query(args.base_url, "ping", auth)
            result = {"ok": True, "version": data.get("version", "")}
        elif args.operation in ("home", "albums", "recent", "new"):
            sort = {
                "home": "recent",
                "albums": "alphabeticalByName",
                "recent": "recent",
                "new": "newest",
            }[args.operation]
            offset = 0
            if args.operation == "albums" and args.value is not None:
                if not args.value.isascii() or not args.value.isdecimal():
                    raise MusicTransportError("Invalid album page offset.")
                offset = int(args.value)
                if offset > 1_000_000 or offset % ALBUM_PAGE_SIZE:
                    raise MusicTransportError("Invalid album page offset.")
            data = query(args.base_url, "getAlbumList2", auth,
                         {"type": sort,
                          "size": str(ALBUM_PAGE_SIZE if args.operation == "albums" else 100),
                          "offset": str(offset)})
            albums = data.get("albumList2", {}).get("album", [])
            # A freshly installed player has no history yet. Populate Home
            # with real library additions, not a fabricated recommendation.
            if args.operation == "home" and not albums:
                data = query(args.base_url, "getAlbumList2", auth,
                             {"type": "newest", "size": "100", "offset": "0"})
                albums = data.get("albumList2", {}).get("album", [])
            result = {"albums": albums}
        elif args.operation == "liked":
            data = query(args.base_url, "getStarred2", auth)
            result = {"starred": data.get("starred2", {})}
        elif args.operation == "artists":
            data = query(args.base_url, "getArtists", auth)
            result = {"indexes": data.get("artists", {}).get("index", [])}
        elif args.operation == "search":
            value = _bounded_text(args.value, "search query", 200)
            data = query(args.base_url, "search3", auth, {"query": value})
            result = {"results": data.get("searchResult3", {})}
            try:
                result["catalog"] = catalog_search(args.base_url, value)
            except MusicTransportError:
                # An unavailable acquisition catalog must never break access
                # to owned songs. Do not use the player app key as REST auth.
                result["catalog"] = {}
        elif args.operation == "album":
            data = query(args.base_url, "getAlbum", auth, {"id": _bounded_text(args.value, "album ID")})
            result = {"album": data.get("album", {})}
        elif args.operation == "playlists":
            data = query(args.base_url, "getPlaylists", auth)
            result = {"playlists": data.get("playlists", {}).get("playlist", [])}
        elif args.operation == "artist":
            data = query(args.base_url, "getArtist", auth, {"id": _bounded_text(args.value, "artist ID")})
            result = {"artist": data.get("artist", {})}
        else:
            data = query(args.base_url, "getPlaylist", auth, {"id": _bounded_text(args.value, "playlist ID")})
            result = {"playlist": data.get("playlist", {})}
        if args.format == "rows":
            sys.stdout.write(_rows(args.operation, result))
        else:
            json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"))
            sys.stdout.write("\n")
        return 0
    except MusicTransportError as exc:
        # Deliberately no URL, request object, traceback, or raw remote error.
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
