#!/usr/bin/env python3
"""Opt-in NOW pairing request broker: tailnet requests, local-only approval.

Separate from the read-only NOW host discovery endpoint. This process has
no administrative network routes, no backend adapter and no persistent grants.
"""
import argparse
import http.server
import json
import re
import socket
import threading

from now_pairing_identity import own_tailnet_ipv4, verify_tailscale_peer
from now_pairing_owner import OwnerControl
from now_pairing_owner_identity import load_pinned_owner, owner_from_local_tailscale
from now_pairing_requests import PairingRequests

PORT = 18792
MAX_BODY = 128
MAX_THREADS = 12
REQUEST_ROUTE = "/v1/pairing/requests"
REQUEST_ROUTE_WITH_ID = re.compile(r"/v1/pairing/requests/([A-Za-z0-9_-]{24,96})\Z")
OWNER_LIST = "/v1/owner/pairing/requests"
OWNER_DECISION = re.compile(
    r"/v1/owner/pairing/requests/([A-Za-z0-9_-]{24,96})/(approve|deny)\Z")
OWNER_CLIENT_HEADER = "X-NOW-Owner-Client"


def make_handler(queue, verify=verify_tailscale_peer, *, owner_user_id=None):
    """All network calls re-verify their actual source IP via WhoIs."""
    class RequestHandler(http.server.BaseHTTPRequestHandler):
        server_version = "NOW-Pairing-Prototype"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def _send(self, status, payload):
            raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def _peer(self):
            # Owner privileges and grants are NEVER available through this
            # transport. Headers, body or claimed account/device IDs ignored.
            if self.headers.get("Origin") is not None:
                return None
            if self.headers.get("Transfer-Encoding") is not None:
                return None
            return verify(self.client_address[0])

        def _owner(self):
            # The trusted installer pins the owner; HTTP clients cannot.
            # Require exact literal tailnet address to resist DNS rebinding.
            if owner_user_id is None:
                return False
            bind_ip, bind_port = self.server.server_address[:2]
            if self.headers.get("Host") != f"{bind_ip}:{bind_port}":
                return False
            if self.headers.get(OWNER_CLIENT_HEADER) != "desktop-v1":
                return False
            peer = self._peer()
            return peer is not None and peer.user_id == owner_user_id

        def do_POST(self):
            decision = OWNER_DECISION.fullmatch(self.path)
            if decision:
                if not self._owner():
                    self._send(403, {"error": "owner_only"})
                    return
                if self.headers.get("Content-Length", "") != "0":
                    self._send(400, {"error": "body_not_allowed"})
                    return
                request_id, action = decision.groups()
                recorded = queue.owner_decide(request_id, approve=action == "approve")
                self._send(200 if recorded else 409,
                           {"decision_recorded": bool(recorded),
                            "moonlight_paired": False})
                return
            if self.path != REQUEST_ROUTE:
                self._send(404, {"error": "not_found"})
                return
            peer = self._peer()
            if peer is None:
                self._send(403, {"error": "forbidden"})
                return
            content_type = self.headers.get("Content-Type", "").strip().lower()
            if content_type != "application/json":
                self._send(415, {"error": "unsupported_media_type"})
                return
            value = self.headers.get("Content-Length", "")
            if not value.isascii() or not value.isdecimal():
                self._send(400, {"error": "invalid_length"})
                return
            size = int(value)
            if size < 2 or size > MAX_BODY:
                self._send(413, {"error": "invalid_length"})
                return
            try:
                raw = self.rfile.read(size)
                body = json.loads(raw)
            except (OSError, ValueError, UnicodeError, socket.timeout):
                self._send(400, {"error": "invalid_request"})
                return
            if not isinstance(body, dict) or set(body) != {"backend"}:
                self._send(400, {"error": "invalid_request"})
                return
            try:
                request_id = queue.request(peer, body["backend"])
            except ValueError:
                self._send(409, {"error": "invalid_or_conflicting_backend"})
                return
            except RuntimeError:
                self._send(429, {"error": "queue_full"})
                return
            self._send(202, {
                "request_id": request_id,
                "owner_status": queue.status_for_peer(peer, request_id),
                "moonlight_paired": False,
            })

        def do_GET(self):
            if self.path == OWNER_LIST:
                if not self._owner():
                    self._send(403, {"error": "owner_only"})
                    return
                rows = [{"request_id": entry.request_id,
                         "device_id": entry.peer.node_id,
                         "account_id": entry.peer.user_id,
                         "backend": entry.backend,
                         "expires_in_seconds": entry.expires_in_seconds}
                        for entry in queue.owner_pending()]
                self._send(200, {"pending": rows, "moonlight_paired": False})
                return
            matched = REQUEST_ROUTE_WITH_ID.fullmatch(self.path)
            if not matched:
                self._send(404, {"error": "not_found"})
                return
            peer = self._peer()
            if peer is None:
                self._send(403, {"error": "forbidden"})
                return
            status = queue.status_for_peer(peer, matched.group(1))
            if status == "unknown":
                self._send(404, {"error": "not_found"})
                return
            self._send(200, {"owner_status": status, "moonlight_paired": False})

        def do_DELETE(self):
            matched = REQUEST_ROUTE_WITH_ID.fullmatch(self.path)
            if not matched:
                self._send(404, {"error": "not_found"})
                return
            peer = self._peer()
            if peer is None:
                self._send(403, {"error": "forbidden"})
                return
            if not queue.cancel_for_peer(peer, matched.group(1)):
                self._send(404, {"error": "not_found"})
                return
            self._send(200, {"cancelled": True, "moonlight_paired": False})

        def do_PUT(self):
            self._send(405, {"error": "method_not_allowed"})

        def log_message(self, fmt, *args):
            # Request URLs can contain opaque request IDs. Log nothing.
            pass

    return RequestHandler


