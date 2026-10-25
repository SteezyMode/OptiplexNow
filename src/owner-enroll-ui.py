#!/usr/bin/python3
"""Graphical request to stage a restricted owner key (alpha pilot).

Prefer an opt-in, owner-authenticated Tailscale host staging listener.
If the listener is absent, the existing TRUSTED owner SSH pilot can stage
the request. Neither path grants owner rights. The private key stays local.
"""
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
from threading import Thread

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, GdkPixbuf

ROOT = Path(__file__).resolve().parent


def load(name, file):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / file))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class EnrollmentWindow:
    def __init__(self, host, user):
        self.host, self.user = host, user
        self.closed = False
        self.busy = False
        self.pending_request = None
        self.review_source = None
        self.window = Gtk.Window(title="NOW | Request Owner Access")
        self.window.set_default_size(460, 550)
        self.window.connect("destroy", self.destroy)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=13)
        column.set_border_width(22)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.window.add(scroll)
        scroll.add(column)
        heading = Gtk.Label(label="APPROVE THIS DEVICE")
        heading.set_xalign(0)
        column.pack_start(heading, False, False, 0)
        info = Gtk.Label(
            label="Request a separate Games/Downloads device credential.\n"
                  "An owner with verified Tailscale access can review the active "
                  "Wolf UI stream remotely when the host has enabled it. "
                  "Otherwise use the existing host-only owner pilot.")
        info.set_xalign(0)
        info.set_line_wrap(True)
        column.pack_start(info, False, False, 0)
        self.status = Gtk.Label(label="No request submitted.")
        self.status.set_xalign(0)
        self.status.set_line_wrap(True)
        self.status.set_selectable(True)
        column.pack_start(self.status, False, False, 0)
        self.code = Gtk.Label(label="")
        self.code.set_xalign(0)
        self.code.set_selectable(True)
        self.code.set_line_wrap(True)
        column.pack_start(self.code, False, False, 0)
        row = Gtk.Box(spacing=7)
        column.pack_start(row, False, False, 0)
        self.request_button = Gtk.Button(label="REQUEST OWNER APPROVAL")
        self.request_button.connect("clicked", self.request)
        row.pack_start(self.request_button, True, True, 0)
        self.check_button = Gtk.Button(label="VERIFY ACCESS")
        self.check_button.connect("clicked", self.verify)
        row.pack_start(self.check_button, True, True, 0)
        self.review_button = Gtk.Button(label="REVIEW WOLF DEVICE / APPROVE REMOTELY")
        self.review_button.set_sensitive(False)
        self.review_button.connect("clicked", self.review)
        column.pack_start(self.review_button, False, False, 0)
        self.qr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.qr_box.set_no_show_all(True)
        self.qr_label = Gtk.Label(label="SCAN ON YOUR OWNER PHONE (TAILSCALE ON)")
        self.qr_label.set_xalign(0)
        self.qr_box.pack_start(self.qr_label, False, False, 0)
        self.qr_image = Gtk.Image()
        self.qr_box.pack_start(self.qr_image, False, False, 0)
        self.qr_hint = Gtk.Label(
            label="Keep this device's Wolf UI stream open. On your phone, "
                  "check the code and fingerprint, then tap Approve. "
                  "No public website or third-party QR generator is used.")
        self.qr_hint.set_xalign(0)
        self.qr_hint.set_line_wrap(True)
        self.qr_box.pack_start(self.qr_hint, False, False, 0)
        column.pack_start(self.qr_box, False, False, 0)
        self.window.show_all()
        self.qr_box.hide()

    def destroy(self, *_):
        self.closed = True
        Gtk.main_quit()

    def job(self, worker, callback):
        if self.busy:
            return
        self.busy = True
        self.request_button.set_sensitive(False)
        self.check_button.set_sensitive(False)
        self.review_button.set_sensitive(False)

        def run():
            try:
                answer = worker()
                error = None
            except Exception:
                answer, error = None, True
            GLib.idle_add(self.finished, callback, answer, error)

        Thread(target=run, daemon=True).start()

    def finished(self, callback, answer, error):
        if self.closed:
            return False
        self.busy = False
        self.request_button.set_sensitive(True)
        self.check_button.set_sensitive(True)
        self.review_button.set_sensitive(self.pending_request is not None)
        callback(answer, error)
        return False

    def request(self, *_):
        self.pending_request = None
        self.review_source = None
        self.review_button.set_sensitive(False)
        self.qr_box.hide()
        self.status.set_text("Contacting owner server through Tailscale...")
        self.job(lambda: load("now_owner_client_request", "owner-enroll-client.py").request_using_available_transport(
            self.host, self.user, include_transport=True), self.request_done)

    def request_done(self, answer, error):
        if error:
            self.status.set_text(
                "Request could not reach the host enrollment helper. "
                "The server owner must install and enable the supported "
                "owner enrollment components. No access was granted.")
            return
        self.pending_request = answer
        self.review_button.set_sensitive(True)
        self.status.set_text(
            "PENDING OWNER APPROVAL. If this Moonlight identity was just paired "
            "through the same owner Tailscale service, choose Review below; "
            "otherwise keep Wolf UI active or use trusted host review.")
        self.code.set_text(
            f"REQUEST CODE: {answer['code']}\n"
            f"KEY FINGERPRINT: {answer['fingerprint']}\n"
            "Do not transfer your private key. Click Verify Access after approval.")
        if (answer.get("transport") == "tailnet" and
                answer.get("phone_approval_available") is True):
            self.status.set_text(
                "Verifying this computer's existing Moonlight identity. "
                "Your private key stays here; phone approval follows.")
            self.job(lambda: load(
                "now_owner_client_prove", "owner-enroll-client.py"
            ).submit_moonlight_proof(self.host, answer), self.proof_done)
        else:
            self.status.set_text(
                "Request staged; phone approval is unavailable on this host. "
                "Host-local owner review remains available.")

    def proof_done(self, result, error):
        if error or result is not True:
            self.qr_box.hide()
            self.status.set_text(
                "Moonlight identity could not be proven automatically. "
                "No QR approval has been offered and no access was granted. "
                "Verify the installed Moonlight profile or host proof service.")
            return
        try:
            answer = self.pending_request
            if not answer:
                return
            qr = load("now_owner_qr", "owner-qr.py")
            url = qr.approval_url(self.host, answer["request_id"], answer["code"])
            png = qr.qr_png(url)
            loader = GdkPixbuf.PixbufLoader.new_with_type("png")
            loader.write(png)
            loader.close()
            self.qr_image.set_from_pixbuf(loader.get_pixbuf())
            self.qr_box.show_all()
            self.status.set_text(
                "DEVICE VERIFIED BY HOST. Scan the QR using your Tailscale-"
                "connected owner phone, compare the code, and tap Approve. "
                "Your Moonlight private key remains on this computer.")
        except (OSError, ValueError):
            self.status.set_text(
                "Device proof recorded, but QR image generation failed. "
                "Check the installed qrencode package.")

    def review(self, *_):
        if self.pending_request is None:
            return
        self.status.set_text(
            "Checking this node's fresh Wolf pairing; otherwise the active Wolf UI...")
        request_id = self.pending_request["request_id"]
        self.job(lambda: load("now_owner_client_review", "owner-enroll-client.py").review_for_owner(
            self.host, request_id), self.review_done)

    def review_done(self, review, error):
        if error or not isinstance(review, dict):
            self.status.set_text(
                "No fresh witnessed pairing or unique active Wolf UI. "
                "No approval granted; use the trusted host owner review.")
            return
        request = self.pending_request
        if not request:
            return
        candidate = review["wolf_client_id"]
        self.review_source = review["source"]
        source_label = (
            "new Wolf ID observed since this node's owner-approved PIN pairing"
            if self.review_source == "recent_pair" else
            "sole active paired Wolf UI device")
        dialog = Gtk.MessageDialog(
            transient_for=self.window, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="Approve this restricted owner device?")
        dialog.format_secondary_text(
            f"Host-observed candidate: {candidate}\n"
            f"Reason: {source_label}\n"
            f"Request code: {request['code']}\n"
            f"Key fingerprint: {request['fingerprint']}\n\n"
            "Confirm you personally paired or opened this exact Moonlight "
            "device from this MacBook. The pairing witness is not cryptographic "
            "proof of the key/certificate link. Approving installs only a "
            "forced-command Games/Downloads key, never a generic shell. "
            "Cancel if there is any ambiguity.")
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Approve reviewed device", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        result = dialog.run()
        dialog.destroy()
        if result != Gtk.ResponseType.OK:
            self.status.set_text("Remote approval cancelled. No access granted.")
            return
        self.status.set_text("Requesting verified host owner authorization...")
        self.job(lambda: load("now_owner_client_approve", "owner-enroll-client.py").approve_reviewed_tailnet(
            self.host, request["request_id"], request["code"], candidate,
            source=self.review_source),
            self.remote_approved)

    def remote_approved(self, success, error):
        if error or success is not True:
            self.status.set_text(
                "Remote owner approval was refused. No privileges assumed. "
                "The stream may have changed or the host may not allow it.")
            return
        self.pending_request = None
        self.review_source = None
        self.review_button.set_sensitive(False)
        self.status.set_text(
            "REMOTE OWNER APPROVAL RECORDED. Use VERIFY ACCESS to confirm "
            "the separate restricted credential works.")

    def verify(self, *_):
        self.status.set_text("Checking the restricted host authorization...")
        self.job(lambda: load("now_owner_games_check", "owner-games-client.py").invoke(
            self.host, self.user, "status"), self.verify_done)

    def verify_done(self, answer, error):
        if error:
            self.status.set_text(
                "Not approved yet, or host unavailable. "
                "Request a device review or ask the owner to approve access.")
        else:
            self.status.set_text(
                "OWNER ACCESS VERIFIED. Games and authorized Downloads can now connect.")


def main():
    if len(sys.argv) != 3:
        return 1
    Gtk.init([])
    EnrollmentWindow(sys.argv[1], sys.argv[2])
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
