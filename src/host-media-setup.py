#!/usr/bin/python3
"""Host-only Videos setup window: review local Jellyfin and opt into routing.

Not a Jellyfin installer or a client enrollment interface. Any approved
routing file is first-write-only and requires a real local Jellyfin probe.
"""
import json
import subprocess
import sys
from threading import Thread

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

HELPER = "/usr/lib/optiplex-now/host_media_adoption.py"
STATUS = frozenset(("local_jellyfin_found", "already_configured",
                    "not_verified", "unsafe_config", "route_created"))


class VideosSetup:
    def __init__(self):
        self.busy = False
        self.can_approve = False
        self.window = Gtk.Window(title="OptiPlex NOW | Videos Host Setup")
        self.window.set_default_size(550, 420)
        self.window.connect("destroy", self.on_destroy)
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        panel.set_border_width(20)
        self.window.add(panel)
        heading = Gtk.Label(label="VIDEOS | USE AN EXISTING JELLYFIN")
        heading.set_xalign(0)
        panel.pack_start(heading, False, False, 0)
        info = Gtk.Label(label=(
            "Find a Jellyfin instance on this host without changing it. "
            "You can approve a same-host address scheme, port and path for "
            "other NOW clients. Your library, accounts, Docker and Caddy "
            "will not be changed. This does not install Jellyfin."))
        info.set_xalign(0)
        info.set_line_wrap(True)
        panel.pack_start(info, False, False, 0)
        self.status = Gtk.Label(label="NOT CHECKED")
        self.status.set_xalign(0)
        self.status.set_line_wrap(True)
        panel.pack_start(self.status, False, False, 0)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        panel.pack_start(grid, False, False, 0)
        self.scheme = Gtk.ComboBoxText()
        self.scheme.append_text("http")
        self.scheme.append_text("https")
        self.scheme.set_active(0)
        grid.attach(Gtk.Label(label="Published scheme"), 0, 0, 1, 1)
        grid.attach(self.scheme, 1, 0, 1, 1)
        self.port = Gtk.Entry()
        self.port.set_text("8096")
        self.port.set_max_length(5)
        grid.attach(Gtk.Label(label="Port"), 0, 1, 1, 1)
        grid.attach(self.port, 1, 1, 1, 1)
        self.path = Gtk.Entry()
        self.path.set_text("/")
        self.path.set_max_length(50)
        self.path.set_placeholder_text("/ or /jellyfin")
        grid.attach(Gtk.Label(label="Base path"), 0, 2, 1, 1)
        grid.attach(self.path, 1, 2, 1, 1)

        hint = Gtk.Label(label=(
            "No hostname or public URL is accepted. Client verification "
            "must still succeed; an HTTPS certificate must match the host "
            "the client uses. A custom Caddy domain is not automatically adopted."))
        hint.set_xalign(0)
        hint.set_line_wrap(True)
        panel.pack_start(hint, False, False, 0)

        pilot = Gtk.Box(spacing=8)
        panel.pack_end(pilot, False, False, 0)
        fresh = Gtk.Button(label="SET UP NEW JELLYFIN ON A CLEAN HOST...")
        fresh.connect("clicked", self.open_clean_host_setup)
        pilot.pack_start(fresh, False, False, 0)

        row = Gtk.Box(spacing=8)
        panel.pack_end(row, False, False, 0)
        self.check = Gtk.Button(label="CHECK LOCAL JELLYFIN")
        self.check.connect("clicked", self.review)
        row.pack_start(self.check, True, True, 0)
        self.approve = Gtk.Button(label="APPROVE EXISTING ROUTE...")
        self.approve.set_sensitive(False)
        self.approve.connect("clicked", self.confirm)
        row.pack_start(self.approve, True, True, 0)
        close = Gtk.Button(label="CLOSE")
        close.connect("clicked", lambda *_: self.window.destroy())
        row.pack_start(close, False, False, 0)
        self.window.show_all()
        GLib.idle_add(self.review)

    def open_clean_host_setup(self, *_):
        # A separate nonprivileged window. Never start the installer from a
        # Videos client, from review, or before deliberate human approval.
        try:
            subprocess.Popen(
                [sys.executable,
                 "/usr/lib/optiplex-now/host-jellyfin-new-ui.py"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        except OSError:
            self.status.set_text(
                "CLEAN-HOST JELLYFIN PILOT UI NOT INSTALLED. NO CHANGES MADE.")

    def on_destroy(self, *_):
        Gtk.main_quit()

    def set_busy(self, busy):
        self.busy = busy
        self.check.set_sensitive(not busy)
        self.approve.set_sensitive(not busy and self.can_approve)
        self.scheme.set_sensitive(not busy and self.can_approve)
        self.port.set_sensitive(not busy and self.can_approve)
        self.path.set_sensitive(not busy and self.can_approve)

    def dispatch(self, args, done):
        self.set_busy(True)
        def run():
            result = None
            try:
                p = subprocess.run(
                    [sys.executable, HELPER, *args], capture_output=True,
                    timeout=9, text=True, check=False)
                if p.returncode == 0 and len(p.stdout) < 4096:
                    result = json.loads(p.stdout)
                    if not isinstance(result, dict) or result.get("status") not in STATUS:
                        result = None
            except (OSError, subprocess.TimeoutExpired, ValueError):
                pass
            GLib.idle_add(done, result)
        Thread(target=run, daemon=True).start()

    def review(self, *_):
        if self.busy:
            return
        self.can_approve = False
        self.status.set_text("CHECKING EXISTING LOCAL JELLYFIN...")
        self.dispatch(["--inspect"], self.review_done)

    def review_done(self, result):
        state = result.get("status") if result else "unavailable"
        if state == "local_jellyfin_found":
            self.can_approve = True
            self.status.set_text(
                "LOCAL JELLYFIN VERIFIED. Confirm its same-host published "
                "port/path before approval. Remote client playback is NOT yet verified.")
        elif state == "already_configured":
            self.can_approve = False
            route = result.get("endpoint") or {}
            self.status.set_text(
                "OWNER ROUTE ALREADY CONFIGURED. Existing approval preserved. "
                "Changing it requires a separate, explicitly reviewed operation.")
            if (isinstance(route, dict) and
                    route.get("scheme") in ("http", "https") and
                    type(route.get("port")) is int and
                    isinstance(route.get("base_path"), str)):
                self.scheme.set_active(0 if route["scheme"] == "http" else 1)
                self.port.set_text(str(route["port"]))
                self.path.set_text(route["base_path"])
        elif state == "unsafe_config":
            self.can_approve = False
            self.status.set_text(
                "EXISTING ROUTE IS INVALID OR UNSAFE. NO CHANGES MADE. "
                "Review the owner config before further action.")
        else:
            self.can_approve = False
            self.status.set_text(
                "LOCAL JELLYFIN NOT VERIFIED ON 127.0.0.1:8096. "
                "No adoption is available. Existing services remain untouched.")
        self.set_busy(False)
        return False

    def confirm(self, *_):
        if self.busy or not self.can_approve:
            return
        scheme = self.scheme.get_active_text()
        port = self.port.get_text().strip()
        base = self.path.get_text().strip()
        if (scheme not in ("http", "https") or
                not port.isascii() or not port.isdecimal() or
                len(port) > 5 or not 1 <= int(port) <= 65535 or
                not base.startswith("/") or len(base) > 49 or
                any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                    for c in base[1:])):
            self.status.set_text(
                "INVALID SAME-HOST ROUTE. Use HTTP/HTTPS, port 1–65535, "
                "and / or one short path such as /jellyfin.")
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.window, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="Approve this existing Jellyfin route?")
        dialog.format_secondary_text(
            f"Publish {scheme} on port {port} at {base} to authorized "
            "NOW clients of this SAME host. This saves only a private "
            "owner route file, does not test external reachability, "
            "and does not change Jellyfin or Caddy.")
        dialog.add_button("CANCEL", Gtk.ResponseType.CANCEL)
        dialog.add_button("APPROVE ROUTE", Gtk.ResponseType.OK)
        choice = dialog.run()
        dialog.destroy()
        if choice != Gtk.ResponseType.OK:
            return
        self.status.set_text("SAVING OWNER-APPROVED ROUTE...")
        self.dispatch(["--approve-existing", "--scheme", scheme,
                       "--port", port, "--base-path", base,
                       "--confirm-owner"], self.approved)

    def approved(self, result):
        self.can_approve = False
        self.set_busy(False)
        if result and result.get("status") == "route_created":
            self.status.set_text(
                "OWNER ROUTE CREATED. No service was changed. "
                "Verify from an enrolled client before claiming Videos works.")
        else:
            self.status.set_text(
                "APPROVAL REFUSED OR STALE. No existing config overwritten. "
                "CHECK LOCAL JELLYFIN again before further action.")
        return False


def main():
    Gtk.init([])
    VideosSetup()
    Gtk.main()


if __name__ == "__main__":
    main()
