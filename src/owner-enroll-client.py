#!/usr/bin/env python3
"""Stage a restricted owner device public key; no credentials are granted.

An opt-in owner-authenticated Tailscale listener is preferred. Existing trusted
owner SSH remains as a controlled alpha fallback only when that listener is
absent. The private key never leaves the client and no Wolf ID is guessed.
The host verifies signed Moonlight proof and the independently pinned owner phone;
no pending request or client-local artifact independently grants authority.
"""
import http.client
import ipaddress
import importlib.machinery
import importlib.util
import json
import os
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
RESTRICTED_ACCESS_STATES = frozenset((
    "needs_wolf_ui", "wolf_ui_connected", "busy", "in_use",
    "joined", "idle", "running", "finished"))


def verified_restricted_access(reply):
    """Accept only a positive, finite, host-verified restricted SSH reply.

    A key file, a successful subprocess exit, a pending approval or a Wolf
    pairing is never enough to claim NOW owner-service authorization.
    """
    return (isinstance(reply, dict) and reply.get("success") is True
            and isinstance(reply.get("status"), str)
            and reply["status"] in RESTRICTED_ACCESS_STATES)


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
        if (not isinstance(data, dict) or
                set(data) not in (REQUIRED, REQUIRED | {"phone_approval_available"})
                or data.get("success") is not True or data.get("status") != "pending"
                or not isinstance(data.get("request_id"), str)
                or not HEX32.fullmatch(data["request_id"])
                or not isinstance(data.get("code"), str)
                or not CODE.fullmatch(data["code"])
                or not isinstance(data.get("fingerprint"), str)
                or not HEX20.fullmatch(data["fingerprint"])
                or ("phone_approval_available" in data and
                    type(data["phone_approval_available"]) is not bool)):
            raise ValueError("Invalid tailnet owner enrollment response")
        return data
    finally:
        client.close()




