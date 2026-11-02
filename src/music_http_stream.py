"""Per-playback, loopback-only HTTP byte-range gateway for DroppedNeedle.

The audio decoder sees only a short-lived 127.0.0.1 URL with an unguessable
path; it NEVER sees the upstream server address or user app-password.
GET/HEAD are the only supported methods. Every request is forwarded as an
authenticated OpenSubsonic POST, optionally with a validated Range header.
No files or media bytes are stored persistently. No arbitrary paths, hosts,
redirects, cookies or extra headers are accepted from mpv.
"""
from __future__ import annotations

import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from music_subsonic import MusicTransportError, _post

RANGE_RE = re.compile(r"bytes=(0|[1-9][0-9]{0,17})-([0-9]{0,18})?\Z")
CONTENT_RANGE_RE = re.compile(r"bytes \d+-\d+/(\d+)\Z")
MIME = re.compile(r"^(audio/[a-z0-9.+-]+|application/(?:ogg|octet-stream|x-flac))$")
MAX_AUDIO_HEADER = 128
MAX_TRANSFER_CHUNK = 128 * 1024


class GatewayError(Exception):
    pass


class _LoopbackServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 8


class MusicStreamGateway:
    """Launch one private short-lived stream. Owner must call close()."""

    def __init__(self, base_url: str, key: str, track_id: str):
        # Do not preserve a music password in a URL, command line or log.
        self.base_url = base_url
        self.auth = {"apiKey": key}
        self.track_id = track_id
        self.nonce = secrets.token_urlsafe(24)
        self.path = "/stream/" + self.nonce
        self._http = None
        self._thread = None

    def start(self) -> str:
        if self._http is not None:
            raise GatewayError("Music gateway is already running.")
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"
            server_version = "BruiserLocalAudio"
            sys_version = ""

            def log_message(self, fmt, *args):
                # URLs can contain a short-lived local path; never log them.
                pass

            def do_GET(self):
                self._handle(False)

            def do_HEAD(self):
                self._handle(True)

            def _handle(self, head: bool):
                if self.path != gateway.path or self.client_address[0] != "127.0.0.1":
                    self.send_error(404)
                    return
                supplied = self.headers.get("Range")
                if supplied and (len(supplied) > 64 or not RANGE_RE.fullmatch(supplied)):
                    self.send_error(416)
                    return
                if head:
                    # The player may ask for a file size before issuing
                    # GET Range. A one-byte upstream response yields total.
                    supplied = "bytes=0-0"
                try:
                    with _post(gateway.base_url, "stream", gateway.auth,
                               {"id": gateway.track_id, "format": "raw"},
                               range_header=supplied) as response:
                        typ = response.headers.get("Content-Type", "").split(";",1)[0].strip().lower()
                        if len(typ) > MAX_AUDIO_HEADER or not MIME.fullmatch(typ):
                            self.send_error(502)
                            return
                        received_range = response.headers.get("Content-Range", "")
                        total = response.headers.get("Content-Length")
                        if head:
                            match = CONTENT_RANGE_RE.fullmatch(received_range)
                            if match is not None:
                                total = match.group(1)
                            elif not (total and total.isascii() and total.isdecimal()):
                                self.send_error(502)
                                return
                        if not head and supplied and response.status != 206:
                            # A server ignoring Range cannot satisfy a seek.
                            self.send_error(502)
                            return
                        if total and (not total.isascii() or not total.isdecimal()
                                      or len(total) > 19):
                            self.send_error(502)
                            return
                        self.send_response(200 if head else response.status)
                        self.send_header("Content-Type", typ)
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Cache-Control", "no-store")
                        if total:
                            self.send_header("Content-Length", total)
                        if not head and received_range:
                            self.send_header("Content-Range", received_range)
                        self.end_headers()
                        if head:
                            return
                        while True:
                            block = response.read(MAX_TRANSFER_CHUNK)
                            if not block:
                                break
                            self.wfile.write(block)
                except (MusicTransportError, OSError, HTTPError):
                    try:
                        self.send_error(502)
                    except (OSError, BrokenPipeError):
                        pass
                except (BrokenPipeError, ConnectionResetError):
                    # mpv moving its playhead can abandon an old range. Fine.
                    pass

        try:
            self._http = _LoopbackServer(("127.0.0.1", 0), Handler)
        except OSError as exc:
            raise GatewayError("Cannot open private music loopback.") from exc
        self._thread = threading.Thread(
            target=self._http.serve_forever, name="bruiser-local-audio", daemon=True)
        self._thread.start()
        return "http://127.0.0.1:%d%s" % (self._http.server_port, self.path)

    def close(self) -> None:
        if self._http is not None:
            self._http.shutdown()
            self._http.server_close()
            self._http = None
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        self.auth.clear()

