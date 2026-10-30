"""GTK regression: verified QR must actually be visible, not just claimed.

Run with: xvfb-run -a /usr/bin/python3 tests/smoke_owner_qr_ui.py
No tailnet, keys, QR encoder, host process or backend access.
"""
import importlib.machinery
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "src/owner-enroll-ui.py"
loader = importlib.machinery.SourceFileLoader("now_test_enroll_ui", str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

# Test the QR render path using an in-memory PNG, not actual enrollment.
buffer = io.BytesIO()
Image.new("RGB", (180, 180), "white").save(buffer, format="PNG")
png_bytes = buffer.getvalue()
def fake_import(name, file):
    if file == "owner-enroll-client.py":
        # Load the real client-side status predicate, never synthesize READY.
        client_path = ROOT / "src/owner-enroll-client.py"
        client_loader = importlib.machinery.SourceFileLoader(name, str(client_path))
        client_spec = importlib.util.spec_from_loader(client_loader.name, client_loader)
        client = importlib.util.module_from_spec(client_spec)
        client_loader.exec_module(client)
        return client
    assert file == "owner-qr.py", file
    return SimpleNamespace(
        approval_url=lambda *args: "http://100.121.156.34:18793/owner/approve/" + "a" * 32 + "#123456",
        qr_png=lambda url: png_bytes,
    )

module.load = fake_import

window = module.EnrollmentWindow("100.121.156.34", "optiplex")
try:
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    assert not window.qr_box.get_visible(), "QR container exposed before verified proof"

    window.pending_request = {
        "request_id": "a" * 32,
        "code": "123456",
        "fingerprint": "b" * 20,
    }
    window.proof_done(True, None)
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    assert window.qr_box.get_visible(), "QR container stayed hidden despite verified proof"
    assert window.qr_box.get_mapped(), "QR container did not map into real GTK window"
    assert window.qr_image.get_mapped(), "QR image is not visible inside its container"
    assert window.qr_label.get_mapped(), "QR heading is not visible"
    assert window.qr_hint.get_mapped(), "QR instructions are not visible"
    assert window.qr_image.get_pixbuf() is not None, "PNG missing from QR image"
    assert window.status.get_text().startswith("DEVICE VERIFIED BY HOST.")
    # A completed verification worker does not mean the host authorized it.
    for reply in (
        None, {}, {"success": False, "status": "needs_wolf_ui"},
        {"success": 1, "status": "needs_wolf_ui"},
        {"success": True, "status": "pending"},
        {"success": True, "status": "joined"},
        {"success": True, "status": "finished"},
        {"success": True, "status": "unavailable"},
    ):
        window.verify_done(reply, None)
        assert not window.status.get_text().startswith(
            "NOW OWNER-SERVICE ACCESS VERIFIED"), reply
    window.verify_done({"success": True, "status": "busy"}, True)
    assert not window.status.get_text().startswith(
        "NOW OWNER-SERVICE ACCESS VERIFIED")
    for state in ("needs_wolf_ui", "wolf_ui_connected", "busy", "in_use"):
        window.verify_done({"success": True, "status": state}, None)
        assert window.status.get_text().startswith(
            "NOW OWNER-SERVICE ACCESS VERIFIED"), state

    # Reusing a pending window must clear old codes before network work.
    window.job = lambda worker, callback: None
    window.request()
    assert window.code.get_text() == ""
    assert not window.qr_box.get_visible()
    assert not window.review_button.get_sensitive()

    pending = {
        "success": True, "status": "pending",
        "request_id": "a" * 32, "code": "123456",
        "fingerprint": "b" * 20, "transport": "ssh",
        "phone_approval_available": False,
    }
    window.request_done(pending, None)
    assert window.pending_request is pending
    assert not window.review_button.get_visible(), (
        "SSH fallback cannot reach host Tailnet review")
    assert not window.review_button.get_sensitive()

    # On a phone-capable host, only the independently authenticated phone
    # can perform the approval; a new client gets a QR, not a review button.
    window.request()
    pending["transport"] = "tailnet"
    pending["phone_approval_available"] = True
    window.request_done(pending, None)
    assert window.phone_approval_mode
    assert not window.review_button.get_visible()
    assert not window.review_button.get_sensitive()
    window.proof_done(False, None)
    assert window.code.get_text() == ""
    assert not window.qr_box.get_visible()

    print("Owner QR GTK smoke passed: QR visibility, fail-closed Verify, "
          "reset on retry/proof failure, review guard.")

finally:
    window.window.destroy()
