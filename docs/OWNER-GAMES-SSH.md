# Restricted owner Games SSH bridge (source-only alpha)

## Purpose and current boundary

The physically verified owner Steam flow already supports Wolf Create, Join,
Stop and relaunch. The GUI Games button still selects the legacy direct Steam
app. This bridge introduces an **independent, per-device SSH credential**
whose single forced host command can request only `status`, `start`, or
`stop` from the existing host-side policy and lifecycle code.

**Not deployed or release accepted.** It does not install authorized keys,
authenticate the Moonlight certificate cryptographically, provision Wolf,
change the installed Games button, or replace the owner's existing admin SSH
access. A human host owner must independently confirm that the presented SSH
public key belongs to the **same physical device** as the approved Moonlight
client ID before binding them. The signed SSH key proves the approved
credential on each later request. Its link to the Moonlight certificate is
an explicit host-owner enrollment decision, not inferred from an IP/name.

This is an **owner-only alpha bridge**, not a Shared Server permission system.
The forced command runs as the configured host OS account. If that account has
Docker power, a bug in its restricted command could be serious. Use a dedicated
limited host service/privilege separation before enabling untrusted members.
Wolf's upstream direct-app access is a separate bypass until admission controls
are enforced there.

## Files and boundaries

- `server/owner_games_ssh.py`: mandatory OpenSSH forced-command handler.
  It rejects an incoming SSH remote command; it reads one bounded JSON line
  from stdin and emits only a redacted response. It uses `SSH_CONNECTION`
  as a defensive sanity check, **not** as device authentication.
- `server/owner_games_enroll.py`: an *operator-only*, read-only authorization
  check that prints a restricted `authorized_keys` line. It never installs
  the key or grants Wolf access.
- `src/owner-games-client.py`: client-only isolated Ed25519 SSH key and
  fixed no-shell request transport. The key is **not** the admin SSH key.
- `server/owner_games_request.py`: the actual Games authorization and session
  coordination, reused without copying the Wolf request planner.
- `src/owner_launch.py`: durable owner Steam lease, PIN and one-shot stop.

## Manual operator pilot (not ordinary product onboarding)

1. On a test client, run `python3 src/owner-games-client.py keygen`.
   It creates a private key under
   `~/.local/share/optiplex-now/games-client/id_ed25519` (0600), with
   its own 0700 folder. It prints **only** the public key. Never send or
   copy the private key to the host.
2. Authenticate separately with the trusted host owner and compare that
   device's **actual Wolf-paired Moonlight certificate/client ID** to the
   existing owner enrollment. No binding from machine name, IP address,
   Tailscale identity alone or client-claimed client ID.
3. From a **stable, owner-controlled host source checkout** run the operator
   generator, pointing to a host-local file containing the client's *public*
   key, the matching current Wolf client ID, and the actual private owner
   policy directory:

   ```sh
   python3 server/owner_games_enroll.py \
     --public-key-file /path/to/client-public-key.pub \
     --client-id VERIFIED_WOLF_CLIENT_ID \
     --state-dir "$HOME/.local/state/optiplex-now-owner-pilot" \
     --confirm-key-device-binding
   ```

   It checks the existing host Wolf grant and current paired inventory
   using read-only API calls, then prints a forced-command `authorized_keys`
   entry. It makes **no** SSH configuration changes. The printed entry
   resembles:

   ```text
   restrict,command="/usr/bin/python3 /OWNER/CHECKOUT/server/owner_games_ssh.py --client-id VERIFIED_ID" ssh-ed25519 PUBLIC_KEY
   ```

4. A trusted operator independently reviews that exact entry and adds it
   to the **intended host account's** `~/.ssh/authorized_keys`. Do not
   replace pre-existing keys; do not run a generic `ssh-copy-id` for this
   restricted credential. OpenSSH `restrict` disables forwarding, pty,
   user rc, agent and X11; `command` pins the one permitted entry point.
   The source path must remain stable and controlled by the owner.
5. Create `~/.config/optiplex-now/owner-games-host.json` on the HOST,
   owned by the host OS account, mode **0600**, with exactly:

   ```json
   {
     "version": 1,
     "state_dir": "/ABSOLUTE/PRIVATE/OWNER/STATE",
     "video_caps": "video/x-raw",
     "enabled": false,
     "legacy_links_reviewed": false
   }
   ```

   This sample intentionally disables writes. Verify the **actual Wolf
   startup** caps; `video/x-raw` is a reference host observation, not a
   universal default. Only an authorized operator may enable this after
   reviewing backup/rollback, persistent Steam aliases and all writers.
   Legacy direct-app bypass means no guarantee of cross-client exclusivity
   yet. Status requests may be tested while write controls remain disabled.
6. With a pre-paired device and a host key already trusted by OpenSSH, an
   owner pilot may call `python3 src/owner-games-client.py status HOST USER`.
   The client uses only its dedicated key and sends a single JSON line as
   stdin, **without supplying an SSH command**. No password prompts or host
   trust-on-first-use are performed silently. Source-only start/stop require
   the separately owner-enabled host policy and the live matching Wolf UI
   session. Never blindly retry a timed-out Create or Stop.

## Implementation limits and return values

`status` may return `needs_wolf_ui`, `wolf_ui_connected`, `busy`,
or `in_use`. `start` delegates to the durable Create+Join transaction.
`stop` delegates to the PIN-gated operation with exact client/lease binding.
The host rereads current Wolf paired clients and the owner grant. It also
checks host Steam processes and Docker container names before each Start.
These checks cannot atomically prevent a direct Wolf app race. A live or
uncertain lease blocks a second launch.

