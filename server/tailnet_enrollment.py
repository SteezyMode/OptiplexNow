#!/usr/bin/env python3
"""Opt-in Tailscale-only STAGING for restricted owner credentials.

By default it STAGES public keys only. The separately enabled pairing
endpoint authenticates the owner's Tailscale source and Wolf PIN. Remote
approval can use a live Wolf UI or a short-lived, unique post-pair client
witness tied to the same Tailscale node and staged public key. Both require
explicit owner confirmation. No installation by a client .deb.
"""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys

from tailnet_owner_identity import own_tailnet_ipv4, pinned_owner_id, verify_owner_peer
from owner_enrollment import (_read_private_config, stage_request,
                              pending_requests, approve_request, REQUEST_ID)
from owner_qr_approval import PAGE_PREFIX, parse_page_request, render_page
from owner_access import PolicyError
from tailnet_wolf_review import single_active_wolf_ui, approve_reviewed_owner_request
from wolf_docker_adapter import WolfDockerAPI
from tailnet_wolf_pair import (pending_owner_wolf, pair_owner_wolf,
                              host_wolf_pair_api)
from tailnet_pair_witness import PairingWitness
from tailnet_wolf_fresh import FreshPairWindow
from owner_access import paired_client_ids

PORT = 18793
ROUTE = "/v1/owner/enrollment/request"
REVIEW_ROUTE = "/v1/owner/enrollment/wolf-candidate"
APPROVE_ROUTE = "/v1/owner/enrollment/approve"
PAIRED_CANDIDATE_ROUTE = "/v1/owner/enrollment/paired-candidate"
PAIR_PENDING_ROUTE = "/v1/owner/wolf-pair/pending"
PAIR_APPROVE_ROUTE = "/v1/owner/wolf-pair/approve"
PAIR_PREPARE_ROUTE = "/v1/owner/wolf-pair/prepare"
MAX_BODY = 1024
MAX_RESPONSE = 512


