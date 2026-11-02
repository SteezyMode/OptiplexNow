#!/usr/bin/env python3
"""One-track, local-only Bruiser Music playback worker.

stdin: initial "api_key=...&username=...\n" (never argv/env), then a bounded
whitelist of commands: PAUSE, RESUME, STOP.
stdout: single-word events BUFFERING, PLAYING, PAUSED, ENDED, STOPPED, ERROR.

OpenSubsonic is queried by authenticated POST with redirects and ambient HTTP
proxies disabled. The response's audio bytes feed mpv through an anonymous
pipe; neither credentials nor a stream URL are passed to the decoder. mpv IPC
lives inside a private 0700 directory and is used only by this worker.
"""
from __future__ import annotations

import json
import os
import select
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs

from music_subsonic import MusicTransportError, _bounded_text, _post, endpoint_for

AUTH_MAX = 4096
CONTROL_MAX = 32
MPV_START_TIMEOUT = 5.0


class PlaybackError(Exception):
    """Safe error, never includes authentication material."""


def read_auth(stream) -> dict[str, str]:
    raw = stream.readline(AUTH_MAX + 1)
    if not raw.endswith(b"\n") or len(raw) > AUTH_MAX:
        raise PlaybackError("Invalid playback authentication.")
    try:
        values = parse_qs(raw[:-1].decode("utf-8"), strict_parsing=True,
                          keep_blank_values=True, max_num_fields=2)
    except (ValueError, UnicodeError) as exc:
        raise PlaybackError("Invalid playback authentication.") from exc
    if set(values) != {"api_key", "username"} or any(len(x) != 1 for x in values.values()):
        raise PlaybackError("Invalid playback authentication.")
    key, username = values["api_key"][0], values["username"][0]
    try:
        _bounded_text(key, "app password", 1024)
        if username:
            _bounded_text(username, "username", 128)
    except MusicTransportError as exc:
        raise PlaybackError("Invalid playback authentication.") from exc
    # DroppedNeedle rejects apiKey combined with u. The username remains
    # local-only context; the revocable app password identifies the account.
    return {"apiKey": key}


