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
MAX_STDIN = 8192
MAX_TEXT = 512


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
    return {"apiKey": key, **({"u": username} if username else {})}


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
    elif operation == "search":
        payload = result.get("results") or {}
        found = [(kind, x) for kind in ("artist", "album", "song")
                 for x in items(payload.get(kind))][:1000]
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
        fields = (kind, identifier[:512], title[:2048], artist[:1024])
        lines.append("\t".join(base64.b64encode(x.encode("utf-8")).decode("ascii")
                               for x in fields))
    return "\n".join(lines) + ("\n" if lines else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bruiser optional OpenSubsonic transport")
    parser.add_argument("base_url", help="Configured music-server URL; no credentials")
    parser.add_argument("operation", choices=("ping", "home", "albums", "recent", "new", "liked", "artists", "search", "album", "artist", "playlists", "playlist", "stream"))
    parser.add_argument("value", nargs="?")
    parser.add_argument("--format", choices=("json", "rows"), default="json")
    parser.add_argument("--auth-format", choices=("json", "form"), default="json")
    args = parser.parse_args(argv)
    try:
        auth = _auth_from_stdin(args.auth_format)
        # Authenticate and validate before making any outbound request.
        endpoint_for(args.base_url, "ping")
        if args.operation in ("album", "artist", "playlist", "stream", "search") and not args.value:
            raise MusicTransportError("This music operation needs a selection.")
        if args.operation == "stream":
            stream(args.base_url, auth, args.value)
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
            data = query(args.base_url, "getAlbumList2", auth,
                         {"type": sort, "size": "100", "offset": "0"})
            result = {"albums": data.get("albumList2", {}).get("album", [])}
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
