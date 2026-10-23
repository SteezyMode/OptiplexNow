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
from owner_access import paired_client_ids
from wolf_docker_adapter import WolfDockerAPI


class OwnerApprovals:
    def __init__(self):
        self.closed = False
        self.running = False
        self.requests = []
        self.clients = []
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
            label="Approve only your own trusted device. Confirm the six-digit "
                  "request code on that client's screen, then independently "
                  "identify its Wolf/Moonlight paired client ID. Never infer "
                  "device identity from IP address or machine name.")
        explanation.set_xalign(0)
        explanation.set_line_wrap(True)
        box.pack_start(explanation, False, False, 0)
        self.request_combo = Gtk.ComboBoxText()
        self.client_combo = Gtk.ComboBoxText()
        for title, widget in (("PENDING DEVICE REQUEST", self.request_combo),
                              ("VERIFIED WOLF CLIENT ID", self.client_combo)):
            text = Gtk.Label(label=title)
            text.set_xalign(0)
            box.pack_start(text, False, False, 0)
            box.pack_start(widget, False, False, 0)
        code_label = Gtk.Label(label="CODE SHOWN ON THE REQUESTING DEVICE")
        code_label.set_xalign(0)
        box.pack_start(code_label, False, False, 0)
        self.code = Gtk.Entry()
        self.code.set_max_length(6)
        self.code.set_placeholder_text("Six digits from requesting device")
        box.pack_start(self.code, False, False, 0)
        self.verified = Gtk.CheckButton(
            label="I compared the code AND independently verified this Wolf device ID")
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
        clients = paired_client_ids(wolf("GET", "/api/v1/clients"))
        sessions = wolf("GET", "/api/v1/sessions")
        if not isinstance(sessions, dict) or sessions.get("success") is not True:
            raise ValueError("Session inventory unavailable")
        active = {x.get("client_id") for x in sessions.get("sessions", [])
                  if isinstance(x, dict)}
        return requests, sorted(clients), active

    def refresh(self, *_):
        self.status.set_text("Reading host-local pending requests and paired Wolf devices...")
        self.job(self.read_host, self.refreshed)

    def refreshed(self, reply, error):
        self.request_combo.remove_all()
        self.client_combo.remove_all()
        self.requests, self.clients = [], []
        self.verified.set_active(False)
        if error:
            self.status.set_text(
                "Host owner enrollment unavailable. Verify the local owner "
                "broker config and Wolf permissions. No changes made.")
            return
        self.requests, self.clients, active = reply
        for index, r in enumerate(self.requests):
            self.request_combo.append_text(
                f"{r['code']}  |  fingerprint {r['fingerprint']}  "
                f"|  expires in {r['seconds_remaining']}s")
        for client in self.clients:
            self.client_combo.append_text(
                client + ("  (active stream)" if client in active else ""))
        self.status.set_text(
            f"{len(self.requests)} pending request(s); {len(self.clients)} paired "
            "Wolf device(s). Compare the client screen before approving.")

    def approve(self, *_):
        request_index = self.request_combo.get_active()
        client_index = self.client_combo.get_active()
        typed = self.code.get_text()
        if (request_index < 0 or client_index < 0 or
                request_index >= len(self.requests) or
                client_index >= len(self.clients) or
                not self.verified.get_active() or
                typed != self.requests[request_index]["code"]):
            self.status.set_text(
                "Select the request, select the VERIFIED Wolf device, "
                "type the exact matching code and check the confirmation.")
            return
        request = self.requests[request_index]
        client = self.clients[client_index]
        dialog = Gtk.MessageDialog(
            transient_for=self.window, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text="Grant owner Games and Downloads access?")
        dialog.format_secondary_text(
            f"Restrict key fingerprint {request['fingerprint']} to Wolf "
            f"device {client}. This modifies the local owner policy and "
            "authorized_keys, preserving existing access. Do not approve "
            "unless you physically verified this same device.")
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