def socket_command(path: str, pause: bool) -> bool:
    """Send one exact mpv property command, never an arbitrary remote command."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(0.8)
            conn.connect(path)
            payload = json.dumps(
                {"command": ["set_property", "pause", pause]},
                separators=(",", ":")
            ).encode() + b"\n"
            conn.sendall(payload)
            answer = b""
            while b"\n" not in answer and len(answer) < 4096:
                chunk = conn.recv(4096 - len(answer))
                if not chunk:
                    break
                answer += chunk
            result = json.loads(answer.split(b"\n", 1)[0])
            return result.get("error") == "success"
    except (OSError, ValueError):
        return False


def socket_volume(path: str, level: int) -> bool:
    """Set only local mpv volume. Arbitrary IPC commands are prohibited."""
    if type(level) is not int or level < 0 or level > 100:
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(0.8)
            conn.connect(path)
            command = json.dumps(
                {"command": ["set_property", "volume", level]},
                separators=(",", ":")
            ).encode() + b"\n"
            conn.sendall(command)
            answer = b""
            while b"\n" not in answer and len(answer) < 4096:
                chunk = conn.recv(4096 - len(answer))
                if not chunk:
                    break
                answer += chunk
            result = json.loads(answer.split(b"\n", 1)[0])
            return result.get("error") == "success"
    except (OSError, ValueError):
        return False


def _parent_exit_signal():
    """Linux: kill the decoder if the worker is forcibly terminated."""
    import ctypes
    parent_pid = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl(1, signal.SIGTERM, 0, 0, 0)  # PR_SET_PDEATHSIG
    if os.getppid() != parent_pid:
        os._exit(1)


def stream_audio(server: str, auth: dict[str, str], track_id: str, decoder,
                 send, done: threading.Event, failure: list[str],
                 pause_state: threading.Event | None = None,
                 pause_guard: threading.Lock | None = None):
    try:
        with _post(server, "stream", auth, {"id": track_id, "format": "raw"}) as response:
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if (not mime or mime.startswith("text/") or "json" in mime or "xml" in mime or
                    "html" in mime):
                raise PlaybackError("Music server did not return an audio stream.")
            first = True
            while not done.is_set():
                data = response.read(64 * 1024)
                if not data:
                    break
                if decoder.poll() is not None:
                    raise PlaybackError("Audio decoder exited before the stream finished.")
                try:
                    decoder.stdin.write(data)
                    decoder.stdin.flush()
                except (BrokenPipeError, OSError) as exc:
                    raise PlaybackError("Audio decoder rejected the stream.") from exc
                if first:
                    # Serialize first-audio and command-state notifications.
                    # Otherwise a rapid PAUSE during buffering could be
                    # followed by a stale PLAYING event.
                    if pause_guard is not None:
                        with pause_guard:
                            send("PAUSED" if pause_state and pause_state.is_set()
                                 else "PLAYING")
                    else:
                        send("PAUSED" if pause_state and pause_state.is_set()
                             else "PLAYING")
                    first = False
            if first:
                raise PlaybackError("Music stream was empty.")
    except (MusicTransportError, PlaybackError, OSError) as exc:
        failure.append(type(exc).__name__)
    finally:
        try:
            decoder.stdin.close()
        except OSError:
            pass
        done.set()


def run(server: str, track_id: str, credential_stream, command_stream, output,
        *, mpv_binary: str | None = None, initial_volume: int = 75) -> int:
    # A configured server address and track ID only; no secrets in argv.
    if type(initial_volume) is not int or not 0 <= initial_volume <= 100:
        output.write("ERROR\n")
        output.flush()
        return 2
    try:
        endpoint_for(server, "stream")
        _bounded_text(track_id, "track ID", 512)
        auth = read_auth(credential_stream)
    except (MusicTransportError, PlaybackError):
        output.write("ERROR\n")
        output.flush()
        return 2
    mpv = mpv_binary or shutil.which("mpv")
    if not mpv:
        output.write("ERROR\n")
        output.flush()
        return 3

    output_lock = threading.Lock()
    def send(value: str):
        with output_lock:
            output.write(value + "\n")
            output.flush()

    done = threading.Event()
    failure: list[str] = []
    stopped = False
    paused = False
    pause_state = threading.Event()
    pause_guard = threading.Lock()

    # mkdtemp uses mode 0700, so no other user can reach mpv's IPC socket.
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        try:
            st = os.stat(runtime)
            if st.st_uid != os.getuid() or (st.st_mode & 0o077):
                runtime = None
        except OSError:
            runtime = None
    with tempfile.TemporaryDirectory(prefix="bruiser-music-", dir=runtime) as directory:
        ipc = os.path.join(directory, "control.sock")
        argv = [
            mpv, "--no-config", "--no-video", "--no-terminal",
            "--really-quiet", "--audio-display=no",
            "--volume=" + str(initial_volume),
            "--input-ipc-server=" + ipc, "--", "-"
        ]
        try:
            decoder = subprocess.Popen(
                argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, close_fds=True,
                preexec_fn=_parent_exit_signal if sys.platform.startswith("linux") else None
            )
        except (OSError, ValueError):
            send("ERROR")
            return 3

        sender = threading.Thread(target=stream_audio,
            args=(server, auth, track_id, decoder, send, done, failure,
                  pause_state, pause_guard),
            daemon=True)
        try:
            send("BUFFERING")
            sender.start()
            started = time.monotonic()
            while True:
                if decoder.poll() is not None:
                    if stopped:
                        send("STOPPED")
                    elif failure or decoder.returncode != 0:
                        send("ERROR")
                    else:
                        send("ENDED")
                    return 0 if stopped or (not failure and decoder.returncode == 0) else 2
                if failure and done.is_set():
                    send("ERROR")
                    return 2
                if not os.path.exists(ipc) and time.monotonic() - started > MPV_START_TIMEOUT:
                    send("ERROR")
                    return 3
                ready, _, _ = select.select([command_stream], [], [], 0.15)
                if not ready:
                    continue
                command = command_stream.readline(CONTROL_MAX + 1)
                if not command:
                    stopped = True
                    send("STOPPED")
                    return 0
                if len(command) > CONTROL_MAX:
                    continue
                action = command.strip().decode("ascii", errors="ignore")
                if action == "STOP":
                    stopped = True
                    send("STOPPED")
                    return 0
                if action.startswith("VOLUME "):
                    digits = action[7:]
                    if digits.isascii() and digits.isdecimal() and len(digits) <= 3:
                        level = int(digits)
                        if level <= 100 and os.path.exists(ipc):
                            socket_volume(ipc, level)
                    continue
                if action not in ("PAUSE", "RESUME") or not os.path.exists(ipc):
                    continue
                wanted_paused = action == "PAUSE"
                if wanted_paused != paused and socket_command(ipc, wanted_paused):
                    with pause_guard:
                        paused = wanted_paused
                        if paused:
                            pause_state.set()
                        else:
                            pause_state.clear()
                        send("PAUSED" if paused else "PLAYING")
        finally:
            done.set()
            if decoder.poll() is None:
                decoder.terminate()
                try:
                    decoder.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    decoder.kill()
                    decoder.wait(timeout=2.0)
            # Stream thread is daemonized to avoid prolonged shutdown after a
            # network stall; no credentials remain in a persistent process.


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) != 3:
        return 2
    server, track_id, raw_volume = argv
    if not raw_volume.isascii() or not raw_volume.isdecimal() or len(raw_volume) > 3:
        return 2
    volume = int(raw_volume)
    if volume > 100:
        return 2
    try:
        # Use the unbuffered file object for BOTH auth and later commands.
        # BufferedReader.readline() can prefetch a PAUSE/STOP line and then
        # select() would see an empty kernel pipe despite buffered commands.
        channel = sys.stdin.buffer.raw
        return run(server, track_id, channel, channel, sys.stdout,
                   initial_volume=volume)
    except (OSError, ValueError):
        print("ERROR", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
