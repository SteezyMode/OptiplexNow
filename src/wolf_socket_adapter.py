"""Allowlisted Wolf HTTP-over-Unix-socket protocol adapter.

Inside the Wolf container the socket is /run/user/wolf/wolf.sock. The host
side wrapper sends this exact code via docker exec, but the ordinary NOW
client does not install, import, or invoke it. No TCP listener is opened.

The allowed POSTs are state-changing: ONLY a future authenticated, approved
host-side owner launch transaction may invoke them. This module does not
authenticate callers or enforce Wolf access rights.
"""
import json
import socket
import sys

WOLF_SOCKET = "/run/user/wolf/wolf.sock"
MAX_REQUEST = 65536
MAX_RESPONSE = 262144
MAX_HEADERS = 16384
# Upstream Wolf CreateLobby waits up to 20 seconds for its runner setup.
# The Unix-socket client must outlive that deadline. No POST retries.
DEFAULT_SOCKET_TIMEOUT = 5
CREATE_SOCKET_TIMEOUT = 26
ALLOWED = frozenset({
    ("GET", "/api/v1/clients"),
    ("GET", "/api/v1/profiles"),
    ("GET", "/api/v1/apps"),
    ("GET", "/api/v1/sessions"),
    ("GET", "/api/v1/lobbies"),
    ("GET", "/api/v1/openapi-schema"),
    ("POST", "/api/v1/lobbies/create"),
    ("POST", "/api/v1/lobbies/join"),
    ("POST", "/api/v1/lobbies/stop"),
})


class WolfSocketError(RuntimeError):
    """Safe diagnostic without raw Wolf JSON, private headers, or secrets."""


def check_request(method, path, body=None):
    if (not isinstance(method, str) or not isinstance(path, str) or
            (method, path) not in ALLOWED):
        raise WolfSocketError("Wolf API operation is not allowlisted")
    if method == "GET" and body is not None:
        raise WolfSocketError("GET requests must not contain a body")
    if method == "POST" and not isinstance(body, dict):
        raise WolfSocketError("Wolf POST requires a JSON object")
    serialized = (json.dumps(body, separators=(",", ":")).encode("utf-8")
                  if body is not None else b"")
    if len(serialized) > MAX_REQUEST:
        raise WolfSocketError("Wolf request body too large")
    return serialized


def socket_timeout(method, path):
    return (CREATE_SOCKET_TIMEOUT if (method, path) ==
            ("POST", "/api/v1/lobbies/create") else DEFAULT_SOCKET_TIMEOUT)


class WolfUnixAPI:
    def __init__(self, socket_path=WOLF_SOCKET, timeout=None):
        self.socket_path = socket_path
        self.timeout = timeout

    def __call__(self, method, path, body=None):
        payload = check_request(method, path, body)
        header = (f"{method} {path} HTTP/1.0\r\n"
                  f"Host: localhost\r\nConnection: close\r\n"
                  f"Content-Length: {len(payload)}\r\n"
                  f"Content-Type: application/json\r\n\r\n").encode("ascii")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                peer.settimeout(self.timeout if self.timeout is not None
                                else socket_timeout(method, path))
                peer.connect(self.socket_path)
                peer.sendall(header + payload)
                chunks = bytearray()
                while True:
                    chunk = peer.recv(8192)
                    if not chunk:
                        break
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE + MAX_HEADERS:
                        raise WolfSocketError("Wolf response exceeds size limit")
        except (OSError, TimeoutError) as exc:
            raise WolfSocketError("Wolf local socket unavailable or timed out") from None
        return parse_response(bytes(chunks))


def parse_response(raw):
    """Validate a complete HTTP response. Fail closed for ambiguous framing."""
    if not isinstance(raw, bytes):
        raise WolfSocketError("Malformed Wolf response")
    head, sep, payload = raw.partition(b"\r\n\r\n")
    if not sep or len(head) > MAX_HEADERS or len(payload) > MAX_RESPONSE:
        raise WolfSocketError("Malformed or oversized Wolf response")
    lines = head.split(b"\r\n")
    fields = lines[0].split(b" ")
    if (len(fields) < 2 or fields[0] not in (b"HTTP/1.0", b"HTTP/1.1")
            or not fields[1].isdigit()):
        raise WolfSocketError("Malformed Wolf HTTP status")
    if fields[1] != b"200":
        raise WolfSocketError("Wolf API refused request")
    length = None
    for line in lines[1:]:
        name, separator, value = line.partition(b":")
        if not separator:
            raise WolfSocketError("Malformed Wolf HTTP header")
        name = name.strip().lower()
        value = value.strip().lower()
        if name in (b"transfer-encoding", b"content-encoding"):
            raise WolfSocketError("Unsupported Wolf response encoding")
        if name == b"content-length":
            if length is not None or not value.isdigit():
                raise WolfSocketError("Ambiguous Wolf response length")
            length = int(value)
    if length is not None and length != len(payload):
        raise WolfSocketError("Truncated Wolf response body")
    try:
        obj = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise WolfSocketError("Invalid Wolf JSON response") from None
    if not isinstance(obj, dict):
        raise WolfSocketError("Wolf response must be a JSON object")
    return obj


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        raise WolfSocketError("Unsupported Wolf API invocation")
    method, path = args
    # Reject method and path before reading stdin.
    check_request(method, path, {} if method == "POST" else None)
    body = None
    if method == "POST":
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(raw) > MAX_REQUEST:
            raise WolfSocketError("Wolf request body too large")
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise WolfSocketError("Invalid Wolf request JSON") from None
    result = WolfUnixAPI()(method, path, body)
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except WolfSocketError:
        # Do not expose session keys, PINs, runner config or raw daemon errors.
        print("Wolf local API operation failed", file=sys.stderr)
        sys.exit(1)
