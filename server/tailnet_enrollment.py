#!/usr/bin/env python3
"""Opt-in Tailscale-only STAGING for restricted owner credentials.

By default it STAGES public keys only. Two separate opt-in features can
(1) pair an authenticated owner's own Tailscale source IP to Wolf using
the fixed PIN protocol, without arbitrary Docker access or generic SSH; and
(2) approve a restricted Games/Downloads key after owner review of the one
active paired Wolf UI session. No installation or enablement by a client .deb.
"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys

from tailnet_owner_identity import own_tailnet_ipv4, pinned_owner_id, verify_owner_peer
from owner_enrollment import _read_private_config, stage_request
from owner_access import PolicyError
from tailnet_wolf_review import single_active_wolf_ui, approve_reviewed_owner_request
from wolf_docker_adapter import WolfDockerAPI
from tailnet_wolf_pair import (pending_owner_wolf, pair_owner_wolf,
                              host_wolf_pair_api)

PORT = 18793
ROUTE = "/v1/owner/enrollment/request"
REVIEW_ROUTE = "/v1/owner/enrollment/wolf-candidate"
APPROVE_ROUTE = "/v1/owner/enrollment/approve"
PAIR_PENDING_ROUTE = "/v1/owner/wolf-pair/pending"
PAIR_APPROVE_ROUTE = "/v1/owner/wolf-pair/approve"
MAX_BODY = 1024
MAX_RESPONSE = 512


def make_handler(owner_user_id, state_dir, *, verify=verify_owner_peer,
                 stage=stage_request, wolf_factory=WolfDockerAPI,
                 approve=approve_reviewed_owner_request,
                 remote_approve_enabled=False, owner_pair_enabled=False,
                 pair_api=host_wolf_pair_api):
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

        def _verified_owner(self):
            if (len(self.headers.get_all("Host") or []) != 1
                    or self.headers["Host"] !=
                       f"{self.server.server_address[0]}:{self.server.server_address[1]}"
                    or self.headers.get("Origin") is not None
                    or self.headers.get("Transfer-Encoding") is not None):
                return False
            return verify(self.client_address[0], owner_user_id) is not None

        def _read_json(self, max_body):
            if self.headers.get("Content-Type") != "application/json":
                raise ValueError("Invalid type")
            size = self.headers.get("Content-Length", "")
            if not size.isascii() or not size.isdecimal():
                raise ValueError("Invalid length")
            length = int(size)
            if length < 2 or length > max_body:
                raise ValueError("Invalid request size")
            return json.loads(self.rfile.read(length))

        def do_POST(self):
            if self.path not in (ROUTE, APPROVE_ROUTE, PAIR_APPROVE_ROUTE):
                self._send(404, {"success": False, "status": "not_found"})
                return
            if not self._verified_owner():
                self._send(403, {"success": False, "status": "forbidden"})
                return
            if ((self.path == APPROVE_ROUTE and not remote_approve_enabled)
                    or (self.path == PAIR_APPROVE_ROUTE and not owner_pair_enabled)):
                self._send(403, {"success": False, "status": "disabled"})
                return
            try:
                obj = self._read_json(MAX_BODY)
                if self.path == PAIR_APPROVE_ROUTE:
                    result = pair_owner_wolf(self.client_address[0], obj,
                                             call_api=pair_api)
                    self._send(200, result)
                    return
                if self.path == ROUTE:
                    if (not isinstance(obj, dict)
                            or set(obj) != {"version", "public_key"}
                            or type(obj["version"]) is not int
                            or obj["version"] != 1):
                        raise ValueError("Invalid public-key request")
                    result = stage(state_dir, obj["public_key"])
                    self._send(202, result)
                    return
                # A separately authenticated owner must deliberately choose
                # and confirm the Wolf ID observed in the current stream.
                # The host independently re-reads paired/active Wolf state.
                if (not isinstance(obj, dict)
                        or set(obj) != {"request_id", "code",
                                       "wolf_client_id", "confirmed"}
                        or obj["confirmed"] is not True
                        or any(not isinstance(obj[key], str)
                               for key in ("request_id", "code", "wolf_client_id"))):
                    raise ValueError("Explicit reviewed approval required")
                result = approve(
                    state_dir, obj["request_id"], obj["code"],
                    obj["wolf_client_id"], wolf_api=wolf_factory(),
                    approval=True)
                if (not isinstance(result, dict)
                        or result.get("success") is not True
                        or result.get("status") != "approved"):
                    raise PolicyError("Host approval was not committed")
                # Avoid returning Wolf secrets or the host file paths.
                self._send(200, {"success": True, "status": "approved"})
            except (OSError, PolicyError, ValueError, TypeError, UnicodeError,
                    KeyError, RuntimeError):
                self._send(400, {"success": False, "status": "denied"})

        def do_GET(self):
            if self.path not in (REVIEW_ROUTE, PAIR_PENDING_ROUTE):
                self._send(404, {"success": False, "status": "not_found"})
                return
            if not self._verified_owner() or (
                    self.path == REVIEW_ROUTE and not remote_approve_enabled) or (
                    self.path == PAIR_PENDING_ROUTE and not owner_pair_enabled):
                self._send(403, {"success": False, "status": "forbidden"})
                return
            if self.path == PAIR_PENDING_ROUTE:
                try:
                    result = pending_owner_wolf(self.client_address[0],
                                                call_api=pair_api)
                    self._send(200, result)
                except (OSError, PolicyError, ValueError, TypeError, RuntimeError):
                    self._send(409, {"success": False, "status": "unavailable"})
                return
            try:
                candidate = single_active_wolf_ui(wolf_factory())
            except (OSError, PolicyError, ValueError, TypeError, RuntimeError):
                self._send(409, {"success": False, "status": "no_unique_wolf_ui"})
                return
            self._send(200, {"success": True, "wolf_client_id": candidate})

        def log_message(self, fmt, *args):
            # Never log enrollment codes, remote identities or raw key data.
            pass

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--owner-id-file", required=True,
                        help="Existing installer-pinned private numeric owner ID file")
    parser.add_argument("--enable-remote-approval", action="store_true",
                        help="EXPERIMENTAL: allow pinned owner to confirm one active Wolf UI device remotely")
    parser.add_argument("--enable-owner-wolf-pairing", action="store_true",
                        help="EXPERIMENTAL: allow only pinned owner to pair own Tailscale node to Wolf")
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
                owner_id, config["state_dir"],
                remote_approve_enabled=args.enable_remote_approval,
                owner_pair_enabled=args.enable_owner_wolf_pairing)) as server:
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
