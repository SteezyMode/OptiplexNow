"""Owner-approved, host-only DroppedNeedle credential issuing boundary.

This is deliberately NOT a public web endpoint or an automatic grant based on
Tailnet/Wolf pairing. The caller must authenticate the restricted SSH key and
supply its pinned verified_client_id, then load the host owner's private
DroppedNeedle account connection independently of the client's request.

The adapter uses DroppedNeedle v2.15.0's existing APIs:
  POST /api/v1/auth/login               (host account; host-only credential)
  POST /api/v1/connect-apps/app-passwords
  POST /api/v1/auth/device-sessions
  GET  /api/v1/auth/sessions            (find companion session ID for revoke)
  DELETE .../app-passwords/{id} and /auth/sessions/{id}

No host administrator credential is returned to a client. The two revocable
device secrets are returned ONLY to the separately verified, confidential
restricted transport after its revoke identifiers have been durably recorded.
The production owner GUI/host-secret bootstrap and SSH action are still pending.
"""
from __future__ import annotations

import json
import re
import secrets
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPHandler, HTTPSHandler

from owner_access import PolicyError, resolve_music

MAX_BODY = 64 * 1024
MAX_TOKEN = 2048
ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class ProvisionError(Exception):
    """Fails without echoing upstream text, credentials, or host paths."""


def _text(value, maximum=MAX_TOKEN):
    return (isinstance(value, str) and 1 <= len(value) <= maximum
            and all(32 < ord(ch) < 127 for ch in value))


def _host_text(value, maximum):
    # Host-local login details may contain spaces or non-ASCII characters;
    # only opaque bearer tokens are restricted to printable ASCII.
    return (isinstance(value, str) and 1 <= len(value) <= maximum
            and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value))


class DroppedNeedleAPI:
    """Fixed-path, no-proxy, no-redirect client for a host-owned DN instance."""

    def __init__(self, base_url):
        # Import the same URL policy as Music's hardened streaming transport.
        from music_subsonic import endpoint_for, MusicTransportError, DenyRedirects
        try:
            checked = endpoint_for(base_url, "ping")
        except MusicTransportError as exc:
            raise ProvisionError("Invalid configured Music service address.") from exc
        suffix = "/subsonic/rest/ping"
        if not checked.endswith(suffix):
            raise ProvisionError("Invalid Music service base path.")
        self.base = checked[:-len(suffix)]
        self.opener = build_opener(ProxyHandler({}), DenyRedirects(),
                                   HTTPHandler(),
                                   HTTPSHandler(context=ssl.create_default_context()))

    def call(self, method, resource, *, bearer=None, data=None):
        if method not in ("GET", "POST", "DELETE"):
            raise ProvisionError("Unsupported Music authorization operation.")
        # Routes are never taken from an arbitrary remote-client request.
        valid = (resource in (
            "/auth/login", "/auth/device-sessions", "/auth/sessions",
            "/connect-apps/app-passwords",
        ) or (
            resource.startswith("/connect-apps/app-passwords/")
            and ID.fullmatch(resource.rsplit("/", 1)[-1])
        ) or (
            resource.startswith("/auth/sessions/")
            and ID.fullmatch(resource.rsplit("/", 1)[-1])
        ))
        if not valid:
            raise ProvisionError("Unexpected Music authorization endpoint.")
        if data is not None and (method != "POST" or not isinstance(data, dict)):
            raise ProvisionError("Invalid Music authorization payload.")
        if bearer is not None and not _text(bearer):
            raise ProvisionError("Invalid host Music session.")
        parts = urlsplit(self.base)
        url = urlunsplit((parts.scheme, parts.netloc,
                          parts.path.rstrip("/") + "/api/v1" + resource, "", ""))
        raw = json.dumps(data, separators=(",", ":")).encode() if data is not None else None
        if raw is not None and len(raw) > 4096:
            raise ProvisionError("Music authorization payload is too large.")
        headers = {"Accept": "application/json", "Cache-Control": "no-store"}
        if raw is not None:
            headers["Content-Type"] = "application/json"
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        req = Request(url, method=method, data=raw, headers=headers)
        try:
            with self.opener.open(req, timeout=12) as response:
                if method == "DELETE":
                    return {}
                content = response.read(MAX_BODY + 1)
        except (HTTPError, URLError, OSError, TimeoutError):
            raise ProvisionError("Music authorization service unavailable.") from None
        except Exception as exc:
            # Do not let a redirect or malformed response leak server details.
            raise ProvisionError("Music authorization request denied.") from None
        if len(content) > MAX_BODY:
            raise ProvisionError("Music authorization response too large.")
        try:
            result = json.loads(content)
        except (ValueError, UnicodeError):
            raise ProvisionError("Music authorization returned invalid data.") from None
        if not isinstance(result, dict):
            raise ProvisionError("Music authorization returned invalid data.")
        return result

    def login(self, username, password):
        if not _host_text(username, 256) or not _host_text(password, 2048):
            raise ProvisionError("Host Music account is not linked.")
        result = self.call("POST", "/auth/login",
                           data={"username": username, "password": password})
        token = result.get("token")
        user = result.get("user")
        if not _text(token) or not isinstance(user, dict) or not _text(user.get("id"), 128):
            raise ProvisionError("Host Music sign-in failed.")
        return token, user["id"]

    def create_app(self, token, device_name):
        result = self.call("POST", "/connect-apps/app-passwords",
                           bearer=token, data={"name": device_name})
        record = result.get("app_password")
        secret = result.get("secret")
        if not isinstance(record, dict) or not ID.fullmatch(str(record.get("id", ""))) or not _text(secret):
            raise ProvisionError("Could not issue Music playback access.")
        return secret, record["id"]

    def create_companion(self, token, device_name, expected_user):
        result = self.call("POST", "/auth/device-sessions", bearer=token,
                           data={"device_name": device_name})
        user = result.get("user")
        secret = result.get("token")
        if not isinstance(user, dict) or user.get("id") != expected_user or not _text(secret):
            raise ProvisionError("Could not issue Music discovery access.")
        sessions = self.call("GET", "/auth/sessions", bearer=token).get("sessions", [])
        matches = [item.get("id") for item in sessions
                   if isinstance(item, dict)
                   and item.get("session_kind") == "companion"
                   and item.get("user_agent") ==
                       "DroppedNeedle companion · " + device_name
                   and ID.fullmatch(str(item.get("id", "")))]
        if len(matches) != 1:
            raise ProvisionError("Cannot track Music device revocation.")
        return secret, matches[0]

    def revoke(self, token, *, app_id=None, session_id=None):
        if session_id is not None:
            self.call("DELETE", "/auth/sessions/" + session_id, bearer=token)
        if app_id is not None:
            self.call("DELETE", "/connect-apps/app-passwords/" + app_id,
                      bearer=token)


