"""Graphical SSH enrollment contract, without opening SSH connections."""
import importlib.util
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

file = Path(__file__).resolve().parents[1] / "src" / "ssh-authorize.py"
spec = importlib.util.spec_from_file_location("now_ssh_authorize", file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeCopyID:
    def __init__(self, exit_code=0, output=b"server-specific output"):
        self.returncode = exit_code
        self.output = output
        self.pid = 4321
        self.calls = []

    def communicate(self, timeout=None):
        self.calls.append(timeout)
        return self.output, None

    def poll(self):
        return self.returncode


class SSHAuthorizeTests(unittest.TestCase):
    def test_validates_host_and_account_without_shell_expansion(self):
        self.assertEqual(module.validate("100.88.1.5", "test_user"),
                         ("100.88.1.5", "test_user"))
        for host, user in (("-option", "alice"), ("host;cmd", "alice"),
                           ("host", "-u"), ("host", "alice@evil"),
                           ("host", "")):
            with self.subTest(host=host, user=user):
                with self.assertRaises(ValueError):
                    module.validate(host, user)

    def test_existing_matching_key_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            ssh = Path(root) / ".ssh"
            ssh.mkdir(mode=0o700)
            private = ssh / "id_ed25519"
            public = ssh / "id_ed25519.pub"
            private.write_text("PRIVATE-KEEP")
            public.write_text("PUBLIC-KEEP")
            with mock.patch.object(module.subprocess, "run") as run:
                self.assertEqual(module.select_key(root), public)
            run.assert_not_called()
            self.assertEqual(private.read_text(), "PRIVATE-KEEP")

    def test_missing_matching_public_key_refuses_to_overwrite_private(self):
        with tempfile.TemporaryDirectory() as root:
            ssh = Path(root) / ".ssh"
            ssh.mkdir(mode=0o700)
            (ssh / "id_ed25519").write_text("PRIVATE-KEEP")
            with mock.patch.object(module.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "no public key"):
                    module.select_key(root)
            run.assert_not_called()

    def test_symlink_and_unsafe_directory_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "target"
            target.mkdir(mode=0o700)
            (Path(root) / ".ssh").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                module.select_key(root)
        with tempfile.TemporaryDirectory() as root:
            ssh = Path(root) / ".ssh"
            ssh.mkdir(mode=0o777)
            ssh.chmod(0o777)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                module.select_key(root)

    def test_installer_does_not_require_or_change_server_root_access(self):
        with tempfile.TemporaryDirectory() as root:
            askpass = Path(root) / "askpass"
            askpass.write_text("#!/bin/sh\nexit 1\n")
            askpass.chmod(0o700)
            pubkey = Path(root) / "id_ed25519.pub"
            pubkey.write_text("ssh-ed25519 MOCK")
            child = FakeCopyID()
            with mock.patch.object(module, "ASKPASS", str(askpass)), \
                 mock.patch.object(module.shutil, "which", return_value="/usr/bin/ssh-copy-id"), \
                 mock.patch.dict(os.environ, {"DISPLAY": ":99"}, clear=False), \
                 mock.patch.object(module.subprocess, "Popen", return_value=child) as popen:
                self.assertEqual(module.authorize("100.80.1.2", "alice", pubkey), 0)
            args, kwargs = popen.call_args
            command = args[0]
            self.assertEqual(command[0], "ssh-copy-id")
            self.assertEqual(command[-1], "alice@100.80.1.2")
            self.assertIn("StrictHostKeyChecking=ask", command)
            self.assertTrue(kwargs["start_new_session"])
            self.assertEqual(kwargs["env"]["SSH_ASKPASS_REQUIRE"], "force")
            self.assertEqual(kwargs["env"]["SSH_ASKPASS"], str(askpass))
            self.assertNotIn("sudo", command)
            self.assertNotIn("my-secret-password", " ".join(command).lower())
            self.assertEqual(child.calls, [module.SSH_TIMEOUT])

    def test_password_refusal_is_not_success(self):
        with tempfile.TemporaryDirectory() as root:
            askpass = Path(root) / "askpass"
            askpass.write_text("mock")
            askpass.chmod(0o700)
            child = FakeCopyID(exit_code=1)
            with mock.patch.object(module, "ASKPASS", str(askpass)), \
                 mock.patch.object(module.shutil, "which", return_value="ssh-copy-id"), \
                 mock.patch.dict(os.environ, {"DISPLAY": ":99"}, clear=False), \
                 mock.patch.object(module.subprocess, "Popen", return_value=child):
                self.assertNotEqual(module.authorize("100.80.1.2", "alice", Path(root) / "pub"), 0)

    def test_no_desktop_fails_instead_of_falling_back_to_terminal(self):
        with mock.patch.dict(os.environ, {"DISPLAY": "", "WAYLAND_DISPLAY": ""}), \
             mock.patch.object(module.shutil, "which", return_value="ssh-copy-id"):
            with self.assertRaisesRegex(ValueError, "graphical desktop"):
                module.authorize("host", "user", Path("/tmp/placeholder.pub"))


if __name__ == "__main__":
    unittest.main()
