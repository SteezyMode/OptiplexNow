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
module.load = lambda name, file: SimpleNamespace(
    approval_url=lambda *args: "http://100.121.156.34:18793/owner/approve/" + "a" * 32 + "#123456",
    qr_png=lambda url: png_bytes,
)

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
    print("Owner QR GTK smoke passed: hidden initially, visible after proof.")
finally:
    window.window.destroy()
