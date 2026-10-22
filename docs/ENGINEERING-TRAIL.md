# Engineering trail: decisions, incidents and handoffs

This is the **append-only engineering trail**, not another roadmap or current-status page.
Read [PRODUCT](PRODUCT.md) for scope, [CURRENT-STATUS](CURRENT-STATUS.md) for today's accepted evidence,
[application-design](application-design.md) for permissions, and
[WOLF-PAIRING-HOST-CONTRACT](WOLF-PAIRING-HOST-CONTRACT.md) for the API contract.
The issue/PR references here preserve **why** changes happened and **what failed** so the
next developer does not repeat an already disproven approach.

## Required handoff at each iteration

Each behavior-changing PR must document **all** of these, in its PR body and a
brief dated entry in this file:

1. **Problem/evidence:** observed hardware, version, commands/API, what actually happened.
2. **Change/boundary:** affected modules and explicitly untouched host/user data.
3. **Decision and rejected approach:** upstream evidence and why the tempting shortcut was declined.
4. **Tests/results:** fixture vs CI vs physical test, exact failing checks and their resolution.
5. **Migration/rollback:** existing settings/state safety, release vs source distinction.
6. **Open risks/next executable check:** precise responsible next step; never mark P0 complete from CI alone.

Keep the latest **implementation status** in CURRENT-STATUS, not here. An unmerged PR
or a passing simulation is **not** a new deployable beta. Do not copy secrets,
Moonlight pairing keys, Steam state, VPN credentials or live session payloads.

## 2026-10-22: Fresh owner Steam client launch, issue #154

### Verified physical observations, not inferred causes

- Reference server: Linux/Pop!_OS with a running Wolf container and already authenticated
  owner Steam profile. MacBook (Mint XFCE) is a new client and Mac mini is a previous client.
- Wolf's direct Moonlight `Steam` application is under the special
  `moonlight-profile-id` and receives **per-device** application-state storage.
  Named profile `user` has Steam runner `WolfSteam` with persistent
  `profile-data/user/WolfSteam` state.
- Both tested clients had legacy per-client `Steam` **symlinks** aimed at that persistent
  folder. The MacBook initially failed direct Steam without the manual link.
  Thus existing physical success does **not** validate fresh-device automation.
- From the Mac mini and MacBook, **Moonlight -> Wolf UI -> user -> Steam** launched Steam.
  The Mac mini's NOW Games shortcut resumed working after updating NOW; an earlier Steam
  update and session changes mean the exact repair cause was **not isolated**.
- Live read-only `GET /api/v1/clients` had an identical repeated `client_id`.
  Do not naively treat duplicate entries as distinct devices. Conflicting duplicate
  records must fail closed.
- Moonlight Flatpak and AppImage may have separate device certificates on one laptop.
  Bind grants to the actual Moonlight identity NOW uses; don't inherit owner access
  from a laptop name, Tailscale IP or prior package.

### Progress and retained decision links

