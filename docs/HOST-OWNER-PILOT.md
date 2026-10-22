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

## Safest first step while the host desktop is occupied

From the MacBook, connect with trusted SSH to the OptiPlex; then, with its Wolf
UI stream **already active on the MacBook**, from the project checkout on
the OptiPlex run:

```bash
python3 server/owner_steam_pilot.py inspect
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
  --state-dir "$HOME/.local/state/optiplex-now-owner-pilot" \
  --confirm-existing-owner --confirm-owner-device
```

Only after separate physical backup, state-alias review, direct-app bypass
assessment and owner approval, a **single**, non-retrying real Create+Join can
be attempted:

```bash
python3 server/owner_steam_pilot.py launch \
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
