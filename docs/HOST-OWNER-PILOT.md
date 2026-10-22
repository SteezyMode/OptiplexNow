# Owner Steam host-local pilot (not a public NOW client feature)

## What this provides

`server/owner_steam_pilot.py` makes the existing host-local owner Steam
lobby transaction reachable from a trusted **operator shell** in an
explicitly gated way. It is not part of the installed v1.18.0 client, does not
register a daemon or listener, and does not change the NOW Games button.
It cannot authenticate a request from another computer and therefore MUST NOT
be exposed as an SSH forced command, network service, HTTP endpoint or desktop
client action without a separate verified device-identity protocol.

Use source checkout on the Wolf host, as the operating-system administrator
who already has Docker access. `WolfDockerAPI` talks only through the fixed
`docker exec -i wolf` private Unix socket adapter. No ports are exposed.

## Mandatory host video-format verification

The prior operator pilot passed an empty `video_producer_buffer_caps` string in the
Wolf CreateLobby request. On the reference NVIDIA host this coincided with a
GStreamer pipeline syntax failure and Wolf's 20-second lobby setup timeout.
**The missing caps are a strong root-cause candidate, not yet physically proven.**

Upstream Wolf selects the producer format at startup. Its GET app/profile API
does not report that selected caps, and automatic guessing is unsafe. Before
using this source-only pilot, obtain the host's startup selection with a
**read-only** command (do not restart Wolf):

```sh
docker logs wolf 2>&1 |
  grep -E 'Using (zero copy|legacy) pipeline on' |
  tail -10
```

For **NVIDIA**, `Using zero copy pipeline on NVIDIA` corresponds to
`video/x-raw(memory:CUDAMemory)`; `Using legacy pipeline on NVIDIA`
corresponds to `video/x-raw`. Pass the confirmed string using `--video-caps`.
If the selection cannot be verified, **stop** rather than guessing. The
current pilot supports exactly these two values; other GPU formats require a
separately validated capability integration and are not silently approximated.
Never submit another lobby Create POST while a previous uncertain lease or
lobby remains.

## Safest first step while the host desktop is occupied

From the MacBook, connect with trusted SSH to the OptiPlex; then, with its Wolf
UI stream **already active on the MacBook**, from the project checkout on
the OptiPlex run:

```bash
python3 server/owner_steam_pilot.py inspect --video-caps 'HOST_VERIFIED_CAPS'
```

This makes five bounded GET calls and emits only a redacted readiness report.
It never initializes owner state, creates lobbies, joins, pairs/unpairs, or
touches Steam. Exactly one Wolf UI Moonlight session must be active, with one
matching paired-client row, zero lobbies, a named Steam profile `user`, and a
valid Docker runner. The profile name may be changed via `--profile`.

This is the same production-shape request plan, but built **in memory only**.
No private Wolf JSON, source client ID, session keys, PINs, Steam runner
environment or mount paths are returned.

## Future controlled operator acceptance (host must be idle)

**Do not execute the following steps while someone else is using the host,
until the owner explicitly schedules a maintenance test and verifies the old
per-client Steam state symlinks and any other potential Steam writers.** The
initial MacBook successful legacy Steam launch was made possible by a manual
server-side state symlink; a test without reviewing aliases could create two
writers to the same Steam data. Back up owner Steam and Wolf data, plan the
rollback and keep the machine otherwise idle.

Enrollment is an explicit adoption of the active, verified Wolf UI client into
a new private state directory. It cannot replace an existing owner policy:

```bash
mkdir -p -m 700 "$HOME/.local/state"
python3 server/owner_steam_pilot.py enroll \
  --video-caps 'HOST_VERIFIED_CAPS' \
  --state-dir "$HOME/.local/state/optiplex-now-owner-pilot" \
  --confirm-existing-owner --confirm-owner-device
```

Only after separate physical backup, state-alias review, direct-app bypass
assessment and owner approval, a **single**, non-retrying real Create+Join can
be attempted:

```bash
python3 server/owner_steam_pilot.py launch \
  --video-caps 'HOST_VERIFIED_CAPS' \
  --state-dir "$HOME/.local/state/optiplex-now-owner-pilot" \
  --confirm-live-steam \
  --confirm-no-other-steam-writer \
  --confirm-legacy-links-reviewed
```

`launch` chooses the paired client identity from the *one verified live Wolf
UI session*; neither the operator nor a remote client passes an arbitrary
client ID in the launch command. It re-reads Wolf state inside the transaction,
uses the persisted owner grant and writes a blocking lease **before POST**.
Create/Join uncertainties leave the state blocked for operator review. Even
after success a `joined` lease remains; **do not delete the lease file** as
a workaround. Safe teardown/reconnect recovery is not yet implemented.

