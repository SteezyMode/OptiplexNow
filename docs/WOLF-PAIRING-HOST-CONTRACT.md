# OptiPlex NOW — Wolf pairing and host integration (Beta 1)

**Status (2026-10-21): implementation in progress, not yet end-to-end tested.** This is a reproducible engineering record, not a claim that a fresh server can be installed automatically.

## Intended product workflow

On the client: install NOW -> sign in -> discover authorized host -> pair Moonlight once in NOW -> launch Games or Videos. The host side must eventually be provisioned by NOW, not configured manually by each end user. The development OptiPlex is a test fixture, **not a product dependency**.

Jellyfin login integration and per-session termination are **deferred** for Beta 1. The existing confirmed **Restart streaming service** is the emergency global Wolf reset; it interrupts active streams. Do not mistake a running Wolf container or desktop container for proof of a connected user.

## Verified on the development host (2026-10-21)

- Host OS: Pop!_OS 24.04 LTS; Docker container name `wolf`.
- Host login account has permission to run `docker info` without `sudo`. This is effectively administrator-level capability; never extend it to an untrusted NOW client.
- Wolf's local Unix socket **inside the container** is `/run/user/wolf/wolf.sock`. Previous guesses `/var/run/wolf/wolf.sock` and `/tmp/wolf.sock` were incorrect.
- `curl` is absent inside this Wolf image; `python3` works for Unix socket requests.
- A local GET `/api/v1/sessions` returned HTTP 200 and real stream sessions, including their dimensions and frame rate. **The response also contains session encryption material. Never log or display raw session JSON.**
- The OpenAPI document is at **GET `/api/v1/openapi-schema`**, not `/openapi.json`.
- The installed API schema confirms: GET `/api/v1/pair/pending`, POST `/api/v1/pair/client`, GET `/api/v1/sessions` and POST `/api/v1/sessions/stop`.
- `PendingPairClient` provides **`client_ip`**, **`pair_secret`**; `PairRequest` requires **`pair_secret`**, **`pin`** (the PIN displayed by the Moonlight client).
- Only read-only schema and session queries were exercised on the host. **A live pairing POST has not been tested.**

## Code ownership / intended boundaries

- `src/wolf-pair-local.py`: the constrained helper intended to run **on the host**. It queries pending pairing requests but exposes only client IP and ordinal index, then accepts an index, original IP and PIN on stdin and resolves the pairing secret locally. Do not output the secret.
- `src/wolf-pair-client.py`: the **client** SSH transport. Uses already trusted SSH keys, a pinned host key and a fixed host-side helper path. PIN is passed on stdin, never in a command-line argument.
- `src/main.c`: GTK setup and Games UI. Moonlight pairing currently launches Moonlight separately and directs users to the Wolf PIN page. GUI integration of the new helper is **not done**.
- `package.py`: bundles the client transport in the NOW .deb. Packaging this file does **not** install the host helper on a remote server.
- `src/restart-streaming.sh`: current confirmed global Wolf service restart (with user confirmation); do not replace with speculative per-session container kills.

## Host provisioning contract (not yet implemented)

1. Ensure Wolf and its local Unix API are available.
2. Install **a vetted copy** of the host helper at `/usr/local/libexec/optiplex-now/wolf-pair-local`. Its location and permissions must be explicit and checked.
3. Decide and enforce which SSH principal may run this helper; **do not grant all remote users access to Docker**, a generic shell, Wolf's unrestricted management API, or passwordless unrestricted sudo.
4. For a trusted owner/test fixture, existing SSH access can exercise the pairing path temporarily; **this is not an appropriate multi-user sharing security model**.
5. Confirm pending list and actual PIN pairing with a newly unpaired Moonlight client before claiming it works.
6. The eventual host installer should carry out provisioning/validation with rollback and without breaking other server services.

## Security / correctness acceptance

- Never expose Wolf's Unix socket as a public TCP listener.
- Do not persist, emit, or put `pair_secret`, session AES key/IV, or pairing PIN into logs, URLs, argv, telemetry, or UI history.
- Verify `client_ip` plus selection still match at pair time; reject changed or expired pairing requests.
- Bound IPC/network waits and message sizes; handle malformed JSON and API errors.
- Treat any SSH user with Docker group membership as privileged. Authorization must be specific to the host owner and explicitly trusted devices.
- No broad network scans, automatic pairing approval, arbitrary Docker actions, or default credentials.
- Tests must distinguish **CI passed** from **host validated** and **fresh client tested**.

## Beta 1 verification checklist

- [x] Locate actual Wolf Unix socket and query live session API without changing sessions.
- [x] Confirm OpenAPI endpoint and required pairing fields on installed Wolf version.
- [x] Verify development host login can access Docker without sudo.
- [ ] Verify host helper installed at the declared path; its permissions and ownership.
- [ ] Execute read-only helper `pending` on the development host.
- [ ] Complete actual Moonlight -> Wolf PIN pairing with test client.
- [ ] Add and test NOW GTK pairing dialog with clear recovery behavior.
- [ ] Prove wrong/expired client selection cannot pair another device.
- [ ] Smoke test Games, Videos and dashboard following a clean .deb install.
- [ ] Test onboarding on a fresh Linux client in the ten-minute acceptance window.

## Future architecture — not Beta 1 commitments

Investigate Headscale and real OptiPlex NOW identity/sharing, a restricted host management agent, Wolf APIs before considering a fork, and low-end Moonlight streaming profiles. See GitHub issue #85. **The product goal is Steam Remote Play ease with Moonlight performance and a simple GUI, independent of any one personal server.**

Update this file *in the same PR as behavior changes*. Mark observed facts as verified with the date and reserve unchecked checklist items for anything not reproduced.
