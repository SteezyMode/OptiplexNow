#!/usr/bin/python3
"""Graphical owner-key request on a trusted Linux owner client (alpha pilot).

Uses the already-approved ordinary owner SSH link ONLY to stage a request.
The separate Ed25519 private key is generated/kept on this Linux profile.
"""
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
from threading import Thread

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

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
        self.window = Gtk.Window(title="NOW | Request Owner Access")
        self.window.set_default_size(440, 265)
        self.window.connect("destroy", self.destroy)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=13)
        column.set_border_width(22)
        self.window.add(column)
        heading = Gtk.Label(label="APPROVE THIS DEVICE")
        heading.set_xalign(0)
        column.pack_start(heading, False, False, 0)
        info = Gtk.Label(
            label="Request a separate Games/Downloads device credential.\n"
                  "Only the owner at the server can approve it. This does not "
                  "alter Moonlight pairing or the server's Steam session.")
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
        self.window.show_all()

    def destroy(self, *_):
        self.closed = True
        Gtk.main_quit()

    def job(self, worker, callback):
        if self.busy:
            return
        self.busy = True
        self.request_button.set_sensitive(False)
        self.check_button.set_sensitive(False)

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
        callback(answer, error)
        return False

    def request(self, *_):
        self.status.set_text("Contacting owner server through Tailscale...")
        self.job(lambda: load("now_owner_client_request", "owner-enroll-client.py").request_using_available_transport(
            self.host, self.user), self.request_done)

    def request_done(self, answer, error):
        if error:
            self.status.set_text(
                "Request could not reach the host enrollment helper. "
                "The server owner must install and enable the supported "
                "owner enrollment components. No access was granted.")
            return
        self.status.set_text(
            "PENDING OWNER APPROVAL. On the host, open NOW Owner Approvals. "
            "Compare this code and independently verify the Wolf device ID.")
        self.code.set_text(
            f"REQUEST CODE: {answer['code']}\n"
            f"KEY FINGERPRINT: {answer['fingerprint']}\n"
            "Do not transfer your private key. Click Verify Access after approval.")

    def verify(self, *_):
        self.status.set_text("Checking the restricted host authorization...")
        self.job(lambda: load("now_owner_games_check", "owner-games-client.py").invoke(
            self.host, self.user, "status"), self.verify_done)

    def verify_done(self, answer, error):
        if error:
            self.status.set_text(
                "Not approved yet, or host unavailable. "
                "The owner must confirm this device on the host first.")
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
