#!/usr/bin/python3
"""Host-local GTK approval of staged owner device credentials (owner pilot).

The operator explicitly checks the code on the requesting client's screen
and identifies the SAME Wolf-paired client independently. Merely being on
the tailnet or in Wolf's paired list does not constitute approval.
"""
from pathlib import Path
import sys
from threading import Thread

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

BRIDGE = Path(__file__).resolve().parent / "owner-bridge"
sys.path[:0] = [str(BRIDGE / "src"), str(BRIDGE / "server")]
from owner_enrollment import (_read_private_config, pending_requests,
                              approve_request)
from owner_access import PolicyError
from tailnet_wolf_review import single_active_wolf_ui
from wolf_docker_adapter import WolfDockerAPI


class OwnerApprovals:
    def __init__(self):
        self.closed = False
        self.running = False
        self.requests = []
        self.candidates = {}
        self.window = Gtk.Window(title="NOW | Owner Device Approvals")
        self.window.set_default_size(540, 440)
        self.window.connect("destroy", self.destroy)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11)
        box.set_border_width(18)
        self.window.add(box)
        title = Gtk.Label(label="APPROVE OWNER DEVICE")
        title.set_xalign(0)
        box.pack_start(title, False, False, 0)
        explanation = Gtk.Label(
            label="Match the six-digit code shown on the requesting computer. "
                  "The host automatically checks a unique live paired Wolf UI "
                  "session against that request's observed connection source. "
                  "No selectable numeric Wolf identities.")
        explanation.set_xalign(0)
        explanation.set_line_wrap(True)
        box.pack_start(explanation, False, False, 0)
        self.request_combo = Gtk.ComboBoxText()
        text = Gtk.Label(label="PENDING DEVICE REQUEST")
        text.set_xalign(0)
        box.pack_start(text, False, False, 0)
        box.pack_start(self.request_combo, False, False, 0)
        self.request_combo.connect("changed", self.selection_changed)
        self.identity = Gtk.Label(label="Verified Wolf session: none")
        self.identity.set_xalign(0)
        self.identity.set_line_wrap(True)
        box.pack_start(self.identity, False, False, 0)
        code_label = Gtk.Label(label="CODE SHOWN ON THE REQUESTING DEVICE")
        code_label.set_xalign(0)
        box.pack_start(code_label, False, False, 0)
        self.code = Gtk.Entry()
        self.code.set_max_length(6)
        self.code.set_placeholder_text("Six digits from requesting device")
        box.pack_start(self.code, False, False, 0)
        self.verified = Gtk.CheckButton(
            label="I verified this request/code and the correct device is streaming Wolf UI")
        box.pack_start(self.verified, False, False, 0)
        self.status = Gtk.Label(label="No host data loaded.")
        self.status.set_xalign(0)
        self.status.set_line_wrap(True)
        box.pack_start(self.status, False, False, 0)
        row = Gtk.Box(spacing=9)
        box.pack_start(row, False, False, 0)
        self.refresh_button = Gtk.Button(label="REFRESH HOST DEVICES")
        self.refresh_button.connect("clicked", self.refresh)
        row.pack_start(self.refresh_button, True, True, 0)
        self.approve_button = Gtk.Button(label="APPROVE SELECTED DEVICE")
        self.approve_button.connect("clicked", self.approve)
        row.pack_start(self.approve_button, True, True, 0)
        self.window.show_all()
        self.refresh()

    def destroy(self, *_):
        self.closed = True
        Gtk.main_quit()

    def job(self, task, done):
        if self.running:
            return
        self.running = True
        self.approve_button.set_sensitive(False)
        self.refresh_button.set_sensitive(False)

        def perform():
            try:
                reply, error = task(), None
            except Exception:
                reply, error = None, True
            GLib.idle_add(self.finish, done, reply, error)

        Thread(target=perform, daemon=True).start()

    def finish(self, done, reply, error):
        if self.closed:
            return False
        self.running = False
        self.approve_button.set_sensitive(True)
        self.refresh_button.set_sensitive(True)
        done(reply, error)
        return False

    @staticmethod
    def read_host():
        state = _read_private_config()["state_dir"]
        requests = pending_requests(state)
        wolf = WolfDockerAPI()
        candidates = {}
        for request in requests:
            source = request.get("source_ip")
            if source:
                try:
                    candidates[request["request_id"]] = single_active_wolf_ui(
                        wolf, expected_source=source)
                except (PolicyError, OSError, KeyError, ValueError):
                    pass
        return requests, candidates

    def refresh(self, *_):
        self.status.set_text("Reading host-local pending requests and paired Wolf devices...")
        self.job(self.read_host, self.refreshed)

    def refreshed(self, reply, error):
        self.request_combo.remove_all()
        self.requests, self.candidates = [], {}
        self.verified.set_active(False)
        if error:
            self.status.set_text(
                "Host owner enrollment unavailable. Verify the local owner "
                "broker config and Wolf permissions. No changes made.")
            return
        self.requests, self.candidates = reply
        for index, r in enumerate(self.requests):
            self.request_combo.append_text(
                f"{r['code']}  |  fingerprint {r['fingerprint']}  "
                f"|  expires in {r['seconds_remaining']}s")
        self.status.set_text(
            f"{len(self.requests)} pending request(s), "
            f"{len(self.candidates)} with matching live Wolf sessions. "
            "Select the request. There is no manual Wolf identity selection.")
        self.selection_changed()

    def selection_changed(self, *_):
        ix = self.request_combo.get_active()
        self.verified.set_active(False)
        request = self.requests[ix] if 0 <= ix < len(self.requests) else None
        client = (self.candidates.get(request["request_id"])
                  if request else None)
        self.identity.set_text(
            "Verified Wolf session: " + client if client else
            "NO MATCH. Reconnect Wolf UI from the requesting device using "
            "the same network address/path as enrollment, then Refresh.")

    def approve(self, *_):
        request_index = self.request_combo.get_active()
        typed = self.code.get_text()
        request = (self.requests[request_index]
                   if 0 <= request_index < len(self.requests) else None)
        client = (self.candidates.get(request["request_id"])
                  if request else None)
        if (not request or not client or
                not self.verified.get_active() or
                typed != request["code"]):
            self.status.set_text(
                "Approval blocked. Select the staged request, verify its "
                "code and keep its matching Wolf UI stream active. "
                "No other Wolf ID can be selected.")
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.window, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="Grant owner Games and Downloads access?")
        dialog.format_secondary_text(
            f"Restrict key fingerprint {request['fingerprint']} to Wolf "
            f"device {client}. This modifies the local owner policy and "
            "authorized_keys, preserving existing access. The host "
            "will recheck its network origin and live Wolf identity "
            "before changing either file.")
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Approve Device", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        self.status.set_text("Applying the explicitly approved host binding...")
        def task():
            state = _read_private_config()["state_dir"]
            return approve_request(state, request["request_id"], typed, client,
                                   confirmed=True)
        self.job(task, self.approved)

    def approved(self, reply, error):
        if error or not reply or not reply.get("success"):
            self.status.set_text(
                "Approval refused or incomplete. Inspect host state before "
                "trying again. No Steam or Docker operation was requested.")
            return
        self.status.set_text(
            "Device approved. Return to the client and click VERIFY ACCESS.")
        self.verified.set_active(False)
        self.code.set_text("")


if __name__ == "__main__":
    Gtk.init([])
    OwnerApprovals()
    Gtk.main()
