#!/usr/bin/env python3
"""Host-local NVIDIA/LACT power bridge, executed over existing owner-admin SSH.

The client supplies this audited script on SSH stdin to 'python3 -'. No host
installation, privileged daemon, listener, sudoers entry or GPU mutation occurs
unless an authorized owner explicitly requests a power-cap change.
"""
import csv
import io
import json
import math
import socket
import subprocess
import sys

LACT_SOCKET = "/run/lactd.sock"
GPU_FIELDS = ("name,power.draw,power.limit,power.min_limit,power.max_limit,"
              "temperature.gpu,utilization.gpu,clocks.gr,pstate")


class GpuPowerError(Exception):
    pass


def number(value):
    try:
        result = float(value.strip())
        return result if math.isfinite(result) and result >= 0 else None
    except (AttributeError, ValueError):
        return None


def parse_gpu(text):
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except (TypeError, csv.Error):
        rows = []
    if len(rows) != 1 or len(rows[0]) != 9:
        raise GpuPowerError("A single NVIDIA GPU is required")
    name, draw, limit, minimum, maximum, temp, util, clock, pstate = (
        item.strip() for item in rows[0])
    current, low, high = number(limit), number(minimum), number(maximum)
    if not name or current is None:
        raise GpuPowerError("NVIDIA power information unavailable")
    bounds = (low is not None and high is not None and
              1 <= low < high <= 1000 and low <= current + 1 <= high + 1)
    return {"gpu": name[:120], "draw_w": number(draw),
            "limit_w": current, "min_w": low if bounds else None,
            "max_w": high if bounds else None, "temp_c": number(temp),
            "util_pct": number(util), "clock_mhz": number(clock),
            "pstate": pstate[:16]}


def probe_gpu(runner=subprocess.run):
    try:
        result = runner(["nvidia-smi", "--query-gpu=" + GPU_FIELDS,
                         "--format=csv,noheader,nounits"],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise GpuPowerError("NVIDIA monitoring unavailable") from None
    if result.returncode or not isinstance(result.stdout, bytes) or len(result.stdout) > 2048:
        raise GpuPowerError("NVIDIA monitoring unavailable")
    return parse_gpu(result.stdout.decode("utf-8", errors="replace"))


def rpc(command, args=None, *, socket_factory=socket.socket):
    request = {"command": command}
    if args is not None:
        request["args"] = args
    sock = socket_factory(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.settimeout(2.5)
        sock.connect(LACT_SOCKET)
        sock.sendall((json.dumps(request, separators=(",", ":")) + "\n").encode())
        body = bytearray()
        while b"\n" not in body:
            chunk = sock.recv(4096)
            if not chunk:
                raise GpuPowerError("LACT response incomplete")
            body.extend(chunk)
            if len(body) > 65536:
                raise GpuPowerError("LACT response oversized")
    except (OSError, socket.timeout):
        raise GpuPowerError("LACT socket unavailable or permission denied") from None
    finally:
        sock.close()
    try:
        reply = json.loads(bytes(body).split(b"\n", 1)[0])
    except (ValueError, UnicodeDecodeError):
        raise GpuPowerError("Invalid LACT response") from None
    if not isinstance(reply, dict) or reply.get("status") != "ok":
        raise GpuPowerError("LACT rejected the request")
    return reply.get("data")


def gpu_id(call=rpc):
    devices = call("list_devices")
    if not isinstance(devices, list) or len(devices) > 32:
        raise GpuPowerError("LACT device inventory unavailable")
    matches = [device["id"] for device in devices if isinstance(device, dict)
               and isinstance(device.get("id"), str)
               and device["id"].lower().startswith("10de:")]
    if len(matches) != 1:
        raise GpuPowerError("A single LACT-managed NVIDIA GPU is required")
    return matches[0]


def inspect(*, probe=probe_gpu, call=rpc):
    details = probe()
    details["control_available"] = False
    try:
        identifier = gpu_id(call)
        config = call("get_gpu_config", {"id": identifier})
        if not isinstance(config, dict):
            raise GpuPowerError("LACT configuration unavailable")
        details["control_available"] = details["min_w"] is not None
        details["configured_w"] = number(config.get("power_cap"))
    except GpuPowerError:
        details["configured_w"] = None
    return {"success": True, "status": "ready", **details}


def set_cap(watts, *, probe=probe_gpu, call=rpc):
    if type(watts) is not int or not (1 <= watts <= 1000):
        raise GpuPowerError("Invalid power limit")
    details = probe()
    low, high = details["min_w"], details["max_w"]
    if low is None or not low <= watts <= high:
        raise GpuPowerError("Power limit is outside device-supported bounds")
    identifier = gpu_id(call)
    config = call("get_gpu_config", {"id": identifier})
    if not isinstance(config, dict) or "power_cap" not in config:
        raise GpuPowerError("LACT power control unavailable")
    updated = dict(config)
    updated["power_cap"] = float(watts)
    # Keep every other LACT setting intact, including fan and clock settings.
    call("set_gpu_config", {"id": identifier, "config": updated})
    # LACT rolls unconfirmed edits back after ~5 seconds. Confirm immediately;
    # do not retry an ambiguous state-changing command.
    call("confirm_pending_config", {"command": "confirm"})
    return {"success": True, "status": "confirmed", "requested_w": watts}


def handle(argv, *, probe=probe_gpu, call=rpc):
    if argv == ["status"]:
        return inspect(probe=probe, call=call)
    if len(argv) == 2 and argv[0] == "set" and argv[1].isdigit():
        return set_cap(int(argv[1]), probe=probe, call=call)
    raise GpuPowerError("Unsupported GPU action")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        response = handle(argv)
        print(json.dumps(response, separators=(",", ":")))
        return 0
    except (GpuPowerError, ValueError):
        print('{"success":false,"status":"unavailable"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
