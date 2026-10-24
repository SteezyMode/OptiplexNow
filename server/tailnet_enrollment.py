#!/usr/bin/env python3
"""Opt-in Tailscale-only STAGING for restricted owner credentials.

It deliberately cannot approve requests, pair Wolf, install authorized_keys,
grant Downloads, start Steam or run administrative commands. The host owner
must install/configure this separately; client .deb packaging must not enable it.
"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys

from tailnet_owner_identity import own_tailnet_ipv4, pinned_owner_id, verify_owner_peer
from owner_enrollment import _read_private_config, stage_request
from owner_access import PolicyError

PORT = 18793
ROUTE = "/v1/owner/enrollment/request"
MAX_BODY = 1024
MAX_RESPONSE = 512


def make_handler(owner_user_id, state_dir, *, verify=verify_owner_peer,
                 stage=stage_request):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NOW-Enrollment-Staging"
        sys_version = ""
        protocol_version = "HTTP/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def _send(self, status, data):
            body = json.dumps(data, separators=(",", ":")).encode("ascii")
            if len(body) > MAX_RESPONSE:
                body = b'{"success":false,"status":"unavailable"}'
                status = 500
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != ROUTE:
                self._send(404, {"success": False, "status": "not_found"})
                return
            # Only one Host header; reject cross-origin browser submissions,
            # malformed framing and all client-claimed owner identity headers.
            if (len(self.headers.get_all("Host") or []) != 1
                    or self.headers["Host"] !=
                       f"{self.server.server_address[0]}:{self.server.server_address[1]}"
                    or self.headers.get("Origin") is not None
                    or self.headers.get("Transfer-Encoding") is not None):
                self._send(403, {"success": False, "status": "forbidden"})
                return
            if verify(self.client_address[0], owner_user_id) is None:
                self._send(403, {"success": False, "status": "forbidden"})
                return
            if self.headers.get("Content-Type") != "application/json":
                self._send(415, {"success": False, "status": "invalid_type"})
                return
            size = self.headers.get("Content-Length", "")
            if not size.isascii() or not size.isdecimal() or not 2 <= int(size) <= MAX_BODY:
                self._send(400, {"success": False, "status": "invalid_size"})
                return
            try:
                obj = json.loads(self.rfile.read(int(size)))
                if (not isinstance(obj, dict) or set(obj) != {"version", "public_key"}
                        or type(obj["version"]) is not int or obj["version"] != 1):
                    raise ValueError("Invalid public-key request")
                # The existing staged request policy validates Ed25519
                # and writes ONLY the pending key (mode 0600, TTL, limit).
                result = stage(state_dir, obj["public_key"])
            except (OSError, PolicyError, ValueError, TypeError, UnicodeError):
                self._send(400, {"success": False, "status": "invalid_request"})
                return
            self._send(202, result)

        def do_GET(self):
            self._send(405, {"success": False, "status": "method_not_allowed"})

        def log_message(self, fmt, *args):
            # Never log enrollment codes, remote identities or raw key data.
            pass

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--owner-id-file", required=True,
                        help="Existing installer-pinned private numeric owner ID file")
    args = parser.parse_args(argv)
    try:
        owner_id = pinned_owner_id(args.owner_id_file)
        host_ip = own_tailnet_ipv4()
        config = _read_private_config()
        if not args.serve:
            print("Tailnet owner enrollment staging preflight passed; nothing started.")
            return 0
        # Never bind 0.0.0.0, localhost relay, or a public listening address.
        with HTTPServer((host_ip, PORT), make_handler(
                owner_id, config["state_dir"])) as server:
            server.timeout = 3
            print("Owner staging enabled on the host's Tailscale address only.")
            server.serve_forever(poll_interval=0.2)
        return 0
    except (OSError, ValueError, PermissionError, PolicyError):
        print("Owner staging unavailable; no credentials were granted.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
