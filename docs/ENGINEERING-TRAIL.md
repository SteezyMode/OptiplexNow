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

## 2026-10-24: Owner-controlled GUI enrollment pilot, PR #184

- **Problem/evidence:** A fresh Linux account paired Wolf and ordinary SSH but could not access Games or Downloads until the owner bound its *distinct* restricted SSH key and approved the correct Wolf client ID manually. The older and newer MacBook profile identities differed. No host service restart was required.
- **Change/boundary:** Add a staged client public-key request and two separate GTK windows (client request / host confirmation) instead of teaching the client to grant itself owner rights. Requests use the already-owner-approved ordinary SSH connection, expire after 10 minutes, and cannot themselves modify the owner policy, Steam or `authorized_keys`. The host owner independently chooses the paired Wolf client ID, matches the client's six-digit code and authorizes a forced-command key against the existing reviewed host broker. Existing host files are privately backed up and code handles rollback of the key on a policy-write error.
- **Rejected alternatives:** No trust derived from client IP, Tailscale membership or a client-supplied Wolf ID. Do not use `ssh-copy-id` for the restricted credential, duplicate a private key across Linux users, automatically approve the first paired device or replace the reference host's working broker. No member-level admin SSH grant.
- **Testing/limits:** Offline request/denial/expiry/key-preservation/rollback tests and package/UI contract tests; exact-head CI and physical two-account acceptance remain distinct. The client and host must already have NOW installed, a trusted owner ordinary SSH path and initialized owner-host policy/broker. This is not a general fresh-host or member installer.
- **Migration/rollback:** Source-only until explicitly physically tested. Debian packaging adds helpers and Python GTK dependencies; package installation must not alter host `authorized_keys` or owner policy. Revert PR code to undo UI changes; any later host enrollment needs explicit per-device revocation rather than deleting all SSH access.
- **Next checks:** CI must pass; install a reviewed package on a disposable/test host and a fresh client; confirm owner approval succeeds, wrong code/unpaired ID/revoked device deny, host shell remains unavailable to the restricted key, previous owner key and active Steam session survive. Do not merge or call Private Alpha 1 ready based on unit tests.

## 2026-10-23: Fresh Linux-profile owner enrollment failure, PR #184 / issue #154

- **Observed:** On the Mint MacBook's normal `macbook` login, PR #184 build #608 found saved host/SSH user and a working ordinary SSH key; Moonlight was already paired, but Games refused and Downloads stayed on a misleading discovery/failure page. The fresh profile initially lacked its distinct `games-client/id_ed25519`. Repeating the wizard's `AUTHORIZE SSH KEY` did not create this restricted key or grant owner-device rights.
- **Identified:** A separate Wolf session disappeared when that profile closed Moonlight. The owner identified and approved its client ID using the existing host policy and manually enrolled the matching new restricted SSH public key via a forced-command entry. The original approved device was preserved and Downloads then worked. This is a **reference-host manual workaround**, not a shippable enrollment flow.
- **Change:** `src/downloads_flow.c` checks missing restricted credentials before the SSH queue call, stops stale discovery text on failed calls, and explains the distinct approval boundary. `src/main.c` states that SSH authorization and Moonlight pairing do not complete Games/Downloads owner enrollment, including the wizard's final page and SSH success message. Tests cover no-key fail-closed behavior and source/GTK regressions.
- **Rejected shortcut:** Never `ssh-copy-id` the restricted key as an unrestricted owner login, duplicate an existing private key across Linux accounts, or auto-bind arbitrary Wolf client IDs from Tailscale membership. Leave actual owner approval host-enforced.
- **Safety/test level:** Source patch only pending exact-head CI and physical UI test. No host containers, Steam directories, downloads, Jellyfin libraries, VPN or authorized keys changed by this source patch. Rollback is reverting these client-only text/guard changes; no config migration.
- **Still blocking Private Alpha 1:** Implement and physically test complete owner-approved graphical device enrollment, including independent certificate/client-ID binding, restricted forced-command installation, error recovery and revocation. A missing-key diagnostic is not the enrollment fix.

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

## 2026-10-22: PR #168 pinned real Wolf lobby schema and disposable Create

**Gap discovered:** PR #164/165 fixtures provided a Docker runner with
`type`, `name`, `image`, `env` but OMITTED required Wolf fields
`mounts`, `devices`, and `ports`. All earlier FakeWolf Create requests
were accepted without schema validation; that was **not proof a real Wolf
daemon would accept an owner's Steam runner**. Read current upstream
Wolf `CreateLobbyRequest`, `AppDocker__tagged` and `JoinLobbyEvent`
schema in `games-on-whales/wolf/docs/modules/dev/partials/spec.json` and
upstream `tests/testWolfAPI.cpp`. A session `moonlight_session_id` is
represented as a STRING in the API schema despite its C++ integer type;
do **not** convert it to an integer based on the native implementation.

**Code correction:** `src/owner_lobby.py` now fails closed unless the named
Steam runner is a tagged `docker` runner with all seven required fields
(`type/name/image/mounts/env/devices/ports`) and correct basic types;
the shared lobby fixture and missing-field denial cases were updated.
This does not alter the working host or Steam data.

