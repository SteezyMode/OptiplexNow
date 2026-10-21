"""Real Linux AF_UNIX peer credentials and one-use simulated host approvals.

Tests use only disposable /tmp configuration and local socketpairs.
No listener is installed, no Docker operations or privileged calls occur.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import unittest
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "server"))
import host_owner  # noqa: E402
import host_stage  # noqa: E402
import host_transaction as tx  # noqa: E402

PLAN = {
    "tool": "now-host-plan", "schema_version": 1,
    "mode": "read_only_preview", "decision": "blocked",
    "may_apply": False, "changes_performed": False,
}
DIGEST = "sha256:" + "a" * 64


@unittest.skipUnless(hasattr(socket, "SO_PEERCRED") and sys.platform.startswith("linux"),
                     "Linux kernel peer credentials required")
class OwnerAuthorityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="now-owner-fixture-")
        self.addCleanup(temp.cleanup)
        stage = Path(temp.name) / "stage"
        host_stage.stage(stage, host_stage.make_bundle(
            PLAN, digest=DIGEST, render_node="/dev/dri/renderD128",
            gpu_vendor="intel"))
        self.workspace = Path("/tmp") / ("now-owner-managed-" + uuid4().hex)
        self.addCleanup(lambda: shutil.rmtree(self.workspace, ignore_errors=True))
        tx.prepare(stage, self.workspace)
        self.generation = tx._state(self.workspace)["active"]
        self.server, self.client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(self.server.close)
        self.addCleanup(self.client.close)
        self.now = [100.0]
        self.owner = host_owner.OwnerAuthority(
            os.getuid(), clock=lambda: self.now[0])
        self.calls = []

    def approve(self, uid, operation, workspace, generation):
        self.calls.append((uid, operation, workspace, generation))
        return True

    def issue(self, *, confirm=None):
        return self.owner.issue(
            self.server, operation="start_wolf",
            workspace=self.workspace, generation=self.generation,
            confirm=self.approve if confirm is None else confirm)

    def consume(self, ticket):
        self.owner.consume(
            self.server, ticket, operation="start_wolf",
            workspace=self.workspace, generation=self.generation)

    def test_actual_kernel_identity_and_explicit_trusted_callback(self):
        uid, pid = host_owner.peer_identity(self.server)
        self.assertEqual(uid, os.getuid())
        self.assertEqual(pid, os.getpid())
        ticket = self.issue()
        self.assertGreaterEqual(len(ticket), 32)
        self.assertEqual(self.calls, [
            (os.getuid(), "start_wolf", self.workspace, self.generation)])
        self.consume(ticket)
        self.assertFalse(self.owner._tickets)

    def test_replay_is_rejected_after_one_success(self):
        ticket = self.issue()
        self.consume(ticket)
        with self.assertRaises(host_owner.AuthorizationError):
            self.consume(ticket)

    def test_owner_uid_is_checked_using_kernel_not_payload(self):
        bad = host_owner.OwnerAuthority(os.getuid() + 100000)
        with self.assertRaisesRegex(host_owner.AuthorizationError, "not the configured owner"):
            bad.issue(self.server, operation="start_wolf",
                      workspace=self.workspace, generation=self.generation,
                      confirm=self.approve)
        self.assertEqual(self.calls, [])

    def test_no_callback_refusal_and_callback_exception(self):
        for cb in (False, 1, lambda *_: False,
                   lambda *_: 1):
            with self.subTest(cb=cb), self.assertRaises(host_owner.AuthorizationError):
                self.issue(confirm=cb)
        def broken(*_):
            raise RuntimeError("approval UI not available")
        with self.assertRaises(host_owner.AuthorizationError):
            self.issue(confirm=broken)
        self.assertEqual(self.owner._tickets, {})

    def test_wrong_operation_and_wrong_generation_fail_closed(self):
        with self.assertRaises(host_owner.AuthorizationError):
            self.owner.issue(self.server, operation="delete_containers",
                             workspace=self.workspace, generation=self.generation,
                             confirm=self.approve)
        with self.assertRaises(host_owner.AuthorizationError):
            self.owner.issue(self.server, operation="start_wolf",
                             workspace=self.workspace, generation="a" * 64,
                             confirm=self.approve)
        self.assertEqual(self.calls, [])

    def test_token_expires_and_is_consumed_even_on_failure(self):
        ticket = self.issue()
        self.now[0] += host_owner.TICKET_TTL + 1
        with self.assertRaises(host_owner.AuthorizationError):
            self.consume(ticket)
        with self.assertRaises(host_owner.AuthorizationError):
            self.consume(ticket)

    def test_operation_and_generation_bound_consumption_no_replay(self):
        ticket = self.issue()
        with self.assertRaises(host_owner.AuthorizationError):
            self.owner.consume(
                self.server, ticket, operation="stop_wolf",
                workspace=self.workspace, generation=self.generation)
        with self.assertRaises(host_owner.AuthorizationError):
            self.consume(ticket)

    def test_attempt_journal_prevents_new_authority(self):
        (self.workspace / "deployment.json").write_text("{}")
        with self.assertRaises(host_owner.AuthorizationError):
            self.issue()
        self.assertFalse(self.owner._tickets)

    def test_too_many_pending_is_bounded(self):
        for _ in range(16):
            self.issue()
        with self.assertRaises(host_owner.AuthorizationError):
            self.issue()
        self.now[0] += 61
        self.issue()
        self.assertEqual(len(self.owner._tickets), 1)

    def test_confirmation_generation_race_is_refused(self):
        # Trusted local UI callback runs while a configuration may be changed.
        def changed(*_):
            self.workspace.joinpath("deployment.json").write_text("{}")
            return True
        with self.assertRaises(host_owner.AuthorizationError):
            self.issue(confirm=changed)
        self.assertEqual(self.owner._tickets, {})

    def test_one_small_json_request_over_actual_unix_socket(self):
        request = {
            "version": 1, "operation": "start_wolf",
            "workspace": str(self.workspace), "generation": self.generation,
        }
        self.client.sendall(json.dumps(request).encode() + b"\n")
        result = host_owner.handle_local_request(
            self.server, self.owner, self.approve)
        self.assertEqual(result["status"], "approved_for_simulation")
        self.consume(result["ticket"])

    def test_one_request_bounded_reply_over_real_unix_stream(self):
        request = {
            "version": 1, "operation": "start_wolf",
            "workspace": str(self.workspace), "generation": self.generation,
        }
        self.client.sendall(json.dumps(request).encode() + b"\n")
        host_owner.serve_one(self.server, self.owner, self.approve)
        self.client.settimeout(2)
        response = json.loads(self.client.recv(1024))
        self.assertEqual(response["version"], 1)
        self.assertEqual(response["status"], "approved_for_simulation")
        self.consume(response["ticket"])

    def test_denied_reply_never_contains_internal_exception_details(self):
        self.client.sendall(b"invalid-json\n")
        host_owner.serve_one(self.server, self.owner, self.approve)
        self.client.settimeout(2)
        response = json.loads(self.client.recv(1024))
        self.assertEqual(response, {"version": 1, "status": "denied"})
        self.assertNotIn("ticket", response)
        self.assertFalse(self.owner._tickets)

    def test_version_bool_does_not_alias_integer_protocol_version(self):
        request = {
            "version": True, "operation": "start_wolf",
            "workspace": str(self.workspace), "generation": self.generation,
        }
        self.client.sendall(json.dumps(request).encode() + b"\n")
        host_owner.serve_one(self.server, self.owner, self.approve)
        response = json.loads(self.client.recv(1024))
        self.assertEqual(response["status"], "denied")
        self.assertEqual(self.calls, [])

    def test_no_trusted_confirmation_mechanism_cannot_issue(self):
        with self.assertRaises(host_owner.AuthorizationError):
            self.owner.issue(
                self.server, operation="start_wolf",
                workspace=self.workspace, generation=self.generation,
                confirm=None)

    def test_tcp_socket_is_explicitly_refused(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as other:
            with self.assertRaisesRegex(host_owner.AuthorizationError, "Unix"):
                host_owner.peer_identity(other)

    def test_rejects_unknown_protocol_fields_and_multiple_requests(self):
        baseline = {
            "version": 1, "operation": "start_wolf",
            "workspace": str(self.workspace), "generation": self.generation,
        }
        for altered in (
            {**baseline, "version": 99},
            {**baseline, "admin": True},
            {**baseline, "operation": "docker_rm"},
            {**baseline, "workspace": "/etc/optiplex-now"},
        ):
            with self.subTest(altered=altered):
                server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    client.sendall(json.dumps(altered).encode() + b"\n")
                    with self.assertRaises(host_owner.AuthorizationError):
                        host_owner.handle_local_request(server, self.owner, self.approve)
                finally:
                    server.close()
                    client.close()
        server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.sendall(json.dumps(baseline).encode() + b"\n{}\n")
            with self.assertRaises(host_owner.AuthorizationError):
                host_owner.handle_local_request(server, self.owner, self.approve)
        finally:
            server.close()
            client.close()

    def test_oversized_and_invalid_wire_requests(self):
        for payload in (b"x" * (host_owner.MAX_REQUEST + 1) + b"\n",
                        b"not-json\n", b"[]\n", b"\n", b"\xff\n"):
            with self.subTest(size=len(payload)):
                server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    client.sendall(payload)
                    with self.assertRaises(host_owner.AuthorizationError):
                        host_owner.handle_local_request(server, self.owner, self.approve)
                finally:
                    server.close()
                    client.close()
        self.assertFalse(self.owner._tickets)

    def test_no_remote_tcp_and_no_persistent_secrets(self):
        self.assertFalse(hasattr(host_owner, "serve_forever"))
        self.assertFalse(hasattr(host_owner, "start_docker"))
        self.assertFalse(hasattr(host_owner, "remove_container"))
        ticket = self.issue()
        self.assertNotIn(ticket, (self.workspace / tx.CURRENT_FILE).read_text())
        self.assertEqual(set(self.workspace.iterdir()).intersection({
            self.workspace / ".now-owner-token",
        }), set())


if __name__ == "__main__":
    unittest.main()
