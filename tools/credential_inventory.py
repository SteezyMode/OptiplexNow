#!/usr/bin/env python3
"""Non-secret credential and service inventory for a Bruiser/NOW host.

This tool deliberately DOES NOT recover, open, decrypt, print, export, or
centralize any password, session cookie, API token, SSH key or Docker env var.
The optional host check only lists running Docker *container names*, classifies
service presence locally and discards the names without printing them.

Use this to map which credentials exist and which should be managed by the
host versus a user's approved client. It is NOT a password backup or scanner.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import subprocess
import sys
from typing import Callable, Sequence


@dataclass(frozen=True)
class Credential:
    id: str
    system: str
    kind: str
    authority: str
    consumer: str
    recommended_storage: str
    intended_experience: str
    recovery: str
    applies_if: str = "service enabled"


# No credential values, key locations, usernames, account identifiers, or
# environment variable values are included in this catalog.
CATALOG = (
    Credential("tailscale-login", "Tailscale", "human account", "tailnet provider",
               "owner", "external account / password manager",
               "Sign in when enrolling a new tailnet device; normal sessions persist",
               "Recover via provider, revoke lost devices"),
    Credential("tailscale-node", "Tailscale", "device identity", "tailnet provider",
               "each authorized host/client", "Tailscale-managed device state",
               "Never request underlying private node keys in Bruiser",
               "Revoke/re-enroll device from Tailscale admin"),
    Credential("now-device", "NOW owner bridge", "signed device authorization",
               "NOW host", "approved client", "client OS keyring; host approval store",
               "One approval per device, then automatic service authorization",
               "Revoke owner-device entitlement; re-enroll with new key"),
    Credential("wolf-pairing", "Wolf/Moonlight", "device pairing certificate",
               "Wolf host", "Moonlight client", "Wolf/Moonlight-managed state",
               "Device pairing distinct from NOW service approval",
               "Unpair device and re-enroll"),
    Credential("steam", "Steam", "human account/session", "Steam/Valve",
               "host game session", "Steam's own account/session storage",
               "Only initial Steam sign-in or expired session requires human action",
               "Use Steam account recovery and revoke compromised sessions"),
    Credential("jellyfin-owner", "Jellyfin", "human/admin account", "Jellyfin",
               "host owner", "Jellyfin account database; human recovery in manager",
               "Initial account setup once; never embed admin password in client",
               "Reset via supported Jellyfin admin/recovery procedure"),
    Credential("jellyfin-user", "Jellyfin", "user session/token", "Jellyfin",
               "approved user/client", "per-device OS keyring or Jellyfin client token store",
               "After owner-approved setup, normal client reconnect is automatic",
               "Revoke one client token/session without changing admin account"),
    Credential("qbittorrent-web", "qBittorrent + VueTorrent", "WebUI login/session",
               "qBittorrent", "host download broker / authorized owner",
               "host-only service authentication; scoped client access via NOW",
               "VueTorrent is another interface to qBittorrent, not a second account",
               "Reset WebUI password through supported qBittorrent administration"),
    Credential("vpn-provider", "Gluetun", "provider/WireGuard secret", "VPN provider",
               "Gluetun host container only", "protected host-only runtime secret",
               "Never visible or requested by client download controls",
               "Rotate/reissue at VPN provider without disabling kill switch"),
    Credential("soulseek", "slskd/Soulseek", "network username/password", "Soulseek",
               "slskd host only", "protected host-only secret",
               "Never ask a Bruiser client to know the Soulseek login",
               "Recover/replace Soulseek login through supported provider"),
    Credential("slskd-api", "slskd", "service API key/session", "slskd",
               "DroppedNeedle or restricted host broker", "protected host-only secret",
               "Music requests go through DroppedNeedle, not slskd",
               "Rotate slskd key and update authorized host integration"),
    Credential("droppedneedle-user", "DroppedNeedle", "human/admin account",
               "DroppedNeedle", "host owner", "DroppedNeedle account database; human recovery separately",
               "Link owner account at host once; not once per new Bruiser device",
               "Use upstream password-recovery flow"),
    Credential("droppedneedle-client", "DroppedNeedle", "revocable app password",
               "DroppedNeedle", "approved music device", "per-device OS keyring via approved host enrollment",
               "Automatically issue/revoke on trusted NOW enrollment (NOT implemented yet)",
               "Revoke this app-password; retain host owner credentials"),
    Credential("droppedneedle-encryption", "DroppedNeedle", "server encryption key",
               "DroppedNeedle deployment", "host app only",
               "protected host config; separately encrypted backup",
               "Never sent to users or packaged into a Bruiser client",
               "Restore matching key together with service database"),
    Credential("caddy-tls", "Caddy", "TLS private key / certificate state",
               "Caddy / ACME", "host reverse proxy", "host-only Caddy data volume",
               "Managed TLS should not require a client login",
               "Renew via ACME or restore host proxy state", "if configured"),
    Credential("subtitles-provider", "OpenSubtitles/Subbuzz", "external service account/API token",
               "subtitle provider", "Jellyfin host plugin", "host-only plugin secret",
               "Subtitles work without a separate login on every client",
               "Regenerate provider access token / service login", "if configured"),
    Credential("subtitle-pipeline", "SubHub/Sublarr", "local API key/service token",
               "SubHub/Sublarr", "host subtitle worker / authorized owner",
               "host-only secret with protected owner bridge",
               "Don't expose worker/admin tokens in media client settings",
               "Rotate worker key; keep API loopback/Tailnet-restricted", "if deployed"),
    Credential("local-ai", "Ollama/Studio", "optional model/provider API credentials",
               "optional provider", "host creative tools",
               "host-only app credential or provider-specific keyring",
               "No credential needed for an unauthenticated local-only Ollama endpoint",
               "Rotate provider token if actually configured", "if configured"),
    Credential("github-dev", "GitHub/CI", "developer OAuth/SSH/token",
               "GitHub", "developer/build pipeline",
               "developer keyring/CI secret store, never released installer",
               "Not part of an ordinary Bruiser user's login flow",
               "Revoke GitHub access and issue new token/key", "development only"),
    Credential("client-backup", "NOW client backup", "backup passphrase",
               "user", "owner restore operation",
               "external human password manager; never in client preset",
               "Needed only to decrypt explicit encrypted client backup",
               "Retain securely; unrecoverable if lost"),
    Credential("music-profile-backup", "Music server backup", "backup contents",
               "host backup owner", "owner disaster recovery",
               "encrypted, access-controlled host backup (NOT currently implemented)",
               "Do not create/share unencrypted server-profile archives",
               "Migrate to encrypted+authenticated export before using for recoveries"),
)

# Detect running *service families* without exposing even container names.
# No claim that a service is fully configured/authenticated or healthy.
CONTAINER_PATTERNS = {
    "Wolf/Moonlight": (r"wolf",),
    "Jellyfin": (r"jellyfin",),
    "qBittorrent + VueTorrent": (r"qbittorrent", r"vuetorrent"),
    "Gluetun": (r"gluetun",),
    "slskd/Soulseek": (r"slskd", r"soulseek"),
    "slskd": (r"slskd", r"soulseek"),
    "DroppedNeedle": (r"droppedneedle", r"dropped.needle"),
    "Caddy": (r"caddy",),
    "SubHub/Sublarr": (r"sublarr", r"subhub"),
    "Ollama/Studio": (r"ollama", r"studio"),
}


def probe_docker_names(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> set[str] | None:
    """Only request running container names; never 'docker inspect' or env."""
    try:
        result = runner(
            ["docker", "ps", "--format", "{{.Names}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    # Deliberately never expose raw names to output or exception messages.
    return {line.casefold()[:256] for line in result.stdout.splitlines()[:2000]}


def detection(system: str, container_names: set[str] | None) -> str:
    if container_names is None:
        return "not checked / Docker unavailable"
    patterns = CONTAINER_PATTERNS.get(system)
    if not patterns:
        return "not determined by Docker"
    if any(re.search(pattern, name) for pattern in patterns for name in container_names):
        return "running Docker name matched (NOT credential verification)"
    return "not detected among running Docker names"


def report(host_check: bool = False,
           runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> dict:
    names = probe_docker_names(runner) if host_check else None
    return {
        "schema": "bruiser-credential-inventory-v1",
        "scope": "known source/service families; NOT a live credential inventory",
        "secret_values_collected": False,
        "host_check_requested": host_check,
        "entries": [
            {**asdict(item), "runtime_hint": (
                detection(item.system, names) if host_check else "not checked"
            )}
            for item in CATALOG
        ],
        "limits": [
            "No password/API-key values or token hashes are read or printed.",
            "Docker host check shows only aggregate name matches; no env/inspect.",
            "NOT proof that a given account exists, is valid, or is stored safely.",
            "Host/desktop configuration and account recovery still need owner review.",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-check", action="store_true",
                        help="Read only running Docker container names; report aggregate matches")
    parser.add_argument("--json", action="store_true", help="Print safe JSON instead of table")
    args = parser.parse_args(argv)
    result = report(args.host_check)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("BRUISER — non-secret credential catalog")
        print("No passwords, API tokens, cookies, keys, or Docker environment values read.")
        print("This is not a vault or live-credential recovery tool.\n")
        for item in result["entries"]:
            status = " | " + item["runtime_hint"] if args.host_check else ""
            print(f"- {item['system']} [{item['kind']}] -> {item['consumer']}{status}")
        print(f"\n{len(result['entries'])} credential categories cataloged; "
              "distinct passwords/accounts may differ by installation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
