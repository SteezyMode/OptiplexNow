#!/usr/bin/python3
"""Owner-only GPU power window, using the existing approved admin SSH account.

The remote script is streamed over SSH stdin. It runs as the authorized Linux
user (no sudo escalation). A restricted Games credential cannot run it.
"""
import importlib.util
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

SCRIPT = Path(__file__).resolve().with_name("gpu_power_host.py")
HOST_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z")
USER_RE = re.compile(r"[a-z_][a-z0-9_-]{0,31}\Z", re.I)
MAX_REPLY = 8192


def valid_target(host, user):
    if not isinstance(host, str) or not isinstance(user, str):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not HOST_RE.fullmatch(host) or ".." in host:
            return False
    return bool(USER_RE.fullmatch(user))


def invoke(host, user, action, value=None, *, runner=subprocess.run, source=SCRIPT):
    if not valid_target(host, user) or action not in ("status", "set"):
        raise ValueError("Invalid owner server")
    if action == "set" and (type(value) is not int or not 1 <= value <= 1000):
        raise ValueError("Invalid power limit")
    if action == "status" and value is not None:
        raise ValueError("Unexpected GPU value")
    try:
        program = source.read_bytes()
        if len(program) > 32768:
            raise ValueError("GPU host helper too large")
    except OSError:
        raise RuntimeError("GPU helper missing from NOW installation") from None
    remote = "python3 - status" if action == "status" else f"python3 - set {value}"
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=5", "-o", "ConnectionAttempts=1",
            "-o", "ClearAllForwardings=yes", "-T", "-l", user, host, remote]
    try:
        result = runner(argv, input=program, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, check=False, timeout=12)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("Owner-admin SSH unavailable") from None
    if (result.returncode != 0 or not isinstance(result.stdout, bytes)
            or len(result.stdout) > MAX_REPLY):
        raise RuntimeError("GPU control unavailable: check owner SSH and LACT socket permissions")
    try:
        data = json.loads(result.stdout)
    except (UnicodeDecodeError, ValueError):
        raise RuntimeError("Invalid GPU host response") from None
    if not isinstance(data, dict) or data.get("success") is not True:
        raise RuntimeError("GPU host denied the request")
    return data


class PowerWindow:
    def __init__(self, host, user):
        self.host, self.user = host, user
        self.busy = False
        self.closed = False
        self.bounds = None
        self.window = Gtk.Window(title="NOW | Host GPU")
        self.window.set_default_size(440, 425)
        self.window.connect("destroy", self.on_destroy)
        area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        area.set_border_width(22)
        self.window.add(area)
        heading = Gtk.Label(label="HOST GPU POWER")
        heading.set_xalign(0)
        area.pack_start(heading, False, False, 0)
        self.status = Gtk.Label(label="Checking NVIDIA GPU and LACT…")
        self.status.set_xalign(0)
        self.status.set_line_wrap(True)
        self.status.set_selectable(True)
        area.pack_start(self.status, False, False, 0)
        self.telemetry = Gtk.Label(label="")
        self.telemetry.set_xalign(0)
        self.telemetry.set_line_wrap(True)
        area.pack_start(self.telemetry, False, False, 0)
        self.buttons = Gtk.Box(spacing=6)
        area.pack_start(self.buttons, False, False, 0)
        self.presets = []
        for title in ("POWER SAVER", "BALANCED", "PERFORMANCE"):
            button = Gtk.Button(label=title)
            button.connect("clicked", self.preset_clicked, len(self.presets))
            button.set_sensitive(False)
            self.buttons.pack_start(button, True, True, 0)
            self.presets.append(button)
        self.slider_text = Gtk.Label(label="Custom power limit")
        self.slider_text.set_xalign(0)
        area.pack_start(self.slider_text, False, False, 0)
        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.slider.set_digits(0)
        self.slider.set_sensitive(False)
        area.pack_start(self.slider, False, False, 0)
        self.apply = Gtk.Button(label="APPLY CUSTOM LIMIT")
        self.apply.set_sensitive(False)
        self.apply.connect("clicked", self.apply_clicked)
        area.pack_start(self.apply, False, False, 0)
        self.hint = Gtk.Label(label=(
            "Changes affect the host immediately. Requires separately approved "
            "owner-admin SSH and LACT socket access. No automatic clock or P-state changes."))
        self.hint.set_xalign(0)
        self.hint.set_line_wrap(True)
        area.pack_start(self.hint, False, False, 0)
        self.window.show_all()
        self.work("status")

    def on_destroy(self, *_args):
        self.closed = True
        Gtk.main_quit()

    def set_busy(self, busy):
        self.busy = busy
        available = self.bounds is not None and not busy
        for button in self.presets:
            button.set_sensitive(available)
        self.slider.set_sensitive(available)
        self.apply.set_sensitive(available)

    def work(self, action, value=None):
        if self.busy:
            return
        self.set_busy(True)
        if action == "set":
            self.status.set_text(f"Applying {value} W…")
        def thread():
            try:
                response = invoke(self.host, self.user, action, value)
                error = None
            except (RuntimeError, ValueError) as exc:
                response, error = None, str(exc)
            GLib.idle_add(self.finished, action, response, error)
        threading.Thread(target=thread, daemon=True).start()

    def finished(self, action, response, error):
        if self.closed:
            return False
        if error:
            self.status.set_text(error)
            self.set_busy(False)
            return False
        if action == "set":
            self.status.set_text("Limit confirmed by LACT. Refreshing…")
            self.set_busy(False)
            self.work("status")
            return False
        gpu = response["gpu"]
        limit = response["limit_w"]
        low, high = response.get("min_w"), response.get("max_w")
        self.telemetry.set_text(
            f'{gpu}\nPower cap: {limit:g} W  |  Maximum: {high:g} W\n'
            f'Power draw: {response.get("draw_w")} W  |  '
            f'Temperature: {response.get("temp_c")} °C\n'
            f'Utilization: {response.get("util_pct")} %  |  '
            f'Core clock: {response.get("clock_mhz")} MHz  |  '
            f'P-state: {response.get("pstate")}'
            if high is not None else f'{gpu}\nPower cap: {limit:g} W')
        if (response.get("control_available") and
                isinstance(low, (int, float)) and isinstance(high, (int, float)) and
                1 <= low < high):
            self.bounds = (int(math.ceil(low)), int(math.floor(high)))
            if self.bounds[0] > self.bounds[1]:
                self.bounds = None
            if self.bounds:
                minimum, maximum = self.bounds
                self.slider.set_range(minimum, maximum)
                self.slider.set_value(max(minimum, min(maximum, round(limit))))
                self.status.set_text("LACT available. Select a preset or an exact cap.")
            else:
                self.status.set_text("Hardware reports no adjustable whole-watt range.")
        else:
            self.bounds = None
            self.status.set_text("Monitoring only: LACT is unavailable or access is denied.")
        self.set_busy(False)
        return False

    def preset_clicked(self, _button, index):
        if self.bounds is None:
            return
        minimum, maximum = self.bounds
        # Conservative, deterministic profile values, constrained by GPU limits.
        choices = (minimum, round(minimum + (maximum - minimum) * 0.55), maximum)
        self.work("set", choices[index])

    def apply_clicked(self, _button):
        if self.bounds is not None:
            self.work("set", int(self.slider.get_value()))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or not valid_target(*argv):
        return 2
    Gtk.init([])
    PowerWindow(*argv)
    Gtk.main()
    return 0


if __name__ == "__main__":
    import math
    sys.exit(main())
