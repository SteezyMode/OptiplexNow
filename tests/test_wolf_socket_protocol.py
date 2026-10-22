"""End-to-end local protocol fixture: real Unix HTTP socket, no Wolf daemon.

Proves the host adapter's exact HTTP bytes, response framing, restricted Docker
command shape and interaction with owner_launch's durable lease. Fabricated
Wolf payloads. This does NOT prove real Wolf API acceptance or client security.
"""
import json
import os
from pathlib import Path
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from owner_access import OwnerStore, PolicyError
from owner_launch import launch_owner_steam, owner_launch_status
from wolf_socket_adapter import (
    MAX_REQUEST, MAX_RESPONSE, WolfUnixAPI, WolfSocketError, parse_response,
    check_request, socket_timeout, DEFAULT_SOCKET_TIMEOUT,
    CREATE_SOCKET_TIMEOUT)
from wolf_docker_adapter import (WolfDockerAPI, CREATE_DOCKER_TIMEOUT,
                                 DEFAULT_DOCKER_TIMEOUT)
from test_owner_lobby import fixtures


class FakeWolfDaemon(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, path, datasets=None, *, response_mode=None):
        self.datasets = fixtures() if datasets is None else datasets
        self.response_mode = response_mode
        self.requests = []
        self.failure_on = None
        self.created = False
        self.mutex = threading.Lock()
        super().__init__(path, FakeWolfHandler)

    def make_reply(self, method, path, body):
        with self.mutex:
            self.requests.append((method, path, body))
            if self.failure_on == (method, path):
                return ("malformed", b"HTTP/1.1 200 OK\r\nContent-Length: 99\r\n\r\n{}")
            table = dict(zip((
                "/api/v1/clients", "/api/v1/profiles", "/api/v1/apps",
                "/api/v1/sessions", "/api/v1/lobbies"),
                self.datasets[1:]))
            if method == "GET" and path in table:
                return ("json", table[path])
            if method == "POST" and path == "/api/v1/lobbies/create":
                self.created = True
                return ("json", {"success": True, "lobby_id": "fixture_lobby_1"})
            if method == "POST" and path == "/api/v1/lobbies/join":
                if not self.created or body.get("lobby_id") != "fixture_lobby_1":
                    return ("json", {"success": False})
                return ("json", {"success": True})
            return ("status", b"HTTP/1.1 404 Not Found\r\nContent-Length: 2\r\n\r\n{}")


class FakeWolfHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(2.0)
        incoming = bytearray()
        while b"\r\n\r\n" not in incoming and len(incoming) < 16384:
            chunk = self.request.recv(8192)
            if not chunk:
                return
            incoming.extend(chunk)
        header, sep, body = bytes(incoming).partition(b"\r\n\r\n")
        if not sep:
            return
        first = header.split(b"\r\n", 1)[0].decode("ascii")
        method, path, _ = first.split(" ", 2)
        content_length = 0
        for line in header.split(b"\r\n")[1:]:
            if line.lower().startswith(b"content-length:"):
                content_length = int(line.split(b":", 1)[1].strip())
        while len(body) < content_length:
            chunk = self.request.recv(8192)
            if not chunk:
                return
            body += chunk
        parsed = json.loads(body) if body else None
        mode, response = self.server.make_reply(method, path, parsed)
        if mode in ("status", "malformed"):
            self.request.sendall(response)
            return
        encoded = json.dumps(response).encode()
        self.request.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            + b"Content-Length: " + str(len(encoded)).encode()
            + b"\r\nConnection: close\r\n\r\n" + encoded
        )


class WolfProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="now-wolf-fixture-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.socket = str(Path(self.temp.name) / "wolf.sock")
        self.server = FakeWolfDaemon(self.socket)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.api = WolfUnixAPI(self.socket)

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_create_lobby_timeout_outlives_upstream_daemon_wait(self):
        # Wolf upstream waits up to 20s for CreateLobby runner setup.
        self.assertGreater(CREATE_SOCKET_TIMEOUT, 20)
        self.assertGreater(CREATE_DOCKER_TIMEOUT, CREATE_SOCKET_TIMEOUT)
        self.assertEqual(socket_timeout("POST", "/api/v1/lobbies/create"),
                         CREATE_SOCKET_TIMEOUT)
        self.assertEqual(socket_timeout("POST", "/api/v1/lobbies/join"),
                         DEFAULT_SOCKET_TIMEOUT)
        self.assertEqual(socket_timeout("GET", "/api/v1/sessions"),
                         DEFAULT_SOCKET_TIMEOUT)
        calls = []
        def fake_runner(argv, **kwargs):
            calls.append((argv[-2:], kwargs["timeout"]))
            return subprocess.CompletedProcess(argv, 0, b'{"success":true}', b"")
        api = WolfDockerAPI(runner=fake_runner)
        api("GET", "/api/v1/sessions")
        api("POST", "/api/v1/lobbies/create", {"runner": {"type": "process"}})
        api("POST", "/api/v1/lobbies/join", {"lobby_id": "example"})
        self.assertEqual(calls, [
            (["GET", "/api/v1/sessions"], DEFAULT_DOCKER_TIMEOUT),
            (["POST", "/api/v1/lobbies/create"], CREATE_DOCKER_TIMEOUT),
            (["POST", "/api/v1/lobbies/join"], DEFAULT_DOCKER_TIMEOUT),
        ])

    def test_socket_uses_real_http_and_only_expected_paths(self):
        result = self.api("GET", "/api/v1/clients")
        self.assertTrue(result["success"])
        self.assertEqual(self.server.requests[0][:2], ("GET", "/api/v1/clients"))
        created = self.api(
            "POST", "/api/v1/lobbies/create", {"profile_id": "user", "pin": [1,2,3,4]})
        self.assertEqual(created["lobby_id"], "fixture_lobby_1")
        joined = self.api(
            "POST", "/api/v1/lobbies/join", {"lobby_id": created["lobby_id"]})
        self.assertTrue(joined["success"])
        self.assertEqual(len(self.server.requests), 3)

    def test_stop_lobby_has_explicit_narrow_allowlist_entry(self):
        body = {"lobby_id": "my_lobby", "pin": [1,2,3,4,5,6,7,8]}
        self.assertEqual(json.loads(check_request(
            "POST", "/api/v1/lobbies/stop", body)), body)
        self.assertEqual(socket_timeout("POST", "/api/v1/lobbies/stop"),
                         DEFAULT_SOCKET_TIMEOUT)

    def test_rejects_unapproved_operations_before_socket_connect(self):
        for method, path, payload in (
            ("POST", "/api/v1/sessions/stop", {}),
            ("POST", "/api/v1/clients/settings", {}),
            ("POST", "/api/v1/pair/client", {}),
            ("DELETE", "/api/v1/lobbies", None),
            ("POST", "/api/v1/lobbies/join", None),
            ("GET", "/api/v1/clients", {"should_not": "exist"}),
        ):
            with self.subTest(method=method, path=path):
                with self.assertRaises(WolfSocketError):
                    self.api(method, path, payload)
        self.assertEqual(self.server.requests, [])
        # The verified public schema GET is now intentionally read-only
        # allowlisted, not an arbitrary Wolf administration request.
        self.assertEqual(
            check_request("GET", "/api/v1/openapi-schema"), b"")

    def test_invalid_http_framing_never_reports_success(self):
        raws = [
            b"",
            b"HTTP/1.1 403 Unauthorized\r\nContent-Length: 2\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nnull",
            b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nBAD",
        ]
        for raw in raws:
            with self.subTest(raw=raw[:35]):
                with self.assertRaises(WolfSocketError):
                    parse_response(raw)

    def test_size_limits_are_enforced(self):
        with self.assertRaisesRegex(WolfSocketError, "too large"):
            self.api("POST", "/api/v1/lobbies/create",
                     {"runner": "X" * (MAX_REQUEST + 1)})
        with self.assertRaises(WolfSocketError):
            parse_response(b"HTTP/1.1 200 OK\r\n\r\n" + b"x" * (MAX_RESPONSE + 1))
        self.assertEqual(self.server.requests, [])

    def test_bad_socket_does_not_echo_secrets_or_retry(self):
        self.server.failure_on = ("POST", "/api/v1/lobbies/create")
        with self.assertRaises(WolfSocketError) as exc:
            self.api("POST", "/api/v1/lobbies/create",
                     {"pin": [4,3,2,1], "runner": {"env": ["SECRET=PRIVATE"]}})
        self.assertNotIn("SECRET", str(exc.exception))
        self.assertNotIn("PRIVATE", str(exc.exception))
        self.assertEqual(len(self.server.requests), 1)

    def test_container_command_shape_and_stdin_is_separate(self):
        calls = []
        def fake_runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, b'{"success":true}', b"")
        api = WolfDockerAPI(runner=fake_runner)
        self.assertEqual(api("POST", "/api/v1/lobbies/join", {
            "lobby_id": "test", "pin": [3,2,1,0]}), {"success": True})
        argv, opts = calls[0]
        self.assertEqual(argv[:5], ["docker", "exec", "-i", "wolf", "python3"])
        self.assertEqual(argv[-2:], ["POST", "/api/v1/lobbies/join"])
        self.assertNotIn("pin", " ".join(argv[0:6]))
        self.assertIn(b'"pin":[3,2,1,0]', opts["input"])
        self.assertIs(opts["stderr"], subprocess.DEVNULL)
        with self.assertRaises(WolfSocketError):
            api("POST", "/api/v1/sessions/stop", {})
        self.assertEqual(len(calls), 1)

    def test_full_transaction_over_real_socket_with_docker_boundary(self):
        # Execute actual published adapter source inside a child Python
        # process, substituting only the UNIX socket fixture path. No Docker.
        from wolf_docker_adapter import ADAPTER_FILE
        source = ADAPTER_FILE.read_text(encoding="utf-8")
        fixed = source.replace(
            'WOLF_SOCKET = "/run/user/wolf/wolf.sock"',
            f"WOLF_SOCKET = {self.socket!r}")
        self.assertNotEqual(source, fixed)
        def fake_docker(argv, **kwargs):
            self.assertEqual(argv[:5],
                             ["docker", "exec", "-i", "wolf", "python3"])
            self.assertEqual(argv[-2][0], "G" if argv[-2] == "GET" else "P")
            actual = [sys.executable, "-c", fixed, *argv[-2:]]
            return subprocess.run(actual, **kwargs)
        api = WolfDockerAPI(runner=fake_docker)
        store = OwnerStore(str(Path(self.temp.name) / "private"))
        with store.locked() as fd:
            store.write(fd, fixtures()[0])
        result = launch_owner_steam("1001", api, store=store, execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(result["status"], "joined")
        self.assertEqual(owner_launch_status(store)["status"], "joined")
        methods = [(m, p) for m, p, _ in self.server.requests]
        self.assertEqual(methods, [
            ("GET", "/api/v1/clients"),
            ("GET", "/api/v1/profiles"),
            ("GET", "/api/v1/apps"),
            ("GET", "/api/v1/sessions"),
            ("GET", "/api/v1/lobbies"),
            ("POST", "/api/v1/lobbies/create"),
            ("POST", "/api/v1/lobbies/join"),
        ])
        self.assertEqual(self.server.requests[-1][2]["lobby_id"],
                         "fixture_lobby_1")
        # The second request is rejected before any new socket operation.
        with self.assertRaises(PolicyError):
            launch_owner_steam("1001", api, store=store, execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(len(self.server.requests), 7)

    def test_ambiguous_create_response_keeps_blocking_lease(self):
        self.server.failure_on = ("POST", "/api/v1/lobbies/create")
        store = OwnerStore(str(Path(self.temp.name) / "private"))
        with store.locked() as fd:
            store.write(fd, fixtures()[0])
        with self.assertRaisesRegex(PolicyError, "uncertain"):
            launch_owner_steam("1001", self.api, store=store,
                               execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(owner_launch_status(store)["status"], "uncertain")
        self.assertEqual(self.server.requests[-1][:2],
                         ("POST", "/api/v1/lobbies/create"))
        with self.assertRaisesRegex(PolicyError, "manual review"):
            launch_owner_steam("1001", self.api, store=store,
                               execution_approved=True, video_caps="video/x-raw")
        self.assertEqual(len(self.server.requests), 6)


if __name__ == "__main__":
    unittest.main()