def issue_approved_music_access(policy, verified_client_id, paired_clients,
                                *, host_account, record_grants, api_factory=DroppedNeedleAPI):
    """Mint two private per-device capabilities after policy+owner authentication.

    host_account and record_grants come ONLY from the privileged host; they
    cannot be fields of an SSH request. record_grants must persist the IDs in
    an atomic host-owned 0600 store; if persistence fails, rollback both keys.
    All returned secret fields must travel only over the already authenticated
    and confidential restricted owner SSH channel, never in logs.
    """
    resolved = resolve_music(policy, verified_client_id, paired_clients)
    if not isinstance(host_account, dict) or set(host_account) != {
        "base_url", "owner_principal_id", "username", "password"
    } or host_account["owner_principal_id"] != resolved["principal_id"]:
        raise ProvisionError("Host owner has not connected Music.")
    if not callable(record_grants):
        raise ProvisionError("Host Music revocation ledger is unavailable.")
    api = api_factory(host_account["base_url"])
    master, user_id = api.login(host_account["username"], host_account["password"])
    label = "Bruiser " + verified_client_id + " " + secrets.token_hex(8)
    app_id = session_id = None
    try:
        app_secret, app_id = api.create_app(master, label)
        rest_secret, session_id = api.create_companion(master, label, user_id)
        revocation = {"client_id": verified_client_id,
                      "host_id": resolved["host_id"],
                      "dn_user_id": user_id,
                      "app_password_id": app_id,
                      "companion_session_id": session_id}
        record_grants(revocation)
        # Do not send the DN master token, password, or host URL to a client.
        return {"app_password": app_secret, "rest_token": rest_secret}
    except BaseException:
        # Never return a credential lacking a durable revocation mapping.
        try:
            api.revoke(master, app_id=app_id, session_id=session_id)
        except Exception:
            pass
        raise
