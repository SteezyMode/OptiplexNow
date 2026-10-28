#!/usr/bin/python3
"""Host-only clean Jellyfin pilot GUI; no writes until explicit pkexec install.

This is not existing-server adoption. It requires a verified immutable
upstream image digest, an existing owner-owned media folder, Tailscale and
Docker Compose, with a fresh local administrator check before installation.
"""
import json
import os
import re
import subprocess
import sys
from threading import Thread

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

HELPER = "/usr/lib/optiplex-now/host_jellyfin_install.py"
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
ALLOWED = ("candidate_after_admin_check", "blocked",
           "running_media_unverified")


class NewJellyfinSetup:
    def __init__(self):
        self.busy = False
        self.eligible = False
        self.checked_values = None
        self.window = Gtk.Window(title="OptiPlex NOW | New Jellyfin Host Pilot")
        self.window.set_default_size(640, 485)
        self.window.connect("destroy", lambda *_: Gtk.main_quit())
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        panel.set_border_width(16)
        self.window.add(panel)
        heading = Gtk.Label(label="NEW JELLYFIN | CLEAN-HOST PILOT")
        heading.set_xalign(0)
        panel.pack_start(heading, False, False, 0)
        intro = Gtk.Label(label=(
            "Only on a clean Linux host with no existing Jellyfin. "
            "Set up the official Jellyfin container with a pinned image, "
            "private config/cache, and an existing media folder mounted "
            "read-only. This is NOT suitable for the working OptiPlex."))
        intro.set_xalign(0)
        intro.set_line_wrap(True)
        panel.pack_start(intro, False, False, 0)

        grid = Gtk.Grid(column_spacing=8, row_spacing=10)
        panel.pack_start(grid, False, False, 0)
        grid.attach(Gtk.Label(label="Media library folder"), 0, 0, 1, 1)
        self.folder = Gtk.FileChooserButton(
            title="Choose an existing owner-owned media folder",
            action=Gtk.FileChooserAction.SELECT_FOLDER)
        self.folder.connect("file-set", self.invalidate)
        grid.attach(self.folder, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label="Jellyfin image SHA256"), 0, 1, 1, 1)
        self.digest = Gtk.Entry()
        self.digest.set_placeholder_text("64 lowercase hex chars; verified upstream image digest")
        self.digest.set_max_length(64)
        self.digest.connect("changed", self.invalidate)
        grid.attach(self.digest, 1, 1, 1, 1)

        self.status = Gtk.Label(label="NOT CHECKED. NOTHING WILL BE INSTALLED.")
        self.status.set_xalign(0)
        self.status.set_line_wrap(True)
        panel.pack_start(self.status, False, False, 0)
        self.info = Gtk.Label(label=(
            "This installs into a separate NOW Jellyfin pilot project. "
            "Requires Docker Engine 28+ because older versions have known "
            "localhost port exposure risks. NOW requests port mappings only "
            "to loopback and this host's Tailscale IPv4, but Docker routing "
            "and real LAN exposure still require physical verification. "
            "No Caddy configuration is changed. "
            "A failed or interrupted install requires manual review."))
        self.info.set_xalign(0)
        self.info.set_line_wrap(True)
        panel.pack_start(self.info, False, False, 0)

        actions = Gtk.Box(spacing=8)
        panel.pack_end(actions, False, False, 0)
        self.check = Gtk.Button(label="CHECK CLEAN-HOST ELIGIBILITY (OS APPROVAL)")
        self.check.connect("clicked", self.check_eligibility)
        actions.pack_start(self.check, True, True, 0)
        self.install = Gtk.Button(label="INSTALL NEW JELLYFIN...")
        self.install.set_sensitive(False)
        self.install.connect("clicked", self.install_clicked)
        actions.pack_start(self.install, True, True, 0)
        close = Gtk.Button(label="CLOSE")
        close.connect("clicked", lambda *_: self.window.destroy())
        actions.pack_end(close, False, False, 0)
        self.window.show_all()

    def invalidate(self, *_):
        self.eligible = False
        self.checked_values = None
        self.install.set_sensitive(False)
        self.status.set_text("SETTINGS CHANGED. RECHECK CLEAN-HOST ELIGIBILITY.")

    def values(self):
        path = self.folder.get_filename()
        digest = self.digest.get_text().strip()
        if not path or not path.startswith("/") or not DIGEST.fullmatch(digest):
            return None
        return (path, digest, str(os.getuid()))

    def set_busy(self, busy):
        self.busy = busy
        self.check.set_sensitive(not busy)
        self.install.set_sensitive(not busy and self.eligible)
        self.folder.set_sensitive(not busy)
        self.digest.set_sensitive(not busy)

    def dispatch(self, argv, done):
        self.set_busy(True)
        def run():
            reply = None
            try:
                p = subprocess.run(
                    ["/usr/bin/pkexec", "/usr/bin/python3", HELPER, *argv],
                    stdin=subprocess.DEVNULL, capture_output=True, text=True,
                    timeout=1200 if "--install" in argv else 35, check=False)
                if p.returncode in (0, 2) and len(p.stdout) < 4096:
                    candidate = json.loads(p.stdout)
                    if (isinstance(candidate, dict) and
                            candidate.get("tool") == "now-jellyfin-clean-host" and
                            candidate.get("status") in ALLOWED):
                        reply = candidate
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
            GLib.idle_add(done, reply)
        Thread(target=run, daemon=True).start()

    def check_eligibility(self, *_):
        if self.busy:
            return
        values = self.values()
        if not values:
            self.status.set_text(
                "CHOOSE AN EXISTING MEDIA FOLDER AND A VERIFIED 64-HEX IMAGE DIGEST.")
            return
        self.eligible = False
        self.checked_values = None
        self.status.set_text("RECHECKING CLEAN-HOST ELIGIBILITY THROUGH OS APPROVAL...")
        self.dispatch(["--check", "--media-path", values[0],
                       "--image-digest", values[1],
                       "--owner-uid", values[2]],
                      lambda result: self.checked(result, values))

    def checked(self, result, values):
        self.eligible = bool(
            result and result.get("status") == "candidate_after_admin_check" and
            self.values() == values)
        self.checked_values = values if self.eligible else None
        self.set_busy(False)
        if self.eligible:
            self.status.set_text(
                "CANDIDATE ONLY. INSTALL RECHECKS STATE BEFORE WRITING. "
                "Runtime video and client access remain unverified.")
        elif result and result.get("status") == "blocked":
            blockers = result.get("blockers")
            if isinstance(blockers, list):
                # Use fixed, bounded diagnostics from the packaged helper.
                hints = "; ".join(str(x)[:100] for x in blockers[:4])
                self.status.set_text("INSTALL BLOCKED: " + hints[:370])
            else:
                self.status.set_text("INSTALL BLOCKED. REVIEW LOCAL STATE.")
        else:
            self.status.set_text("ADMINISTRATOR CHECK CANCELED OR FAILED. NO INSTALL STARTED.")
        return False

    def install_clicked(self, *_):
        values = self.values()
        if self.busy or not self.eligible or not values or values != self.checked_values:
            self.invalidate()
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.window, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="Install a new, separate Jellyfin container on this CLEAN host?")
        dialog.format_secondary_text(
            "This pulls the exact approved Jellyfin image and creates new "
            "persistent private NOW Jellyfin state. The chosen media directory "
            "is mounted READ ONLY. Only loopback and Tailscale mappings "
            "are requested; their actual values are checked after startup. "
            "Network isolation still requires a real-world test. "
            "Do not use on an existing Jellyfin server. If interrupted, DO NOT "
            "retry without inspecting the installation journal and Docker state.")
        dialog.add_button("CANCEL", Gtk.ResponseType.CANCEL)
        dialog.add_button("INSTALL ON THIS HOST", Gtk.ResponseType.OK)
        approved = dialog.run()
        dialog.destroy()
        if approved != Gtk.ResponseType.OK:
            return
        self.eligible = False
        self.checked_values = None
        self.status.set_text("OS AUTHORIZATION REQUESTED. DO NOT RETRY AN INTERRUPTED INSTALL.")
        self.dispatch(["--install", "--media-path", values[0],
                       "--image-digest", values[1],
                       "--owner-uid", values[2],
                       "--confirm", "INSTALL-JELLYFIN"], self.installed)

    def installed(self, result):
        self.set_busy(False)
        if result and result.get("status") == "running_media_unverified":
            self.status.set_text(
                "JELLYFIN CONTAINER STARTED, NOT YET VERIFIED. Complete its "
                "own first-run account setup, then test Videos from an "
                "authorized NOW client before claiming success.")
        else:
            self.status.set_text(
                "INSTALL OUTCOME UNKNOWN OR REFUSED. DO NOT RETRY. "
                "Review the dedicated host journal and Docker project first.")
        return False


def main():
    Gtk.init([])
    NewJellyfinSetup()
    Gtk.main()


if __name__ == "__main__":
    main()
