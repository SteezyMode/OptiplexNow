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

    def test_existing_restricted_credential_skips_qr_and_staging(self):
        from unittest.mock import patch

        calls = []
        class Authorized:
            def invoke(self, host, user, action):
                calls.append((host, user, action))
                return {"success": True, "status": "idle"}

        with patch.object(mod, "_client_module", return_value=Authorized()), \
             patch.object(mod, "request_tailnet", side_effect=AssertionError("staged a duplicate key")), \
             patch.object(mod, "request", side_effect=AssertionError("used admin SSH")):
            result = mod.request_using_available_transport(
                "100.121.156.34", "optiplex", include_transport=True)
        self.assertEqual(result, {
            "success": True, "status": "already_authorized",
            "transport": "restricted_ssh"})
        self.assertEqual(calls, [("100.121.156.34", "optiplex", "status")])

    def test_inconclusive_restricted_access_check_allows_normal_staging(self):
        from unittest.mock import patch

        class NotVerified:
            def invoke(self, host, user, action):
                raise RuntimeError("host inaccessible or unapproved")

        pending = {"success": True, "status": "pending",
                   "request_id": "2"*32, "code": "654321",
                   "fingerprint": "b"*20,
                   "phone_approval_available": True}
        with patch.object(mod, "_client_module", return_value=NotVerified()), \
             patch.object(mod, "request_tailnet", return_value=pending) as staging:
            result = mod.request_using_available_transport(
                "100.121.156.34", "optiplex", include_transport=True)
        staging.assert_called_once_with("100.121.156.34")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["transport"], "tailnet")

    def test_tailnet_owner_denial_does_not_fall_back_to_admin_ssh(self):
        # An explicit server-side identity refusal must not downgrade the
        # enrollment boundary into an ordinary administrator SSH request.
        from unittest.mock import patch
        with patch.object(mod, "already_authorized", return_value=False), \
             patch.object(mod, "request_tailnet", side_effect=ValueError("not authorized")), \
             patch.object(mod, "request", side_effect=AssertionError("unsafe fallback")) as ssh:
            with self.assertRaisesRegex(ValueError, "not authorized"):
                mod.request_using_available_transport(
                    "100.121.156.34", "optiplex", include_transport=True)
            ssh.assert_not_called()

    def test_no_owner_listener_and_no_trusted_ssh_cannot_grant_access(self):
        from unittest.mock import patch
        with patch.object(mod, "already_authorized", return_value=False), \
             patch.object(mod, "request_tailnet", side_effect=ConnectionRefusedError()), \
             patch.object(mod, "request", side_effect=ValueError("owner SSH not configured")):
            with self.assertRaisesRegex(ValueError, "owner SSH not configured"):
                mod.request_using_available_transport(
                    "100.121.156.34", "optiplex", include_transport=True)

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
        self.assertIn('typed != request["code"]', host_ui)
        self.assertNotIn("client_combo", host_ui)
        self.assertIn("single_active_wolf_ui", host_ui)
        self.assertIn("self.review_button.set_visible(not self.phone_approval_mode)", client_ui)
        self.assertIn("or self.phone_approval_mode", client_ui)
        self.assertIn("submit_moonlight_proof(self.host, answer)", client_ui)
        self.assertIn('answer.get("status") == "already_authorized"', client_ui)
        self.assertIn("ALREADY AUTHORIZED for NOW-managed host services.", client_ui)
        self.assertIn("NOW OWNER-SERVICE ACCESS VERIFIED.", client_ui)
        self.assertIn("NOW approval does not revoke or gate that direct streaming.", client_ui)
        self.assertIn("WOLF PAIRING IS INDEPENDENT.", main)
        self.assertIn("NO STEAM FALLBACK", main)
        downloads = (ROOT / "src/downloads_flow.c").read_text()
        self.assertIn("Wolf pairing separately permits access to Wolf-published apps", downloads)
        self.assertIn("self.qr_box.hide()", client_ui)
        self.assertIn("APPROVE THIS DEVICE (OWNER QR)", main)
        self.assertNotIn('wizard_button(c,four,"REQUEST OWNER DEVICE APPROVAL"', main)
        self.assertIn("owner-enroll-ui.py", main)
        self.assertIn("owner_enrollment.py", pkg)
        self.assertIn("owner-approvals-ui.py", pkg)
        self.assertIn("owner-enroll-client.py", pkg)
        self.assertNotIn("ssh-copy-id", client_ui)


if __name__ == "__main__":
    unittest.main()