**Real contract attempt:** The pinned-image disposable-only GitHub workflow
calls `GET /api/v1/openapi-schema` through the actual Wolf Unix socket.
`server/verify_wolf_lobby_contract.py` compares the live required fields,
Docker runner type and JoinLobby string-ID representation to NOW's fixed
request contract. Only after confirming the exact pinned image, per-run
scratch bind, no network privileges, no paired clients, no sessions and no
lobbies, it attempts at most ONE real `POST /api/v1/lobbies/create`, using
a harmless `process` runner (`sleep 10`), isolated profile data and
no Steam credentials. It never issues Join, Stop or cleanup POST; the
entire disposable container is removed afterward. A successful create
still does **not** validate Steam, named profile permissions, input/audio,
reconnection or a real Moonlight session.

**Actual pinned real Wolf result:** [GHA run 39761010450](https://github.com/SteezyMode/OptiplexNow/actions/runs/39761010450)
completed its isolated daemon job successfully. The live schema was compatible:
CreateLobby has 10 required request fields, tagged Docker runner has seven,
and Join's Moonlight session ID is a string. The exact one-shot
`POST /api/v1/lobbies/create` using ONLY disposable process runner
`sleep 10` returned `success: true` with a lobby ID. The sanitized report
recorded `actual_disposable_create: created_disposable_lobby`,
`actual_join_executed: false`, `actual_moonlight_session: false`,
`actual_steam_state_used: false`. This is the **first genuine Wolf lobby
Create POST accepted by NOW's HTTP adapter**; it is not real Steam launch.
The GHA container was disposed of after the test; no production state used.
Standard package build and sanitizer results are tracked separately in PR #168.

Reproduction: `python3 -m unittest discover -s tests -p
'test_real_wolf_lobby_contract.py' -v`; the pinned GitHub CI workflow
exercises the *real* Wolf implementation, not only that local fixture.

**Regression found in first standard CI:** Although [real Wolf run
39761010450](https://github.com/SteezyMode/OptiplexNow/actions/runs/39761010450)
passed, the `build-and-test` job failed
`test_wolf_socket_protocol.test_rejects_unapproved_operations_before_socket_connect`.
Its old denylist still contained the intentionally newly allowed
read-only `GET /api/v1/openapi-schema`. The test drove that request to
the fake Unix socket, so the assertion that **no** socket call occurred failed.
Corrected the denylist and added an explicit allowlist assertion while
preserving POST STOP/pair/settings denials. This is stale-test expectation,
not a failure of the real Wolf contract or a live security bypass. Full CI
must be rerun after the fix; final result belongs in PR #168 and #154.

**What NOT to repeat:** Avoid using incomplete Docker runner mocks as proof
of protocol compatibility. Do not add a live production Wolf helper or
attempt an owner Steam POST from normal client setup. The next production
step needs a disposable GPU-equipped host and genuine Moonlight session for
a verified Create+Join pair, authentication and an upstream bypass security
test. Previous source-only owner grants still do not enforce Wolf access.

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

**Sixth workflow result, verified and reproducible:** Run `39757678257`
completed the isolated **real Wolf** read-only probe successfully. The exact
resolved upstream image was
`ghcr.io/games-on-whales/wolf@sha256:b0ef253739f9bd49b71eba7e150c955fd05990c0d409e666d89236995351551a`.
Wolf returned `success: true` for all five inventories: **2 apps, 1
profile, 0 clients, 0 sessions, 0 lobbies**. The scope is actual daemon GETs
only; there was no paired client, GPU encoding, Steam lobby Create/Join POST,
or playback. The workflow was subsequently **pinned to the verified image
digest** to avoid test drift from the moving `:stable` tag. No owner hardware
or Steam state was involved.

**Release-safety CI failure and resolution:** The new third GitHub workflow
passed its *own* pinned-real-Wolf GET test in run `39757974832`, but the
standard build/test workflow `39757974840` correctly rejected its filename:
`test_repo_contract.WorkflowSafetyTests.test_only_documented_now_workflows_exist`
allowlisted only `ci.yml` and `release.yml`. This was an intentional
repository release-safety contract, not a test that should be bypassed or
deleted. After reviewing `wolf-real-compat.yml`, explicitly added that
single third workflow to the allowlist and added negative tests for release
publication, push triggers, privileged containers, host networking and Docker
socket mounting. The compatibility workflow uses `contents: read` and only
a disposable GitHub-hosted runner. All changes need full CI revalidation.
No reference-host deployment or Steam test is implied.

**Outcome:** see latest PR #167 GitHub Actions and comments; append exact observed
result and any CI fix here. Do not speculate from a missing API.

 A developer must not run a real Wolf POST
against the working reference server by interpreting this code's existence as approval.


## 2026-10-22: Host-local owner Steam pilot, source-only PR (after physical MacBook Wolf UI verification)

1. **Problem/evidence:** MacBook Mint 22.3, NOW v1.18.0, Moonlight 6.2.0 AppImage and Tailscale direct to OptiPlex. Live Wolf UI session was 1366x768 at 30Hz with audio channels 2. Through private Wolf GETs the active client matched exactly one paired-client row and one storage folder, with zero existing lobbies, and named profile `user` had one complete tagged Docker Steam runner. Nine total paired rows represent eight unique IDs; the duplicate was not the active MacBook. No native Create+Join had yet been tried.
2. **Code/change boundary:** Added `src/owner_host_pilot.py`, `server/owner_steam_pilot.py`, tests and `docs/HOST-OWNER-PILOT.md`. `inspect` runs the actual owner lobby planner in memory, using exactly one live Wolf UI session and paired identity from Wolf, then returns a non-sensitive report. `enroll` requires two explicit host-operator consents and writes private policy state only in a caller-chosen absolute directory, refusing replacement. `launch` requires three separate operator attestations, re-checks grant/session identity, and calls the existing fail-closed lease transaction. Source only: nothing deployed or changed on the OptiPlex, and NOW v1.18.0 Games still runs legacy direct Steam.
3. **Security decision/rejected shortcuts:** A normal NOW client or arbitrary SSH command cannot supply a trusted Wolf `client_id`; this pilot deliberately has no remote listener or automatic client invocation. The sole active session ID comes from Wolf itself and must match a unique paired record and the enrolled owner grant. An operator with Docker access is already a privileged host administrator, not a secure remote-device identity. Avoid mapping identity using an unauthenticated client payload/IP/Tailscale label; do not expose the pilot over HTTP or pretend its confirmation flags solve direct Wolf UI/Steam access bypass.
4. **Testing/evidence:** `tests/test_owner_host_pilot.py` uses fabricated Wolf GET/POST API fixtures, temporary owner stores, missing runner/client/session/duplicate/lobby cases, consent denial, enrollment and persisted lease checks. GitHub CI results belong to the PR; these are **not** new physical Steam launch evidence.
5. **Migration/rollback:** `inspect` is read-only. `enroll` writes to a separate explicit private pilot directory only and has no overwrite path. `launch` may change Wolf runtime and Steam data; do not attempt while desktop occupied or before independent Steam backup and review of legacy per-device symlinks. Existing uncertain/joined leases block retries and must not be manually deleted to bypass review; automatic safe stop, reconnect, and rollback are not yet implemented.
6. **Next actual check:** CI first; then run host `inspect` against the one physically active MacBook Wolf UI stream without production mutation. Subsequent host operator enrollment and live Create+Join require a deliberately approved idle-window test and separate Steam-writer safety assessment. The product broker must authenticate remote clients before wiring NOW Games; P0 issue #154 stays open.

**Separate post-alpha concept:** F7 in-stream quality controls for bitrate, resolution and FPS. Standard Moonlight Qt has a statistics overlay, not necessarily mutable live encoding settings. Because NOW invokes external Moonlight, an in-stream interactive panel requires client integration/fork or a controlled reconnect; do not imply one can be added simply by changing NOW's GTK launcher or a Wolf API GET. Keep this scoped after automatic Games acceptance.


## 2026-10-22: Real Wolf CreateLobby timeout bug before first owner Steam POST

1. **Problem/evidence:** The physical MacBook owner profile enrollment and real Wolf API
   preflight succeeded on the OptiPlex. A `5.3G` tar archive of
   `/etc/wolf/profile-data/user/WolfSteam` was created and `tar -tf` passed;
   the archive skipped ephemeral IBus sockets, and restore consistency remains
   untested. The host COSMIC desktop had a separate running Steam process.
   Upstream `src/moonlight-server/api/endpoints.cpp::endpoint_LobbyCreate`
   waits up to **20 seconds** for runner setup; NOW's socket bridge was capped
   at **5 seconds** and `docker exec` subprocess at **10 seconds**.
   An otherwise successful CreateLobby could outlive the NOW client,
   leaving a false `uncertain` lease and potentially live Steam data.
2. **Change/boundary:** `src/wolf_socket_adapter.py` now allows **26s**
   for the specific allowlisted `POST /api/v1/lobbies/create`.
   `src/wolf_docker_adapter.py` allows **35s** for the corresponding
   `docker exec` wrapper, giving the socket bridge headroom.
   GET requests and other POSTs retain 5s socket / 10s wrapper limits.
   No retries, new endpoints, live host commands or caller authentication
   were added. No owner machine, installed beta or Steam state was changed.
3. **Decision/rejected approach:** A global long timeout weakens other APIs.
   Retrying when Create times out risks two Steam writers; existing lease
   correctly blocks after ambiguous Create. Enforce per-method/path deadlines
   and retain fail-closed uncertainty instead.
4. **Tests/results:** `tests/test_wolf_socket_protocol.py` checks each
   timeout path and asserts outer Create timeout exceeds the inner Create
   timeout, which exceeds upstream's 20s. GitHub CI is required; this is
   fixture-level timeout verification, not a real live Steam Create+Join.
5. **Migration/rollback:** Source-only change; no configuration or on-disk
   migration. Revert the two modules if needed, without touching the
   private pilot enrollment. **Do not run real POST during active host Steam
   use without verifying separate storage and an agreed maintenance plan.**
6. **Next executable check:** Merge only on green CI; then use the enrolled
   MacBook Wolf UI session, backed-up named state and a single operator-approved
   host-local `launch` (no retries), collect sanitized result, inspect real
   lobby/session outcome and verify the desktop's independence. Update #154.


## 2026-10-23: Wolf video producer caps for named Steam lobby (#154, PR #174)

- **Evidence:** physical owner Steam CreateLobby generated GStreamer syntax errors and a 20-second setup timeout. NOW's planner put an empty `video_producer_buffer_caps` in the request. Upstream Wolf's lobby video producer consumes this field; Wolf's app/profile API reflector omits its active value.
- **Hypothesis, not confirmed fix:** empty producer caps may account for the parse error. Upstream Wolf uses `video/x-raw` in its legacy pipeline and `video/x-raw(memory:CUDAMemory)` in NVIDIA zero-copy mode, selected at startup. Do not guess or repeat POST to verify.
- **Code:** source-only planner/host-pilot rejects absent or unsupported caps before lease/POST. Operator must establish host-selected format from read-only Wolf startup logs and pass explicit `--video-caps`. No remote broker, automatic discovery or host runtime mutation was added.
- **Tests:** mock planning, durable lease and socket-protocol regressions distinguish intended input and rejected missing caps; GitHub CI applies to source only. It does not prove actual Steam gameplay, video encoding, or secure broker.
- **Next:** inspect current stalled lobby and uncertain lease read-only; verify Wolf's startup producer mode. Develop safe manual recovery for the existing failed attempt separately and only test a new Create+Join with explicit owner approval and an idle writer-safe host.

## 2026-10-23: Physical owner Steam success and PIN-gated lifecycle follow-up

- The reference OptiPlex's legacy NVIDIA pipeline needs `video/x-raw`. After
  PR #174, one real host-local CreateLobby/JoinLobby returned success and the
  MacBook actually played RE2R while the physical OptiPlex desktop remained
  independently usable. Evidence recorded in issue #154. This validates the
  gaming transport, **not** one-click NOW Games.
- The original failed Create left an orphan and a v1 `uncertain` lease. Wolf-only
  maintenance, read-only verification, archived lease and verified private
  owner Steam backup restored a clean host. No owner account/data was deleted.
- Upstream StopLobby checks the private lobby PIN, but the v1 lease did not
  persist it and the API's public reflector only exposes `pin_required`.
  We rejected guessed PINs, direct socket bypass and automatic retry.
- The follow-up source changes persist the PIN in a private 0600 version 2
  lease before Create; a host-only checked StopLobby marks uncertainty before
  POST and archives only after verifying state. The current physical v1
  session is intentionally left running; after planned shutdown, an explicit
  idle reconciliation can archive that old lease.
- Automated tests remain fabricated-state evidence until a version 2 physical
  stop/reconnect cycle is exercised. Immediate next check: finish current
  game naturally, verify runtime, test the guarded session lifecycle without
  modifying the host's desktop or unrelated services.

## 2026-10-23: Reference-host physical owner Steam lifecycle

- One source-only host operator pilot used verified NVIDIA legacy caps
  `video/x-raw` to Create+Join a named owner Steam lobby. The MacBook
  played RE2R while the OptiPlex physical desktop remained independent.
- After natural game exit and Moonlight disconnect, Wolf showed zero sessions
  and lobbies. With no Steam writer present, merged PR #175's host-local
  `reconcile` archived the older v1 lease; no Wolf restart or Steam data
  deletion was needed.
- One v2 Create+Join opened Steam. The lease persisted an owner-only PIN;
  the explicit guarded `stop` returned
  `{lease_archived:true,status:"idle",success:true}`, leaving the MacBook on
  Wolf UI. A subsequent preflight found one Wolf UI stream, zero lobbies, and
  an enrolled paired owner; a fresh v2 Create+Join reopened Steam without
  restarting Wolf or changing Steam/lease files manually.
- This is physical **source-only host operator** evidence, not accepted NOW
  Games-button usability. The GTK Games action still invokes the old direct
  `moonlight stream HOST Steam`; a trusted remote device-authenticated
  host-side authority, approved-client handoff, zero-terminal onboarding,
  sound measurements and a disposable clean-host test remain unverified.
- The new v2 lobby was left joined at end of test. Do not Create again
  without a verified stop and archived lease. Next implementation: connect
  the named owner lifecycle to Games through a narrow authenticated host
  request, without giving ordinary clients unrestricted SSH/Docker access.

## 2026-10-23: Bind future NOW Games actions to authenticated devices

- The reference host physically demonstrated owner Steam Create/Join, RE2R,
  independent desktop, Stop/recovery and relaunch. The current client Games
  button, however, still calls direct Moonlight `Steam` and can select
  per-device state rather than the durable named owner Steam workspace.
- The next minimal module is a strict `status/start/stop` host request gate,
  using the existing owner grant, actual paired-client inventory, live Wolf
  UI identity and lease/Stop implementation. The request cannot provide
  another client ID, profile, PIN, runner or caps. Invalid or revoked
  identities are denied and active leases block new writes.
- Deliberately NOT included: a TCP listener, unattended service, generic
  SSH command, install-time auth, NOW Games UI retarget, Moonlight orchestration,
  new session state machine or physical host deployment. A host-controlled
  authenticated binding for each incoming remote credential is still required
  before this code can be called from the actual NOW client.
- Why: direct SSH with existing Docker-admin permissions or trusting a
  client-submitted Wolf ID would widen rather than resolve the privilege
  boundary. Next acceptance step after CI: independently authenticate a
  remote owner device at host boundary and prove denial of forged, revoked
  and concurrent requests; only then wire the GTK Games button.

## 2026-10-23: Restricted per-client Games SSH key boundary

- The prior host-local owner Games request gate was unexposed, because it
  had no way to associate an incoming remote credential with the exact
  enrolled Moonlight device. Existing admin SSH keys have general host
  and Docker power, so using them for the one-click UI would be unsafe.
- Added an isolated Ed25519 client key and fixed SSH transport, paired with
  an OpenSSH `restrict,command=...` operator-reviewed public key line whose
  **fixed** command pins the corresponding host-approved Wolf client ID.
  This transport sends one bounded JSON `status/start/stop` request and
  never lets the client choose its device ID, profile, Steam PIN, container
  path or remote command. The host reads owner-only 0600 configuration and
  performs writer/process preflight before Start.
- Key issuance, host owner approval, authorized_keys installation, private
  host config and UI activation are **not automatic**, and no reference
  server files or running sessions were modified. This is an owner-only
  alpha approach, not cryptographic Moonlight certificate matching or
  shared-member privilege separation.
- Remaining risk: `restrict` limits what this SSH key can request but the
  host OS account may still have Docker privileges. Upstream Wolf direct
  Steam launch may bypass NOW's single-writer lock. A dedicated limited
  host authority and direct-app ACL need further acceptance before sharing.
- Next acceptance: offline tests, real restricted-key denial checks on
  disposable or status-only host, then graphical Moonlight Wolf UI startup,
  authenticated one-shot Start and actual RE2R playback without a terminal.
  See [owner Games SSH](OWNER-GAMES-SSH.md) and issue #154.

## 2026-10-23: Physical restricted Games SSH and Wolf storage audit

- Following merged PR #178 (main squash commit
  `3662034d49d9c91e10952d222c25487e03acc7aa`), the MacBook
  generated a separate Games-specific Ed25519 key. The owner manually
  installed the corresponding `restrict,command=...` forced-key entry
  for the already approved Wolf Moonlight client, leaving the existing
  administrator SSH access intact. Host Games config was created in 0600
  owner space with `enabled:false`, `legacy_links_reviewed:false`
  and observed legacy NVIDIA caps `video/x-raw`.
- **Physical read-only status accepted:** the MacBook invoked the
  restricted SSH client helper and received
  `{"status":"wolf_ui_connected","success":true}`. This establishes
  working bound credential -> host policy -> paired client status, not
  successful remote Steam Start/Stop or fresh automatic enrollment.
- **Physical denials accepted for tested cases:** an SSH `id` command
  using only the dedicated restricted key returned the host's denied
  response with exit 1; an attempted reverse forwarding returned
  `remote port forwarding failed` with exit 255. This does not
  establish wrong-key, revocation, arbitrary forwarding, or shared-user
  isolation.
- The host read-only preflight found no active owner Steam lease, no
  matching Steam processes or containers, one live Wolf UI session,
  zero lobbies and a still-disabled Games writer path. The owner Steam
  workspace exists as a non-symlink directory.
- The initial recursive Steam scan stopped after 500 directories.
  A subsequent **complete top-level** inventory of 8 numeric per-device
  Wolf folders found **5** Steam symlinks pointing to
  `/etc/wolf/profile-data/user/WolfSteam` and **3** separate
  Steam directories. This is not a full nested filesystem scan. No
  Steam files, aliases, runtime sessions or containers were modified.
- The actual Wolf direct Moonlight apps still include `Wolf UI`,
  `OptiPlex Studio Desktop` and `Steam`, while the existing
  named `user` profile also includes Steam. Direct Steam remains a
  bypass of NOW's lease and can access the shared writable owner
  directory through legacy aliases. We must not interpret five aliases
  as five currently running writers.
- **Chosen sequence:** first implement the restricted-device GTK Games
  flow, including Wolf UI launch/wait, one-shot Start, busy/reconnect,
  explicit guarded Stop and no fallback to direct Steam on failure.
  Then review back up/rollback and verify the installed Wolf API's
  direct-app removal support. Restrict **only direct** Steam with
  a controlled host change that leaves named-profile Steam, other
  direct apps, existing symlinks and personal game data untouched.
  Only enable real restricted-key Games writes in a supervised, tested
  owner window once other writer entry points are addressed. Keep
  current `enabled:false` and `legacy_links_reviewed:false`
  until then.
- **Not shipped:** the current released and source GTK Games button
  still calls `moonlight stream HOST Steam`; source-only broker
  helper and physical SSH status success do not imply zero-terminal
  consumer Games functionality. This is the next software milestone
  under issue #154.

## October 26, 2026 — Wolf fresh-host Steam profile compatibility checkpoint

A clean NOW Wolf host cannot be declared ready just because Docker reports the Wolf container running. Wolf's stable source `src/moonlight-server/state/default/config.v2.toml` currently uses `config_version=3` with global `[[apps]]`, including Steam, and reads `paired_clients[].app_state_folder`; the repository's earlier named-profile documentation describes version 2. The actual pinned image digest still determines which runtime contract a new host uses. One owner Steam home across paired devices is therefore **not safely implied** by merely installing Wolf.

Added a read-only, bounded, fail-closed config readiness inspector and exposed its result in the existing clean-host installer output, plus fixtures for both upstream layouts. Does not alter or enroll Wolf, move Steam state, grant admin access, or change any running server. Source-only and mock tested until CI and physical disposable-host verification. Rollback: revert this independent helper and the installer JSON addition. Next: identify/verify the exact Wolf digest and implement a narrow authenticated owner-to-`app_state_folder` mapping with a single-writer guard on that supported schema, followed by first game stream.

## October 26, 2026 — clean-host Docker/Compose guided dependency install (draft)

Issue #98: `host_install.py` previously required Docker and Compose already present, blocking a nontechnical clean-host journey. Development now adds a separate read-only package feasibility check and explicit local GTK → pkexec → APT action for *empty* Ubuntu/Pop!_OS 24.04 amd64 hosts, using Ubuntu `docker.io` and `docker-compose-v2`. Root independently rechecks that Docker commands, sockets, existing data and conflicting runtime packages are absent, and that an additive APT simulation works without removals/upgrades. No Docker group membership, Docker repository setup, unrelated service action or package-install postinst side effect from the NOW .deb. Installation of Docker can itself start the daemon and affect NAT/firewall behavior; the owner is warned before approval.

Deliberately rejected `curl | sh`, automatically purging Docker packages, taking over existing containerd/runc, adding root-equivalent group access and claiming a running daemon means Wolf is usable. Only code and mock/CI tests at this stage; no APT installation or physical host acceptance. Failure/ambiguous state requires manual package review, not automatic retry/rollback. Revert the opt-in GUI/helper code to roll back NOW behavior; never silently uninstall host runtime packages. Next: pass exact-head CI, then conduct a separate disposable clean-host Docker installation and native Wolf/Steam gameplay validation.

## October 27, 2026 — alpha #192 authority truth and #184 phone fresh-key test readiness

**Problem/evidence:** on a physically paired but NOW-restricted-unapproved Linux Mint client profile, direct Wolf-published Steam still launched (issue #192). Two October 26 iPhone QR approval attempts reused an already authorized restricted key and were correctly rejected: no successful new restricted key has been approved physically. The existing code already denies NOW-managed Games commands rather than falling back to Wolf direct Steam.

**Smallest change:** document two existing authorities for the one-owner alpha (Wolf pairing controls direct published-app streaming; independently approved per-device restricted credential controls NOW-managed host-service commands). Clarify host and client UI text that previously overstated what NOW approval gates. Add static source assertions for the scoped wording and the retained managed-Games no-fallback contract. Prepare the MacBook/phone test with a fresh per-profile key, existing Wolf-paired identity, safe stops on key reuse, and read-only prechecks.

**Rejected:** do not claim NOW owner denial revokes Wolf direct Steam; do not add an unrestricted direct-Steam fallback, a second enrollment protocol, a new privilege manager, automatic key replacement, or host-side Wolf pairing/published-app changes. Separate unrelated users remain excluded from Private Alpha 1. Production host, `authorized_keys`, Wolf config and Steam workspace untouched.

**Tests/evidence level:** GUI texts/source contracts only; CI must pass before merge. No new hardware approval or Steam stream validated by this change. For source rollback, revert this PR; no database, key or host migration required.

**One next step:** physically run the bounded `docs/OWNER-QR-ALPHA.md` MacBook `now-alpha` fresh-key and pinned iPhone approval sequence, verifying before/after restricted status, wrong phone/replay denial, and no interruption of Mac mini streaming. Stop on ambiguous or reused keys.

## October 28, 2026 — Videos: verified Jellyfin instance binding (#171)

**Problem/physical boundary:** NOW's Videos client obtains an authenticated `media` availability result from its trusted host, then independently probes `http://HOST:8096/System/Info/Public`. The source did not verify whether the host's Jellyfin probe and client's reachable endpoint refer to the *same* instance. This can silently select a different Jellyfin on a port-forwarded or misconfigured host.

**Smallest change:** the already-existing, read-only host loopback inventory now returns an allowlisted public `server_id` from the validated Jellyfin system response. The existing restricted SSH `media` reply carries it; the client checks that the response from HOST:8096 has the *identical* server ID before allowing its unchanged finite `available` token to reach GTK. Malformed/mismatched IDs are denied; the fixed local inventory refuses HTTP redirects and environment proxies. Arbitrary URLs, credentials, arbitrary hosts/ports and public discovery are not accepted. Older deployed beta host responses missing `server_id` retain the legacy behavior so owner installations are not broken by a client-only upgrade. Legacy success is **not** proof of instance identity.

**Tests/scope:** offline host/client ID matches, wrong/malformed/oversized identity, redirect and existing restricted grant controls, package/native CI pending. No host, service, firewall, Steam or user media state touched; no hardware Jellyfin playback proven. Rollback: revert this PR. **Next:** test Videos with an authorized clean client against the real host and log whether the host reports `server_id`; then add an owner-approved endpoint descriptor for installations where Jellyfin is not exposed directly on 8096, without teaching clients to follow an arbitrary remote URL. Do not start Windows work.

## October 28, 2026 — user login tray setting

**Request:** "Start minimized in tray at login" must be a normal Settings toggle; NOW already supports the command-line `--start-in-tray`, but lacked the XDG per-user desktop autostart control.

**Implementation:** Add a standalone GTK-free XDG login entry helper and a Settings checkbox. Explicit Save creates/removes only `~/.config/autostart/optiplex-now.desktop`; no system service, package post-install action, root requirement or change to the globally installed desktop launcher. Recognize the prior manual cp/sed entry as NOW's own and preserve unrelated/unrecognized entries; reject symlinks. Existing first-run and missing-tray safeguards still display NOW rather than leaving an invisible process. Cancellation causes no disk write.

**Tests:** disposable XDG home behavioral test for on/off, round-trip and refusal to clobber foreign/symlink entries, plus GUI source contract and CI build. Physical COSMIC/XFCE tray-manager acceptance remains pending. Rollback: disable in Settings or remove the exact per-user autostart file; no server, credential or media changes.

## October 28, 2026 — Videos host-approved same-host endpoint descriptor (development)

**Issue #171 / acceptance gap:** a client-only Jellyfin check hardcoded `HOST:8096`. The host has no approved way to announce that its same host publishes Jellyfin on another HTTP(S) port or short base path. A generic URL supplied by the client or arbitrary host discovery would be unsafe.

**Change:** Add optional owner-local `~/.config/optiplex-now/media-public-endpoint.json`, read only by the existing host-authorized `media` request. The mode-0600, owned, non-symlink JSON accepts exactly `{"version":1,"scheme":"http","port":8096,"base_path":"/"}` (or owner-approved https/other port/one safe path component). No hostname, credentials, URL, redirect or client-provided service ID is accepted. The host still probes the fixed local Jellyfin instance; the client probes the *selected host* using the approved scheme/port/base path and checks its `server_id` matches. Legacy endpoints without a descriptor retain the current 8096 path and finite `available` token. Native GTK accepts only a finite media helper output, never full network-provided URLs. TLS verification is not disabled.

**Scope:** this is a bounded protocol increment; no host config file is installed or silently created, no public DNS, NAT, Caddy, Jellyfin, accounts, library or port forwarding is changed. It supports owner-configured alternative same-host listeners only. A Caddy deployment on a different hostname or an installation with no local Jellyfin listener requires a later owner-approved host GUI/adoption path; do not pretend this change automatically discovers those services. The normal client still enters no URLs. Existing advanced user URL remains an explicit legacy override.

**Evidence/rollback:** Python mock tests for owner file validation, host-authorized instance match and malformed fields; native URL token tests. Full CI and physical Jellyfin playback still required. Rollback is reverting code; it does not modify any owner settings or service. Next: verify on clean authorized client with live host, then integrate owner host GUI endpoint selection/provisioning in the existing Videos setup journey, not a new platform or wizard.

## October 28, 2026 — Videos GUI for owner-reviewed existing Jellyfin

**Scope and reason:** the prior same-host endpoint support required writing a private JSON file by hand. The owner can now open Videos setup from the existing host Server Setup window, review whether Jellyfin answers only on fixed local port 8096, and approve an explicit same-host scheme/port/base path. No root or Docker access and no automatic writes when the window opens. The helper will **create once only** an owner-owned mode-0600 route file after a locally verified Jellyfin check. Existing files, symlinks, unsafe directories and mismatched states fail closed. Owner input does not supply a hostname, URL, credentials, container ID or Steam/Wolf data. TLS remains verified normally on the client; alternative external domains and unexposed Jellyfin are not solved.

**Evidence:** isolated Python tests cover read-only review, existing data preservation, offline refusal, path/scheme validation and source/packaging contract. CI and installed GTK startup smoke must pass; no physical client playback or host media adoption is claimed. No production host, Caddy or Jellyfin changed. Rollback: revert this PR; it creates no owner route until explicitly used by a human in the host GUI.

**Next:** on separate compatible disposable host or explicitly approved existing host, confirm the GUI detects Jellyfin, inspect the exact published listener, approve one route, then test a fresh authorized client Videos → Jellyfin login/playback and host/network restart. Avoid expanding into Plex or rewriting Jellyfin.

## October 28, 2026 — clean-host Jellyfin pilot with explicit owner OS authorization

**Motivation:** adoption-only Videos does not meet Private Alpha 1's fresh-host setup goal. New scoped path: a second opt-in GTK host window, separate from existing Jellyfin adoption, gathers a verified immutable Jellyfin image digest and owner-owned local library folder. Administrator check and separate install confirmation are both mandatory. A clean Ubuntu/Pop 24.04 amd64 host with Tailscale and Docker is the only candidate.

**Implementation:** official Jellyfin image pinned by SHA256; new dedicated Compose project and root-journaled workspace; owner UID/GID container, private persistent config/cache and read-only /media/library, drop all Linux capabilities, no-new-privileges. Publish only localhost 8096 and uniquely verified Tailnet IPv4 8096, not the host's Ethernet or public interfaces. Refuse pre-existing local ports, known Jellyfin containers, inaccessible Docker inventory, prior NOW Jellyfin state, unsupported OS, insufficient free space and unknown media paths/symlinks. Root installer rechecks after user-confirmed pkexec. Failed/interrupted state remains for manual review; never blind retry.

**Evidence only:** offline eligibility/render tests, refusal conditions, packed GUI smoke under disposable Xvfb; GitHub CI to run. No production system changed, no image pulled, no container installed, no physical stream verified. Separate disposable host test and native Jellyfin first-run account setup are still required before calling Videos accepted. Rollback of source is revert PR; physical deployments require a later reviewed uninstaller and must not indiscriminately remove volumes or files.

## October 28, 2026 — Jellyfin pilot port-publishing audit (#203 follow-up)

**Finding:** Docker Engine documents that releases before 28.0.0 may expose localhost-published ports to another machine on the same L2 segment. Even newer Docker in NAT/direct-routing configurations may allow connections through another host interface to an explicitly published host IP. A Compose manifest listing `127.0.0.1` and the host Tailscale IPv4 does not itself prove that Jellyfin is private; previous source only verified the container identity and labels, not actual mapped ports or media mount state.

**Smallest fix:** fail closed unless the live Docker Engine server reports version 28.0.0 or newer; retain the separate OS/Compose/Tailnet/port checks. After Compose starts, inspect the actual container and require exactly the approved published TCP 8096 bindings (allow unrelated *unpublished* EXPOSE metadata only), all three expected bind mounts with /media/library read-only, the expected user, state, image and project labels. Any mismatch becomes an interrupted/unverified install. If the exact container ID, pinned image, managed label and Compose project match, the installer attempts to stop that one container to contain unexpected exposure, preserving its volumes and journal for review. Ambiguous/foreign containers are never stopped and require manual inspection; no automatic remove or retry. Tests simulate old/new version strings, extra/wildcard mappings, wrong port, wrongly writable media, missing mounts, foreign project and malformed state. There is no Docker run in CI.

**Caveat and intentional release gate:** Docker >=28 is a necessary mitigation for the documented localhost issue, **not** a proof of Tailnet-only access; route/ACL/firewall configuration still matters. This gate may reject older Ubuntu/Pop Docker packages, including the other NOW dependency workflow, until an independently checked compatible engine is available. Do not automatically upgrade an existing daemon or bypass this requirement. Only a physical test from allowed Tailnet and disallowed LAN/external clients can establish network exposure behavior. No change to production host, Wolf, Caddy, Steam or live Jellyfin; no software release.

## October 28, 2026 — resolve Docker 28+ candidate on clean 24.04 hosts

Ubuntu Noble's current amd64 `docker.io` package is 29.1.3, and Ubuntu publicly announced the transition to 29.1.3 for 24.04 in March 2026. The earlier concern that our existing distro-only Docker installer inherently cannot satisfy the new Jellyfin pilot >=28 network gate is therefore not generally correct. Preserve the distro package pathway instead of adding a conflicting second upstream Docker repository. See Ubuntu Noble docker.io package and Ubuntu Discourse March 2026 container-stack update announcement.

**Concrete source fix:** the clean-host dependencies `--check` parses the simulated `Inst docker.io (VERSION ...)` package candidate, accepts >=28 only, and blocks missing/old/ambiguous candidates before any APT write. The already consented install still reruns simulation, makes no removals or upgrades, and now verifies the **running Docker daemon** is >=28 before reporting `docker_compose_ready`. Tests include Noble 29.1.3 with Ubuntu suffix, older 24/27, prerelease and malformed candidates, duplicates, and postinstall old-daemon refusal. An owner with an old *existing* Docker runtime is still blocked from automatic migration; no destructive replacement or service restart is attempted.

**Physical gate:** on clean Ubuntu and Pop 24.04 separately, record actual `apt-cache policy docker.io`, postinstall Docker daemon version, Compose availability, and pre/post port exposure on LAN and Tailnet. The check is a version gate, **not** proof that published ports are private. No live reference host touched; CI provides mocked APT evidence only.

## October 28, 2026 — existing Jellyfin + downloader shared-storage relationship review

**Decision:** NOW supports both existing-server adoption and optional clean-host provisioning. The production reference OptiPlex is an *existing-server compatibility baseline*, not a Docker/Gluetun/Jellyfin rebuild target. Its downloads and media library structure may be intricately shared. Do not create another directory tree, change the user's Jellyfin libraries, move torrents, adopt Docker volumes automatically, restart Gluetun, or modify Caddy simply to make NOW integration easier.

**Narrow source step:** the host-only, already privileged **VERIFY EXISTING SERVICES** read-only review reuses its single bounded Docker inventory to compare Jellyfin and qBittorrent bind-source metadata. Emit only finite enum hints for exactly shared, nested, disjoint, missing or unreviewable mounts. Do not return actual directories, container names/IDs, env, credentials, or any client-file capability. A separate fixed read-only `systemctl is-active jellyfin.service` probe detects a native Jellyfin installation only when the Docker inventory has exactly one qBittorrent and no Docker Jellyfin; it emits `native_jellyfin_library_mapping_unverified` rather than pretending to know how those paths intersect. Unknown stays unknown for absent installations, multiple Jellyfin instances, invalid metadata or missing Docker permission. No new host or network listener, no SSH file access or installs. Offline tests cover same/nested/disjoint, false prefix, malformed/oversized paths, missing/duplicate service candidates, redaction, and integration into the existing host review. CI and physical review are separate.

**Next risk to resolve:** a Docker bind overlap does not establish filesystem containment or library membership. Any eventual managed Files/download destination workflow needs **explicit owner-approved storage roots**, server-side realpath/openat-style containment and authorized per-client operations. It must separately validate Jellyfin library paths, qBittorrent save folder semantics and real media readability, preserve existing storage layouts and deny viewers. Preserve the existing owner's ordinary SSH/SFTP workflow, but do not treat that broad owner credential as an authorization mechanism for future viewer/member file management. Any future managed member files require separate server-enforced roots. CI source-only is not host adoption acceptance.

## October 29, 2026 — Native Downloads queue first (development PR)

**Physical observation and product boundary:** Two installed qBittorrent search engines (`torrentscsv.py`, `limetorrents.py`) were physically tried through VueTorrent. `Download with plugin` immediately queued to the default location; `Append to queue` gave no useful destination selection. The existing host's qBittorrent Docker mount expansion was owner-applied and physically verified separately: pre-existing `/downloads` and `/config` preserved; new writable `/library/bigdisk` and `/library/expansion` present for its media library directories. This does not justify replacing the torrent engine or modifying the owner's live media stack again.

**Small source milestone:** Make an in-app native current-downloads list (progress and sanitized state/name) the *default* Downloads page. Use the existing per-device restricted owner `downloads_queue` forced-command request; add an opt-in bounded `--native` presentation format to its client helper. Do not change host protocol or require VueTorrent login to inspect this queue. Retain the authenticated WebKit VueTorrent session behind an **Advanced** button within the same NOW window, with a **Back to Queue** action. Switching main NOW tabs keeps the existing WebKit instance; reopening Downloads shows the primary queue. `Refresh` is explicit; auto-polling, speeds, mutating actions and the new search/add control are **not** claimed in this PR. Existing client `--with-port` text protocol and server-side action remain compatible.

**Design guardrails:** The future result search and destination picker belong *on the same Downloads page*, next to a queue that stays visible. New result paths must be host-approved server roots translated to qBittorrent container paths; no arbitrary host path from a client, silent add to default, general shell, cross-host WebUI, download mutation, or new backend admin server. Search/add and owner-approved storage-root authorization are separate future PRs, rather than a single monolith. Current source PR has only mock and installed-package CI evidence; reference-client acceptance and real queue freshness remain open.