Neither the CLI confirmation flags nor the installed MacBook's Moonlight
pairing provide remote client authentication. SSH users who can run Docker
are host administrators; this is intentionally not a multi-user trust boundary.
The future NOW broker must independently authenticate its requesting device,
deny non-owner direct Wolf app access and safely handle reconnects.

## Operator-only stop and legacy recovery (new source, not installed)

**Do not stop the current reference RE2R session for a source-only test.**
The first successful physical Create+Join on October 23 wrote a **version 1**
lease with a lobby ID but no PIN. Wolf's StopLobby endpoint requires the
actual private lobby PIN, which Wolf's read-only lobby API deliberately
does not reveal. **The new `stop` operation refuses version 1 leases**.

Future owner Steam launches save an 8-digit random PIN alongside the
version 2 lease under the existing 0700 owner directory and 0600 lease
file. This PIN never belongs in client requests, diagnostics, logs or
GitHub. It is available only to the trusted host-local operator process.

After finishing a future version 2 game session, an administrator may
deliberately stop that exact session (this will terminate the game):

```sh
python3 server/owner_steam_pilot.py stop \
  --state-dir "$HOME/.local/state/optiplex-now-owner-pilot" \
  --confirm-stop
```

The stop path requires the one matching owner Steam lobby, the enrolled
device and matching owner workspace, no other active client, and its
original PIN. It marks the lease `uncertain` **before** issuing exactly
one StopLobby POST. Only a confirmed successful stop with no remaining
lobbies and no unexpected sessions archives the lease. An error/timeout
blocks retries and requires manual inspection. A stop confirmation alone
does not prove every Steam process has terminated; verify this before
the next launch. This operation has **no public NOW client endpoint**.

For a legacy v1 lease or an uncertain stop, end the game and use a
separately approved controlled Wolf shutdown/restart or confirmed
out-of-band stop. After the operator independently verifies there are
**zero Wolf lobbies, zero Wolf sessions and no surviving Steam writers**,
the lease may be archived with:

```sh
python3 server/owner_steam_pilot.py reconcile \
  --state-dir "$HOME/.local/state/optiplex-now-owner-pilot" \
  --confirm-runtime-stopped --confirm-no-other-steam-writer
```

`reconcile` does not stop anything, change Wolf/Steam settings, or
restart a container. It refuses all nonempty Wolf runtimes, preserves
private archived evidence, and never clears a lease on a guessed state.
**It is not safe to use merely because a client window closed.**

## Authenticated Games request gate (source only)

`server/owner_games_request.py` is the minimal host-side application gate for
the future NOW Games button. It accepts only `{"version":1,"action":"status"}`,
`"start"` and `"stop"` action payloads, with no client-supplied user,
device identity, Steam profile, runner configuration, filesystem path, PIN or
video caps. A **separate trusted host transport** must bind the *actual*
requesting credential to an already owner-approved Wolf Moonlight client ID,
then supply that bound identity directly to the gate. This is **not** a TCP
listener, SSH command, Unix socket server, authenticator, or deployed helper.
Do not import or expose it to remote clients directly.

`status` returns only safe `needs_wolf_ui`, `wolf_ui_connected`, `busy`
or `in_use` information. `start` requires a host-controlled enable flag,
the exact bound client's active Wolf UI session, an authorized owner workspace
and the existing single-writer lease checks. It uses the **same physically
tested** `launch_owner_steam` transaction. `stop` may only terminate a
lease held by the exact bound owner device and delegates to the existing
PIN-checked one-shot stop.

**Not yet safe to turn on from the shipped UI:** the production transport
must independently authenticate a remote device and bind that credential to
its Moonlight identity; provide a nonadministrative narrow access path;
ensure the expected server-installed files/caps and legacy Steam writer
isolation; and handle Moonlight Wolf UI startup/connection without races.
Existing broad SSH + Docker rights are not a consumer permission model.
An already active joined lease requires a deliberate stop, not an automatic
second Create or forced takeover.

## Rollback and verification boundaries

Before live testing, preserve Wolf `/etc/wolf`, Steam workspace data,
existing mounts/symlinks and the original NOW configuration. This pilot does
not alter the existing Wolf container's setup or the physical host desktop on
its own. Enrollment writes only private `owner-access.json` and lock in the
explicit pilot state directory. Launch additionally writes
`owner-steam-lease.json` and invokes Wolf Create/Join; there is no automatic
rollback of Wolf's runtime lobby. A failing or unknown outcome requires
inspection by the operator, not another POST.

Automated `tests/test_owner_host_pilot.py` uses a **fabricated Wolf API** and
temporary private state only. The successful physical MacBook Wolf UI stream
and owner-profile inventories are documented in issue #154, but there is still
**no physical tested owner Create+Join, authenticated broker or one-click NOW
Games acceptance**.
