#!/usr/bin/env python3
"""Device-local Bruiser Music credential storage via the OS Secret Service.

Store the dedicated, revocable OpenSubsonic *user app password*, never the
DroppedNeedle administrator login or slskd API key. No local plaintext files,
credential-bearing arguments, secret environment variables or CLI logging.

The caller invokes lookup/store/clear on a background subprocess. Secrets
for store travel over stdin; lookup delivers credentials through a bounded
stdout pipe. The schema includes the exact approved URL (host + port + path)
so a changed destination never receives an old server's password.
"""
from __future__ import annotations

import argparse
import sys
from urllib.parse import parse_qs, urlencode

from music_subsonic import MusicTransportError, endpoint_for

SCHEMA_NAME = "com.bruiser.music.open-subsonic"
MAX_PAYLOAD = 4096


class VaultError(Exception):
    """User-facing, credential-free error."""


def canonical_server(server: str) -> str:
    try:
        endpoint = endpoint_for(server, "ping")
    except MusicTransportError as exc:
        raise VaultError("Invalid music server URL.") from exc
    return endpoint.removesuffix("/subsonic/rest/ping")


def normalize_auth_form(form: str) -> str:
    if not isinstance(form, str) or len(form.encode("utf-8")) > MAX_PAYLOAD:
        raise VaultError("Invalid music credential length.")
    try:
        fields = parse_qs(form, keep_blank_values=True, strict_parsing=True,
                          max_num_fields=2)
    except ValueError as exc:
        raise VaultError("Invalid music credential format.") from exc
    if set(fields) != {"api_key", "username"} or any(len(v) != 1 for v in fields.values()):
        raise VaultError("Invalid music credential fields.")
    key, username = fields["api_key"][0], fields["username"][0]
    if not key or len(key) > 1024 or len(username) > 128:
        raise VaultError("Invalid music credential fields.")
    if any(ord(ch) < 32 for ch in key + username):
        raise VaultError("Invalid music credential fields.")
    return urlencode({"api_key": key, "username": username})


def secret_api():
    try:
        import gi
        gi.require_version("Secret", "1")
        from gi.repository import Secret
        schema = Secret.Schema.new(
            SCHEMA_NAME, Secret.SchemaFlags.NONE,
            {"server": Secret.SchemaAttributeType.STRING}
        )
        return Secret, schema
    except (ImportError, ValueError, AttributeError) as exc:
        raise VaultError("OS keyring integration is unavailable.") from exc


def vault(op: str, server: str, form: str | None = None,
          provider=None) -> str | None:
    canonical = canonical_server(server)
    Secret, schema = provider() if provider is not None else secret_api()
    attributes = {"server": canonical}
    try:
        if op == "lookup":
            secret = Secret.password_lookup_sync(schema, attributes, None)
            return normalize_auth_form(secret) if secret else None
        if op == "store":
            normalized = normalize_auth_form(form)
            ok = Secret.password_store_sync(
                schema, attributes, Secret.COLLECTION_DEFAULT,
                "Bruiser Music — saved listening session",
                normalized, None
            )
            if not ok:
                raise VaultError("The OS keyring did not save this device.")
            return "saved"
        if op == "clear":
            Secret.password_clear_sync(schema, attributes, None)
            return "cleared"
    except VaultError:
        raise
    except Exception as exc:
        # Never leak upstream keyring errors; some contain paths/metadata.
        raise VaultError("OS keyring is unavailable or locked.") from exc
    raise VaultError("Unsupported keyring action.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bruiser Music OS keyring helper")
    parser.add_argument("operation", choices=("lookup", "store", "clear"))
    parser.add_argument("server_url")
    args = parser.parse_args(argv)
    try:
        form = None
        if args.operation == "store":
            # Store only the explicit one-time credentials after server login
            # has succeeded; never read from argv, env, or a plaintext file.
            content = sys.stdin.buffer.read(MAX_PAYLOAD + 1)
            if len(content) > MAX_PAYLOAD:
                raise VaultError("Music credential length exceeded.")
            try:
                form = content.decode("utf-8")
            except UnicodeError as exc:
                raise VaultError("Invalid music credential encoding.") from exc
        result = vault(args.operation, args.server_url, form)
        if result is None:
            return 3  # Not previously connected on this device.
        if args.operation == "lookup":
            sys.stdout.write(result)
        else:
            sys.stdout.write(result + "\n")
        return 0
    except VaultError as exc:
        print(str(exc), file=sys.stderr)
        return 4  # Never silently claim a device was remembered.


if __name__ == "__main__":
    raise SystemExit(main())
