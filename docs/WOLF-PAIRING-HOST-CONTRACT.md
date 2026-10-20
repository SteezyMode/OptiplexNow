# Wolf pairing and host integration contract

**Status:** implementation exists in `main`, but the full fresh-device pairing flow has not passed acceptance. Updated 2026-10-21. This is a client/host interface record, not a turnkey server installer.

## Verified test-host environment

- Pop!_OS 24.04 server with Docker container `wolf`.
- Wolf Unix socket inside the container: `/run/user/wolf/wolf.sock`.
- API document: `GET /api/v1/openapi-schema`.
- Pairing endpoints: `GET /api/v1/pair/pending` and `POST /api/v1/pair/client`.
- Session endpoints observed: `GET /api/v1/sessions` and `POST /api/v1/sessions/stop`.
- Pending requests expose `client_ip` and `pair_secret`; authorization uses `pair_secret` and four-digit `pin`.
- The host's trusted SSH operator account can reach Docker without sudo; this is **administrative power**, not a safe permission to give a normal end user.
- Host pairing helper's read-only `pending` command returned an empty list successfully, both on the host and through SSH from the MacBook.
- A completed first-time pairing POST from the native NOW UI has **not** been observed on a newly unpaired client.

The Wolf sessions API can include encryption keys. Never log raw session responses or secrets.

## Packaged code and deployment

| Component | Location / action |
| --- | --- |
| GTK client | `src/main.c`: Moonlight predefined PIN, native pairing dialog, refresh/authorize action |
| Pairing contract | `src/wolf_pairing.c/.h`: parse and reject malformed, duplicate or ambiguous pending-client lists and build validated PIN requests. No network I/O; still requires explicit client selection. |
| Client transport | `src/wolf-pair-client.py`, installed at `/usr/lib/optiplex-now/wolf-pair-client.py`; runs a constrained SSH helper |
| Host helper source | `src/wolf-pair-local.py`, manually installed on the reference host at `/usr/local/libexec/optiplex-now/wolf-pair-local` |
| Moonlight client | External executable or AppImage/Flatpak, not a Wolf service |
| Future host installer | Must provision the helper, permissions, service discovery and network setup automatically; **not implemented** |

The host helper resolves `pair_secret` locally after validating a selected pending client's IP and index. The client submits selection and PIN over SSH stdin. The secret must not be sent to the normal client.

NOW generates a four-digit PIN with OS randomness, runs Moonlight's `pair HOST --pin ####` CLI option and uses the matching PIN for authorization. The temporary PIN is currently visible in the Moonlight process argv, even though it is not logged or stored in NOW settings. Do not describe this flow as eliminating all exposure.

The pairing dialog still requires explicit refresh and authorization of the intended pending client. Parsing a list and constructing a request now use compiled, GTK-independent tests; this is not nonblocking pairing or automatic approval. It may open even when Moonlight has already paired. **Pairing is not automatically guaranteed on the Games button**, and existing pairing does not prove fresh-device enrollment.

## Security requirements

- No raw Wolf or Docker management API over a public network, no generic client shell access, no unrestricted passwordless sudo.
- Narrow broker with explicit host/device permissions, deterministic executable paths and a small allowlist.
- Bound SSH/API waits, validate all messages and client selection before authorizing, fail closed on changes.
- Confirm owner-authorized device enrollment. An account password is not automatic server permission.
- Redact PINs, Wolf pairing secrets, Moonlight certificate keys, Tailscale enrollment keys and session crypto material from diagnostics and code.
- Preserve already-paired device identity and user data during updates; do not reset working clients to test a new connection.

## Required acceptance checks

- [x] Observe the local socket and schema.
- [x] Observe host helper read-only pending query.
- [x] Query the same helper from MacBook over SSH.
- [x] Implement native pairing dialog and generated predefined PIN in code.
- [ ] Complete authorization from a genuinely unpaired client.
- [ ] Verify wrong, expired or changed selection cannot authorize another device.
- [ ] Verify client reconnect without a new PIN.
- [ ] Verify Games streaming includes actual picture, audio and input after authorization.
- [ ] Test timeouts, SSH trust failures and cancellation without a frozen GTK window.
- [ ] Verify the final .deb on a client without prior NOW configuration.

## Future replacement

The Beta 1 fixed-path SSH approach is a development bridge. The future NOW Host installer must register managed services and provide a least-privilege host agent. The eventual account flow should allow an existing account's new device to be approved via a short-lived email link, then provision only that device's authorized access. Neither feature is currently shipped.

See [Beta acceptance](BETA-ACCEPTANCE.md), [Architecture](application-design.md), [Host installer](HOST-INSTALLER.md) and [Issue #94](https://github.com/SteezyMode/OptiplexNow/issues/94).
