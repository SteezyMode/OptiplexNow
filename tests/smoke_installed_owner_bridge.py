"""CI-only installed-package integration: approval -> restricted Games status.

This deliberately imports /usr/lib/optiplex-now/owner-bridge, NOT source-tree
implementations. All state (including SSH authorized_keys and Wolf config) is
under a disposable temporary directory. A loopback HTTP server substitutes
for the transport; verified Tailscale peers are test fixtures, NOT headers.
No real keys, host services, Docker, SSH, Steam or Tailscale are contacted.
Physical fresh-client/phone/controller acceptance remains a separate gate.
"""
import base64
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer
import http.client
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import threading

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.x509.oid import NameOID


ROOT = Path("/usr/lib/optiplex-now")
BRIDGE = ROOT / "owner-bridge"
SERVER = BRIDGE / "server"
SOURCE = BRIDGE / "src"
assert ROOT.is_dir(), "This test requires an installed .deb on disposable CI"
assert SERVER.is_dir() and SOURCE.is_dir(), "Packaged owner bridge is missing"
# Install paths take precedence even when launched from the source checkout.
sys.path[:0] = [str(SERVER), str(SOURCE)]

from owner_access import OwnerStore, PolicyError, approve_device, new_owner
from owner_enrollment import approve_request
from moonlight_cert_identity import wolf_certificate_client_id
from owner_qr_approval import PAGE_PREFIX
from tailnet_enrollment import (make_handler, ROUTE, PROOF_ROUTE,
                                REVIEW_ROUTE, APPROVE_ROUTE)
import owner_games_ssh
import owner_games_request
import owner_certificate_attestation
import owner_games_enroll
import tailnet_owner_identity
import tailnet_wolf_review
import tailnet_wolf_pair
import download_search
import download_manage
import media_endpoint


def installed_path(module):
    filename = Path(module.__file__).resolve()
    if not filename.is_relative_to(BRIDGE):
        raise AssertionError("Loaded host helper outside installed .deb: " + str(filename))


def client_module(name, filename):
    path = ROOT / filename
    assert path.is_file(), "Missing installed client helper " + filename
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def signing_identity():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,
                                            "Disposable NOW integration client")])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(987654321)
            .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3))
            .sign(key, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    private = key.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode("ascii")
    return pem, private


def public_ssh_key():
    private = ed25519.Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH)
    return public.decode("ascii") + " disposable-ci-device"


def fixture_policy():
    profiles = {"success": True, "profiles": [
        {"id": "user", "apps": [{"title": "Steam"}]}]}
    inventory = {"success": True, "clients": [
        {"client_id": "1001", "app_state_folder": "existing-owner-1001"}]}
    policy = new_owner("user", profiles)
    approve_device(policy, "1001", inventory)
    return policy


