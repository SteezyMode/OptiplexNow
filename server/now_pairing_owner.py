"""Owner-only Unix socket approval surface for NOW pairing requests.

Not an HTTP service and not a daemon entry point. The future host broker must
construct this with its own PairingRequests queue and retain the same queue for
trusted, independently authenticated pairing requests and native adapters.

Security: Linux SO_PEERCRED + an owner-owned, mode-0700 directory and mode-0600
socket. A *different* Unix UID is denied. Same-UID processes remain trusted;
this is not a security boundary against malware already running as the owner.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import socketserver
import stat
import struct
import sys

SOCKET_NAME = "owner.sock"
MAX_INPUT = 1024
MAX_OUTPUT = 32768
SOCKET_TIMEOUT = 2


def _peer_uid(connection):
    """OS-reported peer credentials; never read identity from command JSON."""
    cred_size = struct.calcsize("3i")
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, cred_size)
    if len(raw) != cred_size:
        raise OSError("Peer credentials unavailable")
    _pid, uid, _gid = struct.unpack("3i", raw)
    return uid


def _private_directory(path):
    """Refuse missing, symlinked, shared or foreign-owned socket directories."""
    path = os.path.abspath(os.fspath(path))
    info = os.lstat(path)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise PermissionError("Owner socket directory must be a private mode-0700 directory")
    if len(os.fsencode(os.path.join(path, SOCKET_NAME))) >= 100:
        raise ValueError("Unix socket directory path is too long")
    return path


def _serialize_pending(queue):
    return [
        {"request_id": item.request_id,
         "device_id": item.peer.node_id,
         "account_id": item.peer.user_id,
         "backend": item.backend,
         "expires_in_seconds": item.expires_in_seconds}
        for item in queue.owner_pending()
    ]


def _dispatch(queue, request):
    """No client-request submission, pairing grants or backend controls here."""
    if not isinstance(request, dict):
        return {"ok": False, "error": "invalid_request"}
    action = request.get("action")
    if action == "list" and set(request) == {"action"}:
        return {"ok": True, "pending": _serialize_pending(queue)}
    if action in ("approve", "deny") and set(request) == {"action", "request_id"}:
        request_id = request["request_id"]
        if not isinstance(request_id, str):
            return {"ok": False, "error": "invalid_request"}
        decided = queue.owner_decide(request_id, approve=(action == "approve"))
        return {"ok": decided, "error": None if decided else "not_pending"}
    return {"ok": False, "error": "unsupported_operation"}


class _OwnerHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(SOCKET_TIMEOUT)
        try:
            if _peer_uid(self.request) != self.server.owner_uid:
                self._send({"ok": False, "error": "owner_only"})
                return
            raw = self.rfile.readline(MAX_INPUT + 1)
            if not raw.endswith(b"\n") or len(raw) > MAX_INPUT:
                self._send({"ok": False, "error": "invalid_request"})
                return
            message = json.loads(raw.decode("utf-8"))
            result = _dispatch(self.server.pairing_requests, message)
            self._send(result)
        except (OSError, ValueError, UnicodeError, socket.timeout,
                json.JSONDecodeError):
            # Fail closed and never include raw request bytes or OS diagnostics.
            try:
                self._send({"ok": False, "error": "invalid_request"})
            except (BrokenPipeError, OSError):
                pass

    def _send(self, obj):
        serialized = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if len(serialized) > MAX_OUTPUT:
            serialized = b'{"ok":false,"error":"unavailable"}'
        self.wfile.write(serialized + b"\n")
        self.wfile.flush()


class OwnerControl(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    """Explicitly constructed, local-only owner interface.

    Directory must already exist, owned by the current euid and mode 0700.
    No global service unit, network socket or startup mechanism is provided.
    """

    daemon_threads = True
    allow_reuse_address = False
    # Keep the accept queue ahead of a short burst of local owner commands.
    request_queue_size = 32

    def __init__(self, socket_dir, pairing_requests):
        # Import locally so unrelated discovery/preflight runtimes stay isolated.
        from now_pairing_requests import PairingRequests
        if not isinstance(pairing_requests, PairingRequests):
            raise TypeError("A trusted PairingRequests instance is required")
        directory = _private_directory(socket_dir)
        path = os.path.join(directory, SOCKET_NAME)
        if os.path.lexists(path):
            raise FileExistsError("Owner socket path already exists; refusing to replace it")
        self.owner_uid = os.geteuid()
        self.pairing_requests = pairing_requests
        self.socket_path = path
        self._socket_inode = None
        # Binding under a restrictive umask avoids a window of broad access.
        # Only construct from the host broker main thread, before workers start.
        previous_mask = os.umask(0o077)
        try:
            super().__init__(path, _OwnerHandler)
            os.chmod(path, 0o600, follow_symlinks=False)
            info = os.lstat(path)
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != self.owner_uid:
                raise PermissionError("Unexpected owner socket")
            self._socket_inode = info.st_ino
        except Exception:
            # If bind created a socket, clean only that newly created socket.
            self.server_close()
            raise
        finally:
            os.umask(previous_mask)

    def server_close(self):
        super().server_close()
        if self._socket_inode is None:
            return
        try:
            info = os.lstat(self.socket_path)
            if stat.S_ISSOCK(info.st_mode) and info.st_ino == self._socket_inode:
                os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
        self._socket_inode = None


def owner_command(socket_dir, action, request_id=None):
    """Owner-side client. Does not start the broker or establish trust."""
    if action not in ("list", "approve", "deny"):
        raise ValueError("Unsupported owner operation")
    if (action == "list" and request_id is not None) or (
            action != "list" and not isinstance(request_id, str)):
        raise ValueError("Invalid owner command arguments")
    directory = _private_directory(socket_dir)
    message = {"action": action}
    if action != "list":
        message["request_id"] = request_id
    encoded = json.dumps(message, separators=(",", ":")).encode() + b"\n"
    if len(encoded) > MAX_INPUT:
        raise ValueError("Owner command too large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(SOCKET_TIMEOUT)
        connection.connect(os.path.join(directory, SOCKET_NAME))
        connection.sendall(encoded)
        # Bound response parsing even if the socket is replaced by a local
        # malicious same-UID process.
        with connection.makefile("rb") as stream:
            raw = stream.readline(MAX_OUTPUT + 1)
        if not raw.endswith(b"\n") or len(raw) > MAX_OUTPUT:
            raise ValueError("Malformed owner response")
        reply = json.loads(raw)
        if not isinstance(reply, dict) or type(reply.get("ok")) is not bool:
            raise ValueError("Invalid owner response")
        return reply


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local-only NOW pairing owner control")
    parser.add_argument("--socket-dir", required=True,
                        help="Existing owner-controlled directory (mode 0700)")
    parser.add_argument("action", choices=("list", "approve", "deny"))
    parser.add_argument("request_id", nargs="?")
    args = parser.parse_args(argv)
    try:
        response = owner_command(args.socket_dir, args.action, args.request_id)
    except (OSError, ValueError, PermissionError, socket.timeout):
        print("Local owner control unavailable; no pairing approval changed.", file=sys.stderr)
        return 1
    if args.action == "list" and response.get("ok"):
        for item in response.get("pending", []):
            print("{} {} {} {} {}s".format(
                item["request_id"], item["device_id"], item["account_id"],
                item["backend"], item["expires_in_seconds"]))
        return 0
    if response.get("ok"):
        print("Owner decision recorded; Moonlight pairing has NOT been completed.")
        return 0
    print("Request unavailable or already decided; no pairing performed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
