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

**Owner-host operations in PR #165:** none. A developer must not run a real Wolf POST
against the working reference server by interpreting this code's existence as approval.
