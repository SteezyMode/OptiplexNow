"""No-network regression contract for the owner-approved request transport."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "now_owner_enroll_client", ROOT / "src/owner-enroll-client.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeKeys:
    def __init__(self, public):
        self.public = public

    def validated_target(self, host, user):
        if host != "100.121.156.34" or user != "optiplex":
            raise ValueError("Invalid target")

    def ensure_key(self):
        return None, self.public


class EnrollmentClientTests(unittest.TestCase):
    def test_stages_only_public_key_through_existing_owner_ssh(self):
        with tempfile.TemporaryDirectory() as base:
            public = Path(base) / "id_ed25519.pub"
            public.write_text("ssh-ed25519 EXAMPLEPUBLICVALUE test@device\n")
            def runner(argv, **kwargs):
                self.assertEqual(argv[0], "ssh")
                self.assertIn("BatchMode=yes", argv)
                self.assertIn("IdentitiesOnly=yes", argv)
                self.assertIn("StrictHostKeyChecking=yes", argv)
                self.assertIn("ClearAllForwardings=yes", argv)
                self.assertEqual(argv[-2], "100.121.156.34")
                self.assertIn("owner_enrollment.py request", argv[-1])
                self.assertNotIn("ssh-copy-id", argv)
                sent = json.loads(kwargs["input"])
                self.assertEqual(sent["public_key"],
                                 "ssh-ed25519 EXAMPLEPUBLICVALUE test@device")
                self.assertNotIn("private_key", sent)
                result = {"success": True, "status": "pending",
                          "request_id": "1"*32, "code": "123456",
                          "fingerprint": "a"*20}
                return subprocess.CompletedProcess(
                    argv, 0, json.dumps(result).encode(), b"")
            answer = mod.request("100.121.156.34", "optiplex",
                                 key_module=FakeKeys(public), owner_key=public, runner=runner)
            self.assertEqual(answer["status"], "pending")
            self.assertEqual(answer["code"], "123456")

    def test_rejects_untrusted_host_response(self):
        with tempfile.TemporaryDirectory() as base:
            public = Path(base) / "id_ed25519.pub"
            public.write_text("ssh-ed25519 EXAMPLEPUBLICVALUE")
            for obj in ({"success": True, "status": "approved"},
                        {"success": True, "status": "pending",
                         "request_id": "bad", "code": "123456",
                         "fingerprint": "a"*20},
                        {"success": True, "status": "pending",
                         "request_id": "1"*32, "code": "NOTPIN",
                         "fingerprint": "a"*20}):
                with self.subTest(obj=obj):
                    def runner(argv, **kwargs):
                        return subprocess.CompletedProcess(
                            argv, 0, json.dumps(obj).encode(), b"")
                    with self.assertRaises(ValueError):
                        mod.request("100.121.156.34", "optiplex",
                                    key_module=FakeKeys(public), owner_key=public, runner=runner)

    def test_gui_and_host_bridge_scripts_compile_without_gtk_session(self):
        import py_compile
        for source in (
            "src/owner-enroll-client.py",
            "src/owner-enroll-ui.py",
            "src/owner-approvals-ui.py",
            "server/owner_enrollment.py",
        ):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as base:
                py_compile.compile(str(ROOT / source),
                                   cfile=str(Path(base) / "check.pyc"),
                                   doraise=True)

    def test_packaged_ui_requires_host_approval(self):
        host_ui = (ROOT / "src/owner-approvals-ui.py").read_text()
        client_ui = (ROOT / "src/owner-enroll-ui.py").read_text()
        pkg = (ROOT / "package.py").read_text()
        main = (ROOT / "src/main.c").read_text()
        self.assertIn("approve_request(state, request", host_ui)
        self.assertIn("confirmed=True", host_ui)
        self.assertIn("self.verified.get_active()", host_ui)
        self.assertIn("typed != self.requests[request_index]", host_ui)
        self.assertIn("APPROVE THIS DEVICE (OWNER QR)", main)
        self.assertNotIn('wizard_button(c,four,"REQUEST OWNER DEVICE APPROVAL"', main)
        self.assertIn("owner-enroll-ui.py", main)
        self.assertIn("owner_enrollment.py", pkg)
        self.assertIn("owner-approvals-ui.py", pkg)
        self.assertIn("owner-enroll-client.py", pkg)
        self.assertNotIn("ssh-copy-id", client_ui)


if __name__ == "__main__":
    unittest.main()