| PR | Delivered in repository | CI / physical boundary |
| --- | --- | --- |
| [#160](https://github.com/SteezyMode/OptiplexNow/pull/160) | Wizard saves valid service URLs independent of incomplete SSH fields; test helper extracted | CI passed after fixing stale exact-source-string Python assertions; **fresh physical Jellyfin setup retest remains** (#147) |
| [#161](https://github.com/SteezyMode/OptiplexNow/pull/161) | Personal Server is one-owner case of future Shared Server identities/permissions | Architecture contract only; no live admission enforcement |
| [#162](https://github.com/SteezyMode/OptiplexNow/pull/162) | Read-only Wolf profiles/clients inventory and redacted owner candidate status | CI passed after fixing a false-positive test: substring `pin` matched word `mapping`; no live helper deployment |
| [#163](https://github.com/SteezyMode/OptiplexNow/pull/163) | Versioned server-local owner principal, durable workspace, explicit approved/revoked devices, atomic private state | CI passed; developer-only root/admin tool; **not connected to Wolf permission enforcement** |
| [#164](https://github.com/SteezyMode/OptiplexNow/pull/164) | Offline Wolf UI-compatible named Steam lobby Create/Join request planner and denial checks | CI passed, still **no Wolf write API calls** |
| [#165](https://github.com/SteezyMode/OptiplexNow/pull/165) | Host-local lease and guarded create/join transaction; retains failure evidence, no silent double-start | CI result recorded on PR; still not connected to GUI, and no real Wolf POST or physical acceptance |

### Upstream behavior and rejected shortcuts

- Wolf UI [App.cs](https://github.com/games-on-whales/wolf-ui/blob/main/src/Scenes/Main/Body/Apps/App.cs)
  starts a **named profile** by obtaining the active Moonlight session and creating/joining
  a lobby. The lobby carries `runner_state_folder` derived from
  `profile-data/<profile-id>/<runner.name>`. Its [Lobbies.cs](https://github.com/games-on-whales/wolf-ui/blob/main/src/Resources/WolfAPI/v1/Lobbies.cs)
  uses `POST /lobbies/create` then `POST /lobbies/join`; both are under the
  Wolf `/api/v1` prefix.
- `POST /api/v1/clients/settings` supports `app_state_folder`, but this is
  **client-wide**, not proof of selecting the existing named owner profile.
  Do **not** automatically set it to `user` or guess `Steam` vs `WolfSteam`.
- The symlink repair was an emergency host workaround, **not** a permission model.
  Do not generalize it into product installation, create links per member, move existing
  Steam directories or share writable Steam state between independent concurrent sessions.
- A private Wolf lobby PIN is defense in depth, **not** admission control.
  Even if NOW refuses a button, a separately paired Moonlight client may still select
  upstream Wolf apps directly. No unrelated colleague may be invited yet.
- The public upstream [Wolf single-player/multiple-devices issue #496](https://github.com/games-on-whales/wolf/issues/496)
  covers a closely matching use case. Upstream behavior still needs pinned-version physical verification;
  **do not fork Wolf** solely based on simulations.
- Existing NOW `moonlight stream HOST Steam` continues to invoke the legacy direct-launch
  app; none of PRs #161–#165 quietly retargeted it. The owner-host reference installation
  is **not** a destructive test fixture.

### Current PR #165 transaction contract

- `src/owner_launch.py` is **not installed, invoked or network-exposed** by NOW client.
  It only runs if a future trusted host caller explicitly enables execution and passes
  a **server-authenticated** Wolf device ID.
- Under the same root-owned state lock as the owner policy, it checks the actual paired
  device grant, reads live Wolf profiles/apps/sessions/lobbies, and runs the #164 planner.
- It writes a versioned `owner-steam-lease.json` **before** the first possible Wolf
  POST, then tracks `creating -> created -> joined`. A timeout/error leaves a
  durable **uncertain** record; crashes leave at least a prior blocking state.
  Never automatically retry the same owner Steam home or stop a potentially running lobby.
- Lease records include only client/workspace IDs and an optional created lobby ID:
  **no Steam secrets, Wolf AES keys, runner config, profile PIN or lobby PIN**.
- All lease statuses block subsequent create attempts until explicit recovery is implemented.
  This favors preserving one writable Steam home over pretending reconnection is finished.
  A Wolf UI/direct Steam actor can still race with this lock: **the lease guards cooperating
  NOW code, not the upstream Wolf daemon**.
- Tests use a fake Wolf transport. Even passing all CI checks does **not** prove Wolf will
  honor `client_id` as the actual lobby join session identifier, accept the exact payload
  on the pinned host image, or protect upstream direct-app access.

### PR #165 regression history

- **First CI run:** native sanitizer checks passed. The build/package tests reached
  `test_join_failure_keeps_lobby_for_explicit_recovery` and failed because its
  assertion searched for the substring `stop` in the *entire request body*.
  Wolf's legitimate JSON key `stop_when_everyone_leaves` contains that word.
  This was a **false-positive test assertion**, not an observed Wolf stop call.
- **Correction:** inspect `(HTTP method, API path)` and reject only an actual
  `POST .../stop` request. Retest through the full PR CI pipeline. Never infer
  that a Wolf stop operation occurred from text matching serialized request data.
- The transaction is only exercised with fake Wolf replies and a disposable
  local state directory. Real Wolf Create/Join and recovery remain untested.

### Required next team actions, in order

1. **Disposable Wolf host/session only:** record exact Wolf image digest, APIs, app IDs, the
   `WOLF_SESSION_ID` vs `client_id` relation, actual request/response JSON schemas,
   video buffer caps, and whether create/join succeeds from the approved test device.
   Redact session AES material and secrets. Exercise failure after create, reboot, and reconnect.
2. **Host authority, not client shell:** implement an authenticated, narrow broker that derives
   the caller's Moonlight client ID from a verified credential. Never trust a user-supplied ID,
   Wolf profile ID, runner path or arbitrary JSON request body. Keep Docker/socket host-local.
3. **Upstream admission control:** prove unknown/revoked users cannot reach owner Steam via
   direct Moonlight Steam, Wolf UI, alternate apps, stale certs or guessed lobby IDs.
   Passing NOW's own authorization checks is insufficient. Refuse Shared Server invitations
   until this is proven.
4. **Lease reconciliation:** implement inspected, idempotent recovery that validates
   the Wolf lobby/session against the persisted transaction before clearing it. No timeout-only
   "lease expired, launch again" logic; explicit actor/owner confirmation on uncertainty.
5. **Only then** connect `Games` to the trusted broker and run a genuine **fresh**
   Linux client test: no manual symlink, no Wolf UI navigation, no Steam re-login,
   correct video/audio/controller, host desktop uninterrupted, repeat across MacBook,
   Mac mini, and Steam Deck; verify restart/upgrade, simultaneous click and revocation.
6. Continue P1 existing Jellyfin (#147/#148) and P2 VPN downloads/files **after P0**
   works in a physical end-to-end test. Keep eventual member accounts and new media
   provisioning deferred per PRODUCT.

## 2026-10-22: PR #166 disposable Wolf socket-protocol verification

### Problem and evidence

- Previous #165 `FakeWolf` Python tests return Python dictionaries directly. They **never**
  exercised HTTP request framing, JSON/Content-Length, Unix sockets, Docker's
  child process boundary, response truncation or Wolf API refusal. Do not call
  those tests a protocol integration test.
- Wolf's upstream UI code provides the Create/Join JSON shape, but **does not**
  prove the reference host's pinned Wolf image accepts our request. Real Wolf
  Create/Join remains an outstanding physical/disposable test.

### Changes and owned modules

- `src/wolf_socket_adapter.py`: explicit GET allowlist for
  `clients/profiles/apps/sessions/lobbies`; POST allowlist for
  `lobbies/create` and `lobbies/join` **only**. Bounded request/response
  sizes, 5-second socket timeout, complete HTTP status and length checks,
  and sanitized errors. Rejects chunked/encoded replies until explicitly
  verified and supported, rather than misparsing transport.
- `src/wolf_docker_adapter.py`: a host-local bridge with fixed
  `docker exec -i wolf python3 -c <reviewed-local-script> METHOD PATH`.
  JSON request data crosses **stdin**, not argv; stderr is discarded and raw
  session data must never be logged. No arbitrary Docker command, shell,
  network listener, or Wolf admin API is accepted.
- `tests/test_wolf_socket_protocol.py`: a **real temporary AF_UNIX HTTP
  server** and a Docker-command stand-in that executes the *same adapter
  source* in a local child Python process. Tests validate entire seven-step
  owner launch request ordering, successful state lease, no repeat launch,
  unsafe endpoint rejection, HTTP length/framing/JSON refusal, ambiguous
  first POST and persisted blocking lease.
- New adapter remains a **developer module only**: not included in the
  published host installer, not exposed to clients, and not called by the
  existing Games shortcut. No active Wolf container or Steam files changed.

### Rejected shortcuts / failure modes

- Do not expose generic Wolf `POST` support for convenience. A caller with
  the socket has administrative-level Wolf access.
- The old `wolf-pair-local.py` raw Docker bridge reads only 4096 bytes from
  stdin for POST; a lobby runner config can be larger. Do **not** reuse that
  bridge for lobby creation. The new adapter has a separate bounded request
  protocol and deliberately does not rewrite existing pairing behavior.
- Do not suppress ambiguous response framing, retry on timeout or automatically
  clear `owner-steam-lease.json`: a partial POST may already have created a lobby.
- An allowlisted host bridge is **not authentication**. Wolf's upstream direct
  apps and Wolf UI are still outside NOW's device-grant enforcement.
- This fixture answers protocol *compatibility in a simulated daemon*, not
  Wolf version/driver compatibility or actual Steam video/input.

### Reproduce and hand off

Run `python3 -m unittest discover -s tests -p 'test_wolf_socket_protocol.py' -v`
or the entire `python3 -m unittest discover -s tests -v` suite. PR #166 CI
result must be entered in its PR and #154; native package tests cannot replace
a disposable real Wolf host.

**Next required proof:** on a disposable host with an actual compatible Wolf
image digest, confirm response framing and the exact `GET /api/v1/apps`,
`GET /api/v1/sessions`, `POST /api/v1/lobbies/create` and
`POST /api/v1/lobbies/join` schemas while hiding keys/PINs. If this adapter
rejects chunked transfer or a different session ID, update the explicitly
tested protocol contract **before** production enablement. Do not ask an owner
to test the writing path against their live Steam state. Then implement
authenticated host broker, Wolf direct-app admission denial, lease recovery
and physical fresh-client P0 acceptance.

## 2026-10-22: PR #167 attempted real Wolf daemon on isolated CI runner

**Problem:** PR #166 tests real Unix-socket bytes but its daemon is a Python
simulation. Real Wolf could reject our socket/framing or fail to start. This
iteration probes the *real upstream image* without using the user's running
OptiPlex or pretending a mock is Wolf.

**Change:** `server/probe_real_wolf.py` refuses any container except one
with a unique `now-wolf-compat-*` name, explicit disposable label, exactly
one scratch `/etc/wolf` storage mount, nonprivileged execution and
`--network none`. It reads only the five GET inventory endpoints and reports
counts, not raw Wolf profile/client/session fields. The special
`.github/workflows/wolf-real-compat.yml` job on GitHub's hosted runner
attempts to boot upstream `:stable` with no GPU, no uinput/uhid, no Docker
socket and no port exposure, and records its **resolved image digest**. No
POST and no credentials; one-use container and scratch volume are cleaned up.
`tests/test_real_wolf_probe.py` checks production-container rejection and
allowlisted read-only operations with a mocked Docker command.

**Verification category:** an actual upstream image **boot attempt** on a
hosted non-GPU runner. If Wolf refuses to start, the step reports BLOCKED
(no daemon test performed), even when the workflow status is success.
If the five APIs respond, that proves only the *real daemon read-only GET*
subset with this exact image and environment. **No active Moonlight session,
GPU stream, actual lobby Create/Join, or fresh owner setup is verified.**

**Rejected approaches:** do not run a second Wolf on the personal server,
mount `/etc/wolf` or the real host's Docker socket, reuse Steam data,
enable host ports or mark real session behavior accepted from this job.
Wolf's official quickstart requires render/input devices, which hosted
runners lack. A dedicated **disposable GPU-equipped machine** is needed
for Create/Join/session/reconnect physical acceptance. See
[REAL-WOLF-VALIDATION.md](REAL-WOLF-VALIDATION.md).

**First workflow result:** Run `39755626372` stopped in the *preflight
unit test* before running Docker. Test `test_probe_only_uses_five_gets_and_redacts_session_keys`
incorrectly scanned the whole Docker argv for the string `POST`, even though
the embedded **reviewed source code** in argv legitimately contains that
word. No POST request was executed. The corrected test checks the exact
selected HTTP method (`argv[-2] == "GET"`) for each of the five requests.
This is a false-positive assertion; it is not a real Wolf startup failure.
Rerun PR CI before updating the real-daemon evidence.

**Second workflow result:** Run `39755752062` passed the Python
preflight and pulled/started the upstream Wolf container far enough for Wolf to
create root-owned `cfg/config.toml`, `cfg/key.pem` and `cfg/cert.pem` in the
disposable scratch directory. The job failed in trap cleanup because the hosted
runner user could not remove root-owned files. This is a **fixture cleanup
failure** rather than an API pass. Changed cleanup to use `sudo rm -rf
--one-file-system` only if the target path exactly matches the current runner
`$RUNNER_TEMP/now-wolf-compat-$GITHUB_RUN_ID`, after removing that specific
container. The workflow now emits a sanitized actual probe report to logs as
well as its summary. Recheck both physical-read-only outcome and cleanup.

**Third workflow result:** Run `39756053115` successfully pulled the
actual upstream image, booted the container and cleaned up the scratch state,
but the read-only probe reported `Disposable Wolf must have exactly one
isolated mount`. No GETs were executed. The original gate assumed Wolf
would use only the explicit scratch bind. The image also supplies other Docker
mounts. Updated the gate to accept **only image-declared Docker-generated
64-character hex-named anonymous volumes**, and still refuse any other bind,
named/persistent volume, privileged container or host network. Added positive
and negative volume tests. This is a strict probe-gate compatibility change,
not a real Wolf API result. Rerun and record the actual gate result.

**Fourth workflow result:** Run `39756922735` printed sanitized mounts
from the running upstream Wolf image:
`/etc/wolf` (single scratch bind), plus an anonymous 64-hex Docker volume at
`/run/user/wolf`. The image declares `/run/user/wolf/` **with a trailing
slash**, which Docker normalizes off `Mounts[].Destination`. The gate rejected
that safe mount before its first GET. Corrected the comparator by normalizing
only declared destination trailing slashes; still requires a Docker-generated
64-character hex name, a declaration in the image, no extra binds and no host
network/privilege. A regression fixture now reproduces the exact spelling
difference. The fail-closed diagnostic proves the real image mount layout,
**not** the API semantics yet.

**Fifth workflow result: first actual real Wolf read-only API PASS.**
PR #167 run `39757247197` on a disposable Ubuntu 24.04 GitHub-hosted
runner successfully booted upstream Wolf with `--network none`, no GPU/input
devices, no Docker socket, a newly created `/etc/wolf` scratch bind and the
image-declared anonymous `/run/user/wolf` volume. The strict container
safety gate passed. The **real daemon**, accessed via our tested Python
HTTP-over-Unix socket adapter inside the running container, returned all five
allowlisted successful GET inventories with these counts: 2 apps, 1 profile,
0 clients, 0 sessions, 0 lobbies. The sanitized JSON explicitly reported
`result: pass`, `steam_stream_tested: false` and `creates_lobbies: false`.
The job was successful and its cleanup removed the temporary container and
scratch state. This **does not validate the POST Create/Join protocol** or
hardware streaming. Exact upstream image digest is echoed in the follow-up
workflow for future reproducibility; the mutable `:stable` tag is not a
long-term test pin.

**New executable next step:** a separate GPU-equipped **disposable** Wolf
host plus an active disposable Moonlight Wolf UI session for the first *real*
`/api/v1/lobbies/create` and `join` pair. Use owner-independent Steam
state and the current policy/lease checks. Confirm video buffer caps and
actual session ID mapping; collect only sanitized outputs. Do **not** use
the owner's reference Steam environment or invite other users.

**Outcome:** see latest PR #167 GitHub Actions and comments; append exact observed
result and any CI fix here. Do not speculate from a missing API.

 A developer must not run a real Wolf POST
against the working reference server by interpreting this code's existence as approval.