def submit_moonlight_proof(host, request, *, config_path=None,
                          connection=http.client.HTTPConnection):
    """Send signed Moonlight *public* proof. Phone approval is still separate.

    The matching Moonlight profile must be uniquely identifiable. The
    client's existing private key is only read in its process; it is never
    serialized into the request payload or placed in NOW settings.
    """
    host = _tailnet_target(host)
    if (not isinstance(request, dict) or
            not all(isinstance(request.get(k), str) for k in (
                "request_id", "code", "fingerprint"))
            or not HEX32.fullmatch(request["request_id"])
            or not CODE.fullmatch(request["code"])
            or not HEX20.fullmatch(request["fingerprint"])):
        raise ValueError("Invalid owner enrollment request")
    path = Path(__file__).with_name("moonlight-identity-proof.py")
    loader = importlib.machinery.SourceFileLoader("now_moonlight_cert_proof", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    candidate = config_path or module.unique_moonlight_config()
    proof = module.sign_for_request(
        candidate, module.enrollment_challenge(
            request["request_id"], request["code"], request["fingerprint"]))
    data = json.dumps({
        "request_id": request["request_id"],
        "certificate_pem": proof["certificate_pem"],
        "signature_b64": proof["signature_b64"]
    }, separators=(",", ":")).encode("ascii")
    if len(data) > 11000:
        raise ValueError("Oversized Moonlight certificate proof")
    client = connection(host, 18793, timeout=12)
    try:
        client.request("POST", "/v1/owner/enrollment/certificate-proof",
                       body=data, headers={"Content-Type": "application/json",
                                           "Accept": "application/json"})
        result = client.getresponse()
        body = result.read(513)
        if result.status != 200 or len(body) > 512:
            raise ValueError("Host did not accept Moonlight certificate proof")
        reply = json.loads(body)
        if (not isinstance(reply, dict) or set(reply) != {"success", "status"}
                or reply.get("success") is not True
                or reply.get("status") != "proof_recorded"):
            raise ValueError("Host did not record Moonlight certificate proof")
        return True
    finally:
        client.close()


WOLF_ID = re.compile(r"[0-9]{1,20}\Z")


def _tailnet_target(host):
    try:
        ip = ipaddress.ip_address(host)
    except (TypeError, ValueError):
        raise ValueError("A Tailscale IPv4 address is required") from None
    if (ip.version != 4 or ip not in ipaddress.ip_network("100.64.0.0/10")
            or str(ip) == "100.100.100.100"):
        raise ValueError("A Tailscale IPv4 address is required")
    return str(ip)


def review_active_wolf(host, request_id, *, connection=http.client.HTTPConnection):
    """Read one host-observed Wolf UI client ID; no privilege granted."""
    host = _tailnet_target(host)
    if not isinstance(request_id, str) or not HEX32.fullmatch(request_id):
        raise ValueError("Invalid owner request ID")
    client = connection(host, 18793, timeout=6)
    try:
        client.request("GET", "/v1/owner/enrollment/wolf-candidate/" + request_id,
                       headers={"Accept": "application/json"})
        reply = client.getresponse()
        raw = reply.read(513)
        if reply.status != 200 or len(raw) > 512:
            raise ValueError("No unique active Wolf UI or remote owner review disabled")
        data = json.loads(raw)
        wolf_id = data.get("wolf_client_id") if isinstance(data, dict) else None
        if (not isinstance(data, dict) or data.get("success") is not True
                or not isinstance(wolf_id, str) or not WOLF_ID.fullmatch(wolf_id)
                or set(data) != {"success", "wolf_client_id"}):
            raise ValueError("Invalid host Wolf review response")
        return wolf_id
    finally:
        client.close()


class NoRecentPairing(ValueError):
    """A fresh same-node Wolf pairing witness is not available."""


def review_recent_pairing(host, request_id, *,
                          connection=http.client.HTTPConnection):
    """Ask host for a newly paired Wolf ID witnessed on this same Tailnet node."""
    host = _tailnet_target(host)
    if not isinstance(request_id, str) or not HEX32.fullmatch(request_id):
        raise ValueError("Invalid staged enrollment request ID")
    payload = json.dumps({"request_id": request_id},
                         separators=(",", ":")).encode("ascii")
    client = connection(host, 18793, timeout=7)
    try:
        client.request("POST", "/v1/owner/enrollment/paired-candidate",
                       body=payload,
                       headers={"Content-Type": "application/json",
                                "Accept": "application/json"})
        reply = client.getresponse()
        raw = reply.read(513)
        if reply.status in (404, 409):
            raise NoRecentPairing("No recent same-node pairing witness")
        if reply.status != 200 or len(raw) > 512:
            raise ValueError("Owner recent pairing review denied")
        data = json.loads(raw)
        ident = data.get("wolf_client_id") if isinstance(data, dict) else None
        if (not isinstance(data, dict) or set(data) !=
                {"success", "wolf_client_id"}
                or data["success"] is not True
                or not isinstance(ident, str) or not WOLF_ID.fullmatch(ident)):
            raise ValueError("Untrusted recent Wolf pairing candidate")
        return ident
    finally:
        client.close()


def review_for_owner(host, request_id):
    """Prefer same-node witnessed pairing; only absent proof tries Wolf UI."""
    try:
        return {"wolf_client_id": review_recent_pairing(host, request_id),
                "source": "recent_pair"}
    except NoRecentPairing:
        return {"wolf_client_id": review_active_wolf(host, request_id),
                "source": "active_wolf_ui"}


def approve_reviewed_tailnet(host, request_id, code, wolf_client_id, *,
                             source="active_wolf_ui",
                             connection=http.client.HTTPConnection):
    """Explicit owner confirmation, never automatic. No admin SSH fallback."""
    host = _tailnet_target(host)
    if (not isinstance(request_id, str) or not HEX32.fullmatch(request_id)
            or not isinstance(code, str) or not CODE.fullmatch(code)
            or not isinstance(wolf_client_id, str)
            or not WOLF_ID.fullmatch(wolf_client_id)):
        raise ValueError("Invalid owner review request")
    if source not in ("recent_pair", "active_wolf_ui"):
        raise ValueError("Unknown owner review source")
    fields = {"request_id": request_id, "code": code,
              "wolf_client_id": wolf_client_id, "confirmed": True}
    if source == "recent_pair":
        fields["source"] = source
    payload = json.dumps(fields, separators=(",", ":")).encode("ascii")
    client = connection(host, 18793, timeout=12)
    try:
        client.request("POST", "/v1/owner/enrollment/approve", body=payload,
                       headers={"Content-Type": "application/json",
                                "Accept": "application/json"})
        reply = client.getresponse()
        raw = reply.read(513)
        if reply.status != 200 or len(raw) > 512:
            raise ValueError("Remote owner approval denied or unavailable")
        data = json.loads(raw)
        if (not isinstance(data, dict) or set(data) != {"success", "status"}
                or data.get("success") is not True
                or data.get("status") != "approved"):
            raise ValueError("Invalid owner approval response")
        return True
    finally:
        client.close()


def already_authorized(host, user, *, games=None):
    """Prove current restricted Games access before offering a new QR request.

    This uses the existing read-only forced-command 'status' action, not
    host-side public-key matching or a local assumption about stored files.
    Failure is inconclusive: it may mean unapproved, offline, or bad routing.
    """
    module = games or _client_module()
    try:
        reply = module.invoke(host, user, "status")
        return verified_restricted_access(reply)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError):
        return False


def request_using_available_transport(host, user, *, include_transport=False):
    """Verify current restricted access before staging a fresh owner request.

    A working authorized key needs no QR approval. A failed check is not
    treated as proof of non-enrollment; the trusted host still controls staging.
    """
    if already_authorized(host, user):
        result = {"success": True, "status": "already_authorized"}
        return dict(result, transport="restricted_ssh") if include_transport else result
    try:
        result = request_tailnet(host)
        return dict(result, transport="tailnet") if include_transport else result
    except ConnectionRefusedError:
        # Only an absent pilot service permits the existing trusted owner
        # alpha path. An explicit 403, malformed response or wrong identity
        # must NOT be silently routed around through administrator SSH.
        result = request(host, user)
        return dict(result, transport="ssh") if include_transport else result


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
