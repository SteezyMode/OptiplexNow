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

## Read-only owner Steam inventory (in development)

The reference host's real Wolf API was queried on October 22:

- `GET /api/v1/clients` returned per-device `app_state_folder` values, with one client repeated identically. Identical duplicate records must be coalesced; conflicting duplicates must fail closed.
- `GET /api/v1/openapi-schema` confirmed `POST /api/v1/clients/settings`, but that client-wide folder setting is **not** proof of choosing the named owner Steam profile.
- The host has direct Steam under `moonlight-profile-id` and a persistent Steam app under named profile `user`. Wolf UI -> `user` -> Steam worked from Mac mini and MacBook; direct shortcuts were not yet verified on an unmodified fresh client. The preexisting symlinks are temporary host-side repairs, not permission models.

The optional, read-only `owner-status` action in `src/wolf-pair-local.py` reads `GET /api/v1/profiles` and `GET /api/v1/clients`, validates their shapes, reports direct Steam availability and named Steam profile **candidates**, counts unique paired clients and identical duplicates, and rejects conflicting client folder records. It deliberately does **not**:

- Call a write API, modify configuration, create links, adopt Steam state, or start a session.
- Treat one Steam candidate or a paired Moonlight certificate as proof of account ownership.
- Return profile PINs, Wolf runner environment, session encryption keys or per-client sensitive settings.
- Grant privileged Docker/SSH access to a member. The existing host helper still requires an administrative SSH operator; this is **not yet** a secure general-user broker.

The action is passed through the explicit trusted SSH allowlist and GTK-independent cancellable transport. It is **not wired to the normal Games button** until a server-enforced identity binding and supported named-profile launch mechanism are implemented and tested. The live reference host is unchanged; the helper on the reference machine may still be an older deployed version, so an untested status request is not evidence of a successful physical API call.

Owner profile continuity and revocation remain blocked on [#154](https://github.com/SteezyMode/OptiplexNow/issues/154), with the [one-owner identity contract](application-design.md#personal-server-identity-and-access-contract) governing the implementation. A future change may add a narrowly authorized mapping operation **only after** a disposable-client test confirms Wolf's native launch/ownership semantics and refusal paths.

## Owner-device policy module (not deployed)

`src/owner_access.py` adds a developer-only, host-local authorization foundation for [#154](https://github.com/SteezyMode/OptiplexNow/issues/154). The owner profile, server-local principal and Moonlight client IDs are stored in a private, versioned NOW policy file, separate from Wolf's Steam homes and client-side presets. Only an explicit local administrator operation can initialize the store or approve a device. A paired client with no approval resolves to no Games permission. Repeated identical Wolf client records are accepted; conflicting records refuse access. Local owner policy resolution itself is read-only and does not launch Steam.

`src/owner-access-local.py` is a **developer-only** CLI with `initialize`, `approve-device` and `resolve-games` operations. It requires the local root administrator and queries Wolf's existing read-only APIs to verify that named Steam profiles and device IDs exist. It is **not called by the normal client, not included in the public setup workflow, and not installed automatically on the live reference server**. A local policy grant does **not** revoke or constrain Wolf's independent pairing/stream access. Direct Wolf bypass and safe session-launch enforcement are still outstanding; do not invite a separate person onto the existing owner server on the strength of this file.

The code and tests preserve the path to a future `principals` list containing members and separate workspaces without making them available in the current release. Version 1 enforces one owner and one Steam workspace; adding member records later requires a validated schema migration and actual host security controls, not a GUI switch.

## Packaged code and deployment

| Component | Location / action |
| --- | --- |
| GTK client | `src/main.c`: Moonlight predefined PIN, native pairing dialog, refresh/authorize action |
| Pairing contract | `src/wolf_pairing.c/.h`: parse and reject malformed, duplicate or ambiguous pending-client lists and build validated PIN requests. No network I/O; still requires explicit client selection. |
| Async transport | `src/wolf_transport.c/.h`: runs the existing SSH Python bridge through GIO off the GTK main thread, with cancellation and bounded UI waits. No new host API or permissions. |
| Client transport | `src/wolf-pair-client.py`, installed at `/usr/lib/optiplex-now/wolf-pair-client.py`; runs a constrained SSH helper |
| Host helper source | `src/wolf-pair-local.py`, manually installed on the reference host at `/usr/local/libexec/optiplex-now/wolf-pair-local` |
| Moonlight client | External executable or AppImage/Flatpak, not a Wolf service |
| Future host installer | Must provision the helper, permissions, service discovery and network setup automatically; **not implemented** |

The host helper resolves `pair_secret` locally after validating a selected pending client's IP and index. The client submits selection and PIN over SSH stdin. The secret must not be sent to the normal client.

NOW generates a four-digit PIN with OS randomness, runs Moonlight's `pair HOST --pin ####` CLI option and uses the matching PIN for authorization. The temporary PIN is currently visible in the Moonlight process argv, even though it is not logged or stored in NOW settings. Do not describe this flow as eliminating all exposure.

The pairing dialog still requires explicit refresh and authorization of the intended pending client. Parsing a list and constructing a request use GTK-independent compiled tests. Pending-client refresh and authorization now run off the GTK main thread using the existing SSH bridge; dialog cancellation prevents stale results from updating a destroyed widget. This does not make pairing automatic or grant host access. It may open even when Moonlight has already paired. **Pairing is not automatically guaranteed on the Games button**, and existing pairing does not prove fresh-device enrollment.

## Security requirements

- No raw Wolf or Docker management API over a public network, no generic client shell access, no unrestricted passwordless sudo.
- Narrow broker with explicit host/device permissions, deterministic executable paths and a small allowlist.
- Bound SSH/API waits, validate all messages and client selection before authorizing, fail closed on changes.
- Confirm owner-authorized device enrollment. An account password is not automatic server permission.
- Redact PINs, Wolf pairing secrets, Moonlight certificate keys, Tailscale enrollment keys and session crypto material from diagnostics and code.
- Preserve already-paired device identity and user data during updates; do not reset working clients to test a new connection.

## Offline negative-path coverage

The Python client and host helper have simulated tests for: unavailable SSH, subprocess timeouts, malformed host responses, explicit Wolf refusal, changed client address, expired request index, missing host secret and invalid PINs. These mocks exercise fail-closed behavior **without contacting the real Wolf container**. They do not prove host identity when two pending requests can share an IP, nor replace a physical unpaired-client test.

## Required acceptance checks

- [x] Observe the local socket and schema.
- [x] Observe host helper read-only pending query.
- [x] Query the same helper from MacBook over SSH.
- [x] Implement native pairing dialog and generated predefined PIN in code.
- [ ] Complete authorization from a genuinely unpaired client.
- [ ] Verify wrong, expired or changed selection cannot authorize another device.
- [ ] Verify client reconnect without a new PIN.
- [ ] Verify Games streaming includes actual picture, audio and input after authorization.
- [ ] Test timeouts, SSH trust failures and cancellation without a frozen GTK window on a real fresh client (the new mock transport CI test does not replace this observation).
- [ ] Verify the final .deb on a client without prior NOW configuration.

## Future replacement

The Beta 1 fixed-path SSH approach is a development bridge. The future NOW Host installer must register managed services and provide a least-privilege host agent. The eventual account flow should allow an existing account's new device to be approved via a short-lived email link, then provision only that device's authorized access. Neither feature is currently shipped.

See [Beta acceptance](BETA-ACCEPTANCE.md), [Architecture](application-design.md), [Host installer](HOST-INSTALLER.md) and [Issue #94](https://github.com/SteezyMode/OptiplexNow/issues/94).