SSH host keys remain verified, the client uses `-F /dev/null` and
`IdentitiesOnly=yes`, and the server sends no private PIN, session AES data,
Steam runner details or Docker information. The client never receives an
unrestricted SSH shell or copies the host operator's admin key.

Revocation needs **both** the host's forced-command public key removed from
`authorized_keys` and the corresponding NOW Games device grant revoked.
Remove the unused client private key from that device. Do not destroy the
owner's Steam data when revoking a device.

## Physical reference-host verification (October 23, 2026 JST)

This is **manually installed on one personal reference host**, not shipped
as an operational, automatically installed NOW Host service. The MacBook
generated a dedicated Ed25519 key, independent of the administrator key.
The owner verified its existing Wolf-paired/approved identity, installed
an OpenSSH forced-command entry, and created the 0600 host configuration
with both `enabled` and `legacy_links_reviewed` set to `false`.
No public/private key bytes, IP addresses or device IDs are published here.

- Restricted `status` returned
  `{"status":"wolf_ui_connected","success":true}` from the MacBook.
- Attempted remote command `id` returned
  `{"success":false,"status":"denied"}`, SSH exit code 1.
- Reverse port forwarding with `-R 127.0.0.1:0:127.0.0.1:1`
  was refused with SSH exit code 255. This proves one reverse-forwarding
  negative case; other forwarding/PTY, wrong-key, removal and revocation
  paths still need deliberate verification.
- A subsequent read-only host preflight found no active owner Steam
  lease, no detected Steam processes or Steam containers, one active Wolf
  UI session, zero lobbies, and verified `video/x-raw` caps.
- A completed nonrecursive inventory found 8 per-device Steam locations.
  Five `Steam` entries are symlinks to the same *existing* named owner
  `/etc/wolf/profile-data/user/WolfSteam` directory, and three are separate
  directories. An earlier recursive scan hit its 500-directory limit and
  must not be described as a complete filesystem audit.
- The live direct Moonlight apps are `Wolf UI`,
  `OptiPlex Studio Desktop` and `Steam`; the separate named
  `user` profile retains Steam and other applications. **Direct Steam
  remains a bypass** of the NOW Games single-writer lease, especially with
  the five writable aliases. No links were deleted or rewritten.

**Decision:** Keep `enabled:false` and
`legacy_links_reviewed:false` until a controlled admission/rollback
plan is accepted. Current status-only restricted authentication is proven;
remote Steam Start/Stop through this key and the GTK Games workflow are not.
A momentarily clean process/container scan is not proof that no other
device could launch the direct Steam app concurrently. This owner-only
alpha transport is not a multi-user trust boundary.

The present source-only client helper does not automatically bind a new
Moonlight certificate to a key. End users should not need to copy keys or
configure host filesystem permissions once proper installer onboarding is
implemented.

## Required Games integration order

1. Add an asynchronous GTK Games controller that calls the **restricted**
   client helper, not the Docker-capable administrator SSH key. Show a clear
   setup/approval state for devices lacking a restricted key. Reuse the
   existing Moonlight binary modes (AppImage, package, Flatpak).
2. On click, query Games status and, if needed, open Moonlight **Wolf UI**.
   Wait for the authenticated, same-device `wolf_ui_connected` status.
   Never assume a spawned Moonlight process is a verified stream; surface
   timeout, cancellation and pairing errors.
3. Send **one** authenticated Start request, display returned in-use/busy
   state, and allow explicit checked Stop of that same authenticated lease.
   Never automatically retry after an uncertain Create/Stop, and never
   silently fall back to the legacy direct Steam app.
4. Independently review shared Steam link topology, Steam-writer/race
   admission and backup/rollback. Upstream Wolf has a direct-app removal
   handler separate from named profile management, but verify support in
   the installed daemon before performing any change. With the owner
   informed and the session idle, back up Wolf configuration, remove
   **only direct** Moonlight Steam and verify the named `user` Steam profile
   and existing Steam symlinks remain intact. Avoid an unnecessary Wolf
   restart or change to unrelated services.
5. Only then enable host Start/Stop for a controlled one-time test of
   actual RE2R gameplay/audio/input through NOW while preserving the
   physical desktop. Record reconnection, denied/no-key cases and the
   absence of a usable direct Steam shortcut.

These stages are intentionally explicit: removing direct Steam before
client integration would break today's working NOW Games button. Enabling
managed Start while direct Steam still bypasses isolation risks multiple
writers to the same Steam workspace.

## Validation and next acceptance

Offline fixtures must validate key parsing, explicit enrollment approval,
binding to current authorized Wolf clients, no-shell SSH invocation,
private file modes, disabled host config, denial of arbitrary commands,
writer checks and the physical lifecycle adapter. These tests are not a
real SSH session and do not establish upstream Wolf admission control.

The reference host now passes one dedicated-key read-only status, shell
command denial and reverse-port-forward denial test. These **do not**
validate revocation, wrong-key attempts, every forwarding mode, live
Start/Stop via the restricted key or NOW Games-button integration. Follow
the gated integration and bypass-removal sequence above, with meaningful
busy/reconnect and failure handling and an actual independent-desktop
gameplay test. No ordinary user should have to perform the manual pilot
steps above.