def run():
    # The test must not silently import source checkout modules.
    for module in (sys.modules["owner_access"], sys.modules["owner_enrollment"],
                   sys.modules["moonlight_cert_identity"],
                   sys.modules["owner_qr_approval"],
                   sys.modules["tailnet_enrollment"], owner_games_ssh,
                   owner_games_request, owner_certificate_attestation,
                   owner_games_enroll, tailnet_owner_identity,
                   tailnet_wolf_review, tailnet_wolf_pair,
                   download_search, download_manage, media_endpoint):
        installed_path(module)
    client = client_module("ci_installed_owner_client", "owner-enroll-client.py")
    client_path = ROOT / "moonlight-identity-proof.py"
    assert client_path.is_file(), "Signed Moonlight helper absent from .deb"

    with tempfile.TemporaryDirectory(prefix="now-installed-owner-") as folder:
        root = Path(folder)
        state = root / "owner-state"
        store = OwnerStore(str(state))
        with store.locked() as fd:
            store.write(fd, fixture_policy())

        auth = root / "authorized_keys"
        previous_auth = "ssh-ed25519 AAAAexisting-owner admin-only\\n"
        auth.write_text(previous_auth)
        auth.chmod(0o600)
        broker = SERVER / "owner_games_ssh.py"

        cert, private = signing_identity()
        client_id = wolf_certificate_client_id(cert.encode("ascii"))
        assert client_id != "1001"
        wolf_conf = root / "wolf.toml"
        wolf_conf.write_text(
            "paired_clients=[{client_cert=" + json.dumps(cert) +
            ', app_state_folder="disposable-wolf-home"}]\\n')
        wolf_conf.chmod(0o600)
        qt = root / "Moonlight.conf"
        qt.write_text("[General]\\ncertificate=@ByteArray(" +
                      cert.replace("\\n", r"\\n") + ")\\nkey=@ByteArray(" +
                      private.replace("\\n", r"\\n") + ")\\n")
        qt.chmod(0o600)

        public = root / "id_ed25519.pub"
        public.write_text(public_ssh_key() + "\\n")

        class Keys:
            @staticmethod
            def ensure_key():
                return root / "untransmitted-private-key", public

        def wolf(method, route):
            assert method == "GET", "Only disposable Wolf reads are allowed"
            if route == "/api/v1/clients":
                return {"success": True, "clients": [
                    {"client_id": "1001", "app_state_folder": "existing-owner-1001"},
                    {"client_id": client_id,
                     "app_state_folder": "disposable-wolf-home"}]}
            if route == "/api/v1/sessions":
                return {"success": True, "sessions": []}
            if route == "/api/v1/lobbies":
                return {"success": True, "lobbies": []}
            raise AssertionError("Unexpected Wolf endpoint " + route)

        peer = {"ip": "100.72.15.27", "node": "fresh-owner-client"}
        trusted_phone = "trusted-owner-phone"

        def verify(source, owner_id):
            if source != peer["ip"] or owner_id != "1042":
                return None
            return owner_id, peer["node"]

        def approve(state_dir, request_id, code, selected_id, *,
                    wolf_api, approval, wolf_config):
            return approve_request(
                state_dir, request_id, code, selected_id,
                confirmed=approval, wolf_api=wolf_api,
                wolf_config=wolf_config, auth_path=auth, broker_path=broker)

        base = make_handler(
            "1042", str(state), verify=verify, wolf_factory=lambda: wolf,
            approve=approve, wolf_config=str(wolf_conf),
            remote_approve_enabled=True, approver_node_id=trusted_phone)

        class SyntheticWhoIsPeer(base):
            def setup(self):
                super().setup()
                # Only test code can set the peer, never a user-supplied header.
                self.client_address = (peer["ip"], self.client_address[1])

        server = HTTPServer(("127.0.0.1", 0), SyntheticWhoIsPeer)
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()

        class LocalTransport(http.client.HTTPConnection):
            def __init__(self, host, port, timeout):
                assert host == "100.72.15.9" and port == 18793
                super().__init__("127.0.0.1", server.server_port, timeout=timeout)

        def request(method, route, payload=None):
            wire = http.client.HTTPConnection("127.0.0.1",
                                              server.server_port, timeout=3)
            try:
                body = json.dumps(payload) if payload is not None else None
                headers = {"Content-Type": "application/json"} if body else {}
                wire.request(method, route, body=body, headers=headers)
                reply = wire.getresponse()
                data = reply.read()
                if "application/json" in reply.getheader("Content-Type", ""):
                    return reply.status, json.loads(data)
                return reply.status, data.decode("utf-8")
            finally:
                wire.close()

        def restricted_status():
            return owner_games_ssh.execute(
                verified_client_id=client_id,
                environ={"SSH_CONNECTION": "100.72.15.27 1000 100.72.15.9 22"},
                read_request=lambda: {"version": 1, "action": "status"},
                read_config=lambda: {"state_dir": str(state),
                                     "video_caps": "video/x-raw",
                                     "enabled": True,
                                     "legacy_links_reviewed": True},
                wolf_api_factory=lambda: wolf,
                writer_check=lambda: True)

        try:
            # A genuine new key is staged only; no owner SSH line changes.
            pending = client.request_tailnet("100.72.15.9",
                                             key_module=Keys(),
                                             connection=LocalTransport)
            assert pending["status"] == "pending"
            assert pending["phone_approval_available"] is True
            assert auth.read_text() == previous_auth
            try:
                restricted_status()
            except PolicyError:
                pass
            else:
                raise AssertionError("Staged key could use restricted Games")

            # A signed proof is accepted but still cannot authorize Games.
            assert client.submit_moonlight_proof(
                "100.72.15.9", pending, config_path=qt,
                connection=LocalTransport) is True
            assert auth.read_text() == previous_auth
            rid = pending["request_id"]
            code = pending["code"]
            approval = {"request_id": rid, "code": code,
                        "wolf_client_id": client_id, "confirmed": True}
            assert request("GET", PAGE_PREFIX + rid)[0] == 403
            assert request("GET", REVIEW_ROUTE + "/" + rid)[0] == 403
            assert request("POST", APPROVE_ROUTE, approval)[0] == 403
            assert auth.read_text() == previous_auth

            # A phone on the same Tailscale account but the wrong *node*
            # may not approve; the configured node must review exact proof.
            peer.update(ip="100.72.15.28", node="wrong-owner-phone")
            assert request("POST", APPROVE_ROUTE, approval)[0] == 403
            assert auth.read_text() == previous_auth

            peer["node"] = trusted_phone
            status, page = request("GET", PAGE_PREFIX + rid)
            assert status == 200
            assert pending["fingerprint"] in page
            assert code not in page
            assert request("GET", REVIEW_ROUTE + "/" + rid) == (
                200, {"success": True, "wolf_client_id": client_id})
            bad = dict(approval, code="000000" if code != "000000" else "111111")
            assert request("POST", APPROVE_ROUTE, bad)[0] == 400
            assert auth.read_text() == previous_auth

            assert request("POST", APPROVE_ROUTE, approval) == (
                200, {"success": True, "status": "approved"})
            granted = auth.read_text()
            assert granted.startswith(previous_auth)
            assert "--client-id " + client_id in granted
            assert private not in granted
            assert stat.S_IMODE(auth.stat().st_mode) == 0o600

            # The forced-command host broker now recognizes the newly
            # granted device, but no Wolf session has been started.
            assert restricted_status() == {
                "success": True, "status": "needs_wolf_ui"}
            assert request("POST", APPROVE_ROUTE, approval)[0] == 400
            assert auth.read_text() == granted
            with store.locked() as fd:
                policy = store.read(fd)
            assert len(policy["devices"]) == 2
            assert len({device["client_id"]
                        for device in policy["devices"]}) == 2
            print("Installed .deb owner bridge passed: fresh key -> signed "
                  "proof -> pinned-phone approval -> restricted Games status; "
                  "wrong phone/code and replay refused.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    run()
