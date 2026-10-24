#!/usr/bin/env python3
"""Request owner-device approval over a known, already authorized owner SSH account.

This never transfers the private key, grants permissions, or guesses a Wolf
identity. The actual owner completes the binding on the HOST GUI; end users
must not receive host-admin SSH credentials.
"""
import http.client
import ipaddress
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

CLIENT_MODULE = Path(__file__).with_name("owner-games-client.py")
HOST_HELPER = "/usr/lib/optiplex-now/owner-bridge/server/owner_enrollment.py"
REQUIRED = frozenset(("success", "status", "request_id", "code", "fingerprint"))
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX20 = re.compile(r"[0-9a-f]{20}\Z")
CODE = re.compile(r"[0-9]{6}\Z")


def _client_module():
    loader = importlib.machinery.SourceFileLoader("now_games_enroll", str(CLIENT_MODULE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def request(host, user, *, key_module=None, owner_key=None, runner=subprocess.run):
    games = key_module or _client_module()
    games.validated_target(host, user)
    _, public_path = games.ensure_key()
    public = public_path.read_text(encoding="ascii").strip()
    # The transport is the pre-existing, explicitly approved owner SSH
    # credential; enrollment itself creates a SEPARATE restricted key.
    owner_key = Path(owner_key) if owner_key else Path.home() / ".ssh/id_ed25519"
    if owner_key.is_symlink() or not owner_key.is_file():
        raise ValueError("Ordinary owner SSH is not configured")
    argv = ["ssh", "-F", "/dev/null", "-i", str(owner_key),
            "-o", "IdentitiesOnly=yes",
            "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=6", "-o", "ConnectionAttempts=1",
            "-o", "ClearAllForwardings=yes", "-T", "-l", user, "--", host,
            "/usr/bin/python3 " + HOST_HELPER + " request"]
    raw = (json.dumps({"version": 1, "public_key": public},
                      separators=(",", ":")) + "\n").encode("ascii")
    proc = runner(argv, input=raw, stdout=subprocess.PIPE,
                  stderr=subprocess.DEVNULL, timeout=20, check=False)
    if proc.returncode != 0 or len(proc.stdout or b"") > 1024:
        raise ValueError("Owner request transport unavailable")
    answer = json.loads(proc.stdout)
    if (not isinstance(answer, dict) or set(answer) != REQUIRED
            or answer["success"] is not True or answer["status"] != "pending"
            or not isinstance(answer["request_id"], str)
            or not HEX32.fullmatch(answer["request_id"])
            or not isinstance(answer["code"], str)
            or not CODE.fullmatch(answer["code"])
            or not isinstance(answer["fingerprint"], str)
            or not HEX20.fullmatch(answer["fingerprint"])):
        raise ValueError("Untrusted owner enrollment response")
    return answer



def request_tailnet(host, *, key_module=None, connection=http.client.HTTPConnection):
    """Stage only a public key using a separately provisioned Tailscale listener.

    The listener authenticates the actual Tailscale WhoIs peer and pinned owner.
    This does not approve the key, bind Wolf IDs or install authorized_keys.
    Normal clients never supply SSH usernames or administrator credentials.
    """
    try:
        ip = ipaddress.ip_address(host)
    except (TypeError, ValueError):
        raise ValueError("Owner enrollment requires a Tailscale IPv4 host") from None
    if (ip.version != 4 or ip not in ipaddress.ip_network("100.64.0.0/10")
            or str(ip) == "100.100.100.100"):
        raise ValueError("Owner enrollment requires a Tailscale IPv4 host")
    games = key_module or _client_module()
    _, public = games.ensure_key()
    payload = json.dumps({"version": 1,
                          "public_key": public.read_text(encoding="ascii").strip()},
                         separators=(",", ":")).encode("ascii")
    if len(payload) > 1024:
        raise ValueError("Invalid restricted owner public key")
    client = connection(host, 18793, timeout=6)
    try:
        client.request("POST", "/v1/owner/enrollment/request", body=payload,
                       headers={"Content-Type": "application/json",
                                "Accept": "application/json"})
        response = client.getresponse()
        raw = response.read(1025)
        if response.status != 202 or len(raw) > 1024:
            raise ValueError("Tailnet owner enrollment is unavailable or not authorized")
        data = json.loads(raw)
        if (not isinstance(data, dict) or set(data) != REQUIRED
                or data.get("success") is not True or data.get("status") != "pending"
                or not isinstance(data.get("request_id"), str)
                or not HEX32.fullmatch(data["request_id"])
                or not isinstance(data.get("code"), str)
                or not CODE.fullmatch(data["code"])
                or not isinstance(data.get("fingerprint"), str)
                or not HEX20.fullmatch(data["fingerprint"])):
            raise ValueError("Invalid tailnet owner enrollment response")
        return data
    finally:
        client.close()


def request_using_available_transport(host, user):
    """Prefer narrow authenticated Tailnet staging; retain explicit owner pilot.

    Existing already-authorized owner SSH is a development fallback only.
    Neither route approves a key or weakens owner policy.
    """
    try:
        return request_tailnet(host)
    except ConnectionRefusedError:
        # Only an absent pilot service permits the existing trusted owner
        # alpha path. An explicit 403, malformed response or wrong identity
        # must NOT be silently routed around through administrator SSH.
        return request(host, user)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print('{"success":false,"status":"unavailable"}')
        return 1
    try:
        result = request(args[0], args[1])
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 0
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError, json.JSONDecodeError):
        print('{"success":false,"status":"unavailable"}')
        return 1


if __name__ == "__main__":
    sys.exit(main())
