"""Real Linux AF_UNIX owner approval tests; never contact Tailscale or Moonlight."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
from threading import Thread
from unittest.mock import patch
import unittest

SERVER = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(SERVER))
import now_pairing_requests

spec = importlib.util.spec_from_file_location(
    "now_pairing_owner", SERVER / "now_pairing_owner.py")
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


class OwnerSocketTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="now-owner-test-")
        # Another regression module loads this same file dynamically during
        # unittest discovery; resolve types from the current shared module.
        pairing = sys.modules["now_pairing_requests"]
        self.queue = pairing.PairingRequests()
        self.peer = pairing.PeerIdentity("n_DEVICE_01", "u_ACCOUNT_01")
        self.service = owner.OwnerControl(self.folder.name, self.queue)
        self.thread = Thread(target=self.service.serve_forever,
                             kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.service.shutdown()
        self.service.server_close()
        self.thread.join(timeout=2)
        self.folder.cleanup()

    def ask(self, payload):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(2)
            conn.connect(self.service.socket_path)
            conn.sendall(json.dumps(payload).encode() + b"\n")
            with conn.makefile("rb") as reader:
                return json.loads(reader.readline(8193))

    def test_real_unix_owner_list_then_approve_and_consume_once(self):
        request_id = self.queue.request(self.peer, "sunshine")
        response = owner.owner_command(self.folder.name, "list")
        self.assertTrue(response["ok"])
        self.assertEqual(len(response["pending"]), 1)
        self.assertEqual(response["pending"][0]["request_id"], request_id)
        self.assertEqual(response["pending"][0]["backend"], "sunshine")
        self.assertTrue(owner.owner_command(
            self.folder.name, "approve", request_id)["ok"])
        self.assertEqual(self.queue.status_for_peer(self.peer, request_id), "approved")
        self.assertIsNone(self.queue.take_grant_for_adapter(self.peer, request_id, "wolf"))
        grant = self.queue.take_grant_for_adapter(self.peer, request_id, "sunshine")
        self.assertIsNotNone(grant)
        self.assertIsNone(self.queue.take_grant_for_adapter(self.peer, request_id, "sunshine"))
        self.assertFalse(owner.owner_command(
            self.folder.name, "approve", request_id)["ok"])

    def test_owner_deny_never_grants(self):
        request_id = self.queue.request(self.peer, "wolf")
        self.assertTrue(owner.owner_command(self.folder.name, "deny", request_id)["ok"])
        self.assertEqual(self.queue.status_for_peer(self.peer, request_id), "denied")
        self.assertFalse(owner.owner_command(self.folder.name, "approve", request_id)["ok"])
        self.assertIsNone(self.queue.take_grant_for_adapter(self.peer, request_id, "wolf"))

    def test_no_remote_or_client_approval_actions(self):
        req = self.queue.request(self.peer, "wolf")
        for action in ("request", "grant", "consume", "run", "restart",
                       "status", "pair", None):
            with self.subTest(action=action):
                result = self.ask({"action": action, "request_id": req,
                                   "peer": {"node_id": "forged"}})
                self.assertFalse(result["ok"])
        self.assertEqual(self.queue.status_for_peer(self.peer, req), "pending")
        self.assertFalse(self.ask({"action": "approve", "request_id": req,
                                   "owner": True})["ok"])
        self.assertEqual(self.queue.status_for_peer(self.peer, req), "pending")
        self.assertTrue(self.ask({"action": "approve", "request_id": req})["ok"])

    def test_os_uid_mismatch_is_rejected_before_dispatch(self):
        req = self.queue.request(self.peer, "sunshine")
        with patch.object(owner, "_peer_uid", return_value=os.geteuid() + 1):
            self.assertEqual(self.ask({"action": "list"})["error"], "owner_only")
            self.assertEqual(self.ask({"action": "approve", "request_id": req})["error"],
                             "owner_only")
        self.assertEqual(self.queue.status_for_peer(self.peer, req), "pending")

    def test_socket_is_private_and_deleted_on_close(self):
        path = self.service.socket_path
        info = os.lstat(path)
        self.assertTrue(stat.S_ISSOCK(info.st_mode))
        self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.folder.name).st_mode), 0o700)
        self.service.shutdown()
        self.service.server_close()
        self.thread.join(timeout=2)
        self.assertFalse(os.path.lexists(path))

    def test_refuses_clobbering_existing_socket(self):
        with self.assertRaises(FileExistsError):
            owner.OwnerControl(self.folder.name, self.queue)
        self.assertTrue(self.ask({"action": "list"})["ok"])

    def test_refuses_shared_or_symlinked_directory(self):
        with tempfile.TemporaryDirectory(prefix="now-owner-dir-") as dirname:
            os.chmod(dirname, 0o755)
            with self.assertRaises(PermissionError):
                owner.OwnerControl(dirname, self.queue)
            os.chmod(dirname, 0o700)
            link = os.path.join(dirname, "nested-link")
            os.symlink(self.folder.name, link)
            with self.assertRaises(PermissionError):
                owner.OwnerControl(link, self.queue)
            self.assertFalse(os.path.exists(os.path.join(dirname, "owner.sock")))

    def test_refuses_wrong_queue_type(self):
        with self.assertRaises(TypeError):
            owner.OwnerControl(self.folder.name, {"state": "pending"})

    def test_malformed_oversized_and_non_json_requests(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(2)
            conn.connect(self.service.socket_path)
            conn.sendall(b"x" * 1030 + b"\n")
            with conn.makefile("rb") as reader:
                response = json.loads(reader.readline())
            self.assertFalse(response["ok"])
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(2)
            conn.connect(self.service.socket_path)
            conn.sendall(b"{unparseable}\n")
            with conn.makefile("rb") as reader:
                response = json.loads(reader.readline())
            self.assertFalse(response["ok"])

    def test_parallel_owner_decisions_allow_exactly_one(self):
        req = self.queue.request(self.peer, "wolf")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda _: owner.owner_command(self.folder.name, "approve", req)["ok"],
                range(24)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.queue.status_for_peer(self.peer, req), "approved")

    def test_command_line_local_only(self):
        request_id = self.queue.request(self.peer, "sunshine")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(owner.main(
                ["--socket-dir", self.folder.name, "list"]), 0)
        self.assertIn(request_id, output.getvalue())
        self.assertIn("n_DEVICE_01", output.getvalue())
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(owner.main(
                ["--socket-dir", self.folder.name, "approve", request_id]), 0)
        self.assertIn("NOT been completed", output.getvalue())

    def test_invalid_cli_or_socket_directory_does_not_approve(self):
        req = self.queue.request(self.peer, "wolf")
        with self.assertRaises(ValueError):
            owner.owner_command(self.folder.name, "pair", req)
        with self.assertRaises(ValueError):
            owner.owner_command(self.folder.name, "approve")
        with self.assertRaises(ValueError):
            owner.owner_command(self.folder.name, "list", req)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(owner.main(
                ["--socket-dir", "/path/does/not/exist", "approve", req]), 1)
        self.assertEqual(self.queue.status_for_peer(self.peer, req), "pending")


if __name__ == "__main__":
    unittest.main()