def make_handler(owner_user_id, state_dir, *, verify=verify_owner_peer,
                 stage=stage_request, wolf_factory=WolfDockerAPI,
                 approve=approve_reviewed_owner_request,
                 remote_approve_enabled=False, owner_pair_enabled=False,
                 pair_api=host_wolf_pair_api, commit=approve_request,
                 witness=None, require_fresh_pairing=False, fresh_window=None,
                 pending=pending_requests):
    witness = witness if witness is not None else PairingWitness()
    fresh_window = fresh_window if fresh_window is not None else FreshPairWindow()

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

        def _send_html(self, status, markup, nonce):
            payload = markup.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                "default-src 'none'; script-src 'nonce-" + nonce +
                "'; style-src 'nonce-" + nonce +
                "'; connect-src 'self'; form-action 'none'; "
                "frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def _verified_owner(self):
            if (len(self.headers.get_all("Host") or []) != 1
                    or self.headers["Host"] !=
                       f"{self.server.server_address[0]}:{self.server.server_address[1]}"
                    or self.headers.get("Transfer-Encoding") is not None):
                return False
            # Only the browser page's approval POST may carry an Origin;
            # it must match the exact local Tailnet host. Other routes keep
            # rejecting Origin, and all routes verify the real Tailscale peer.
            origin = self.headers.get("Origin")
            expected = ("http://" + self.server.server_address[0] + ":" +
                        str(self.server.server_address[1]))
            if (origin is not None and not (
                    self.path == APPROVE_ROUTE and origin == expected)):
                return False
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return False
            return verify(self.client_address[0], owner_user_id)

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
            if self.path not in (ROUTE, APPROVE_ROUTE, PAIR_APPROVE_ROUTE,
                                  PAIR_PREPARE_ROUTE, PAIRED_CANDIDATE_ROUTE):
                self._send(404, {"success": False, "status": "not_found"})
                return
            identity = self._verified_owner()
            if not identity:
                self._send(403, {"success": False, "status": "forbidden"})
                return
            if ((self.path in (APPROVE_ROUTE, PAIRED_CANDIDATE_ROUTE)
                 and not remote_approve_enabled)
                    or (self.path in (PAIR_APPROVE_ROUTE, PAIR_PREPARE_ROUTE)
                        and not owner_pair_enabled)
                    or (self.path == PAIR_PREPARE_ROUTE and not require_fresh_pairing)
                    or (self.path == PAIRED_CANDIDATE_ROUTE and not owner_pair_enabled)):
                self._send(403, {"success": False, "status": "disabled"})
                return
            try:
                obj = self._read_json(MAX_BODY)
                if self.path == PAIR_PREPARE_ROUTE:
                    if obj != {}:
                        raise ValueError("Pair preparation accepts only empty payload")
                    result = fresh_window.prepare(
                        identity, self.client_address[0], call_api=pair_api)
                    self._send(200, result)
                    return
                if self.path == PAIR_APPROVE_ROUTE:
                    if remote_approve_enabled:
                        # Source-bound review opt-in captures the baseline.
                        before = paired_client_ids(wolf_factory()(
                            "GET", "/api/v1/clients"))
                    if require_fresh_pairing:
                        result = fresh_window.pair(
                            identity, self.client_address[0],
                            obj, call_api=pair_api)
                    else:
                        result = pair_owner_wolf(self.client_address[0], obj,
                                                 call_api=pair_api)
                    if remote_approve_enabled:
                        # Only a successful host-side PIN approval creates
                        # a candidate. Plain Wolf pairing is unchanged.
                        witness.paired(identity, self.client_address[0], before)
                    self._send(200, result)
                    return
                if self.path == ROUTE:
                    if (not isinstance(obj, dict)
                            or set(obj) != {"version", "public_key"}
                            or type(obj["version"]) is not int
                            or obj["version"] != 1):
                        raise ValueError("Invalid public-key request")
                    result = stage(state_dir, obj["public_key"],
                                   source_ip=self.client_address[0])
                    if remote_approve_enabled and owner_pair_enabled:
                        witness.staged(identity, self.client_address[0],
                                       result["request_id"])
                    result = dict(result, phone_approval_available=remote_approve_enabled)
                    self._send(202, result)
                    return
                if self.path == PAIRED_CANDIDATE_ROUTE:
                    if (not isinstance(obj, dict)
                            or set(obj) != {"request_id"}
                            or not isinstance(obj["request_id"], str)):
                        raise ValueError("Invalid pending owner request")
                    try:
                        client_id = witness.candidate(
                            identity, self.client_address[0],
                            obj["request_id"], wolf_factory())
                    except PolicyError:
                        self._send(409, {"success": False,
                                         "status": "no_fresh_pair"})
                        return
                    self._send(200, {"success": True, "wolf_client_id": client_id})
                    return
                # A separately authenticated owner must deliberately choose
                # and confirm the Wolf ID observed in the current stream.
                # The host independently re-reads paired/active Wolf state.
                if (not isinstance(obj, dict)
                        or set(obj) not in (
                            {"request_id", "code", "wolf_client_id", "confirmed"},
                            {"request_id", "code", "wolf_client_id",
                             "confirmed", "source"})
                        or obj.get("confirmed") is not True
                        or any(not isinstance(obj[key], str)
                               for key in ("request_id", "code", "wolf_client_id"))):
                    raise ValueError("Explicit reviewed approval required")
                if "source" in obj and obj["source"] != "recent_pair":
                    raise PolicyError("Unsupported enrollment review source")
                if "source" in obj:
                    if not owner_pair_enabled:
                        raise PolicyError("Pairing witness feature disabled")
                    observed = witness.candidate(
                        identity, self.client_address[0],
                        obj["request_id"], wolf_factory())
                    if obj["wolf_client_id"] != observed:
                        raise PolicyError("Wolf device differs from trusted pairing witness")
                    # No lobby or session shutdown: still explicitly
                    # confirmed by the owner, and bound to a fresh
                    # server-observed client plus staged key on this node.
                    result = commit(state_dir, obj["request_id"], obj["code"],
                                    observed, confirmed=True,
                                    wolf_api=wolf_factory())
                else:
                    result = approve(
                        state_dir, obj["request_id"], obj["code"],
                        obj["wolf_client_id"], wolf_api=wolf_factory(),
                        approval=True)
                if (not isinstance(result, dict)
                        or result.get("success") is not True
                        or result.get("status") != "approved"):
                    raise PolicyError("Host approval was not committed")
                if "source" in obj:
                    witness.consumed(identity, self.client_address[0],
                                     obj["request_id"])
                # Avoid returning Wolf secrets or the host file paths.
                self._send(200, {"success": True, "status": "approved"})
            except (OSError, PolicyError, ValueError, TypeError, UnicodeError,
                    KeyError, RuntimeError):
                self._send(400, {"success": False, "status": "denied"})

        def do_GET(self):
            if self.path.startswith(PAGE_PREFIX):
                if not remote_approve_enabled or not self._verified_owner():
                    self._send(403, {"success": False, "status": "forbidden"})
                    return
                try:
                    request_id = parse_page_request(self.path)
                    request = next(
                        (entry for entry in pending(state_dir)
                         if entry["request_id"] == request_id), None)
                    if request is None:
                        raise ValueError("Unknown or expired enrollment request")
                    markup, nonce = render_page(
                        request_id, request["fingerprint"],
                        request["seconds_remaining"])
                except (OSError, PolicyError, ValueError, TypeError,
                        KeyError, RuntimeError):
                    self._send(404, {"success": False, "status": "not_found"})
                    return
                self._send_html(200, markup, nonce)
                return
            review_request_id = None
            if self.path.startswith(REVIEW_ROUTE + "/"):
                review_request_id = self.path[len(REVIEW_ROUTE) + 1:]
                if not REQUEST_ID.fullmatch(review_request_id):
                    self._send(404, {"success": False, "status": "not_found"})
                    return
            if review_request_id is None and self.path != PAIR_PENDING_ROUTE:
                self._send(404, {"success": False, "status": "not_found"})
                return
            owner = self._verified_owner()
            if not owner or (
                    review_request_id is not None and not remote_approve_enabled) or (
                    self.path == PAIR_PENDING_ROUTE and not owner_pair_enabled):
                self._send(403, {"success": False, "status": "forbidden"})
                return
            if self.path == PAIR_PENDING_ROUTE:
                try:
                    if require_fresh_pairing:
                        result = fresh_window.pending(
                            owner, self.client_address[0],
                            call_api=pair_api)
                    else:
                        result = pending_owner_wolf(self.client_address[0],
                                                    call_api=pair_api)
                    self._send(200, result)
                except (OSError, PolicyError, ValueError, TypeError, RuntimeError):
                    self._send(409, {"success": False, "status": "unavailable"})
                return
            try:
                request = next(
                    (item for item in pending(state_dir)
                     if item["request_id"] == review_request_id), None)
                if not request or not request.get("source_ip"):
                    raise PolicyError("No source-bound pending request")
                candidate = single_active_wolf_ui(
                    wolf_factory(), expected_source=request["source_ip"])
            except (OSError, PolicyError, ValueError, TypeError,
                    KeyError, RuntimeError):
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
    parser.add_argument("--require-fresh-wolf-pairing", action="store_true",
                        help="EXPERIMENTAL: only approve new pairing requests after owner-prepared baseline")
    args = parser.parse_args(argv)
    try:
        if args.require_fresh_wolf_pairing and not args.enable_owner_wolf_pairing:
            raise ValueError("Fresh request proof requires owner pairing endpoint")
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
                owner_pair_enabled=args.enable_owner_wolf_pairing,
                require_fresh_pairing=args.require_fresh_wolf_pairing)) as server:
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