class PairingHTTPServer(http.server.ThreadingHTTPServer):
    """Cap concurrent requests, so a tailnet peer cannot spawn many threads."""
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, bind, handler):
        self._capacity = threading.BoundedSemaphore(MAX_THREADS)
        super().__init__(bind, handler)

    def process_request(self, request, client_address):
        if not self._capacity.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._capacity.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._capacity.release()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Experimental NOW pairing broker")
    parser.add_argument("--serve", action="store_true",
                        help="Explicitly start tailnet requests and local owner socket")
    owner_config = parser.add_mutually_exclusive_group()
    owner_config.add_argument("--owner-id-file",
                        help="Trusted installer-registered mode-0600 Tailscale owner account ID")
    owner_config.add_argument("--owner-from-local-tailnet", action="store_true",
                        help="At explicit server activation, identify owner as the enrolled Tailscale server account")
    parser.add_argument("--socket-dir",
                        help="Existing mode-0700 directory owned by this Unix user")
    args = parser.parse_args(argv)
    if not args.serve and args.socket_dir is not None:
        parser.error("--socket-dir is only used with --serve")
    if args.serve and not args.socket_dir:
        parser.error("--serve requires --socket-dir")
    if (args.owner_id_file is not None or args.owner_from_local_tailnet) and not args.serve:
        parser.error("Owner binding requires --serve")
    try:
        address = own_tailnet_ipv4()
        if not args.serve:
            print("NOW pairing broker preflight available on local Tailscale address.")
            print("No listeners opened, credentials created or services changed.")
            return 0

        # Remote owner operations are disabled unless server installation
        # has pinned the verified owner account in a private local file.
        owner_user_id = (load_pinned_owner(args.owner_id_file) if args.owner_id_file
                         else owner_from_local_tailscale() if args.owner_from_local_tailnet
                         else None)
        queue = PairingRequests()
        # Both sockets live in THIS process and use precisely the same queue.
        with PairingHTTPServer((address, PORT), make_handler(queue, owner_user_id=owner_user_id)) as server:
            with OwnerControl(args.socket_dir, queue) as owner:
                worker = threading.Thread(target=owner.serve_forever,
                                          kwargs={"poll_interval": 0.2}, daemon=True)
                worker.start()
                try:
                    print("NOW pairing request broker active on Tailscale only.")
                    print("Owner approval uses the private local Unix socket.")
                    server.serve_forever(poll_interval=0.2)
                finally:
                    owner.shutdown()
                    worker.join(timeout=3)
        return 0
    except (OSError, ValueError, RuntimeError, PermissionError):
        # Avoid outputting host paths, Tailscale data or raw error payloads.
        print("NOW pairing broker unavailable: check Tailscale, owner directory and port.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
