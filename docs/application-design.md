# Client architecture

Status: implemented client boundaries and future contracts. See [Current status](CURRENT-STATUS.md) for observed test coverage.

## Runtime

The installed package provides a GTK3 desktop launcher, supporting scripts, status/tray UI, and optional host-management helpers. NOW invokes separately installed Moonlight for streaming and configured browser/SSH/SFTP programs for other access. Tailscale provides a supported path to remote peers; Tailscale is not a NOW account service.

The app is a client for an **already configured Linux host**. The New Server Setup surface does not provision Wolf, media software, credentials, containers or a VPN.

## Boundaries

| Owner | Owns |
| --- | --- |
| NOW client | Connection/configuration UI, discovery, allowed host actions, status presentation, client backups |
| NOW future host manager | Opt-in installation, service registry, config lifecycle, health/diagnostics, scoped enrollment, update/repair/backup |
| Wolf | Streaming server, application and desktop sessions, Moonlight protocol endpoints |
| Moonlight | Video/audio/control client and device certificate identity |
| Tailscale or a future supported alternative | Network membership and reachability |
| Media software | Jellyfin authentication, media playback, libraries and service internals |
| OptiPlex Studio | Local-first creative projects, tools and AI-assisted workflows |

Do not put server admin power in an ordinary client. The Wolf Unix management socket and Docker control must stay host-local behind an authenticated, narrow mediation layer.

## Identity and data model

Do not conflate the following:

- **User:** principal entitled to access a specific host or logical desktop.
- **Device:** individually paired client certificate and future NOW enrollment credential; revocable separately.
- **Host:** server with a stable ID and explicit ownership.
- **Desktop/profile:** durable workspace definition, owner and data home; not necessarily a current container.
- **Session:** transient connection and running stream state; never infer a connected user from container count.

The current beta uses Tailscale peer access, SSH trust and native Moonlight/Wolf pairing, **not** one unified NOW identity. Future email approval authorizes a new device under an existing account. It cannot bypass host-owner authorization or grant a new host automatically.

## Configuration compatibility

- Persisted client settings: `~/.config/optiplex-desk/config.ini` (or configured XDG config directory). `src/config.c/.h` now owns file parsing, defaults, compatibility migration, and atomic private saves. It retains an indexed compatibility array for the current GTK controller; a future typed settings API can remove index coupling after its callers and migration tests are converted. Preserve all field positions and user-defined links during upgrades.
- Display name, Debian package ID, desktop executable, config directory, preset format and backup format are different compatibility surfaces. Never bulk-rename them.
- `.onp` presets export only allowed non-secret connection settings. Keep legacy files readable.
- `.onb` backups are encrypted and may include SSH/Moonlight identity; protect them like credentials and test restore on a trusted spare client.
- Primary action and tray action selections are separate masks. Migration must retain both.
- Existing host services and user data are outside the client's installation lifecycle unless explicitly opted into an owned management operation.
- Optional Videos, Music, Downloads, and Web Gaming URL settings belong to the user's host and are never hardcoded to the development server. Adding a new optional key to config and portable presets must preserve older config and v1/v2 preset imports.

## Health and capability contracts

Report state and source independently: Tailscale is connected/disconnected, Wolf can be reachable/running, desktop container count is not client session count, and Gluetun health is a container-defined probe rather than an independently verified tunnel exit IP. Missing data is unknown, not healthy.

An eventual host installer must publish managed service IDs and health capabilities instead of requiring a name such as `gluetun`. Avoid accidental Docker permission expansion and application-specific host assumptions.

## Maintainability and threading contract

The six ordered engineering items and next-session stop condition live in [Product direction](PRODUCT.md#beta-1-engineering-execution-plan). This section defines implementation boundaries, not a second roadmap.

**Current source state:** `src/config.c/.h` owns configuration persistence; `src/process.c/.h` supplies bounded process execution; `src/wolf_pairing.c/.h` and `src/wolf_transport.c/.h` own Wolf request validation and asynchronous bridge execution. `src/tailscale_async.c/.h` now owns cancellable Tailscale helper execution and parsed discovery rows, while `src/tailscale-status.py` interprets read-only status JSON. The GTK wizard only starts jobs and displays their results. `main.c` still contains the substantial tray/status and action controller; not all other subprocess calls are asynchronous.

**Wolf and network operations:**
- Keep process execution, pending-client parsing and Wolf authorization decisions outside GTK callbacks behind a small API with explicit host identity, selected client and result/error fields.
- Perform potentially blocking SSH/API work in a worker or asynchronous subprocess. Copy required inputs before starting; post results to the GTK main context. Never dereference GTK widgets from the worker.
- Track cancellation and dialog lifetime so a completion cannot update or revive a closed window. Coalesce duplicate requests, bound each wait, and show offline/refused/expired states without authorizing another client.
- Distinguish what the existing SSH helper can do from what a normal beta tester is entitled to do. This refactor must not widen access to the host Docker socket or replace the future least-privilege authorization work.
- Preserve the existing manual approval decision until explicit client identification and owner authorization have been verified. "Automatic" discovery is not permission to pair any pending IP.

**Other module boundaries:**
- Keep monitoring probes, normalization of service states and presentation separate. Current worker-based status updates are a useful model; do not collapse them back into blocking UI callbacks.
- Tray and wizard layers may select actions and render state, but should not own low-level SSH commands or parsing rules. Keep external helper paths and launch semantics compatible unless a measured issue requires a separate change.
- Apply `.clang-format` only to new or edited code. Never combine a repository-wide style diff with network, settings or pairing changes.

**Verification contract:** mocked transport and parsing tests cover empty/stale/multiple pending requests, timeouts, cancellation and malformed data; compiled native tests cover extracted pure functions; GTK smoke tests cover lifetime and UI responsiveness where feasible. Real new-client pairing and streaming are independently required by [Beta acceptance](BETA-ACCEPTANCE.md). Do not substitute CI for device observations.

## Graphical Tailscale setup boundary

For the first graphical installer target, NOW on Debian/Ubuntu-family systems delegates only an explicitly confirmed Tailscale install to `pkexec /usr/bin/python3 /usr/lib/optiplex-now/tailscale-install.py`. The root helper has no variable command arguments, uses upstream HTTPS resources on a distro/codename allowlist, validates a single signed apt source entry, then installs the `tailscale` package through apt and enables its daemon. An existing `tailscale` executable is left unchanged. Tailscale sign-in opens the device-local `http://100.100.100.100/` web interface (supported by modern Tailscale) without starting a root shell. An unavailable PolicyKit agent must fail visibly and direct the user to official instructions, not silently fall back to terminal commands. Only package installation requires elevated privileges, not ordinary NOW startup.

## Graphical SSH access authorization

The beta's SSH wizard now uses a user-initiated, GTK-controlled authorization flow rather than launching a terminal for `ssh-copy-id`. `src/ssh_authorize.c/.h` runs the fixed `ssh-authorize.py` bridge asynchronously, and the packaged `now-ssh-askpass` GTK binary is invoked by OpenSSH for the server password or explicit host-fingerprint decision. The user's private key remains in their home directory. An existing `~/.ssh/id_ed25519` key pair is reused; missing or symlinked halves are never overwritten. A newly created ED25519 private key is locally owned and unencrypted for unattended reconnect, so its file protection and backup handling remain important.

OpenSSH retains `StrictHostKeyChecking=ask`. The user must explicitly approve an unfamiliar fingerprint; changed known-host keys are never automatically accepted. Passwords and passphrases are entered into a masked graphical prompt and are not placed in arguments or application config. `ssh-copy-id` can append the public key to the selected remote user's authorized_keys, after that user authenticates. This is **not** a zero-touch device enrollment system, a host-management permission broker, or an authorization to use Docker/Wolf as root. A nontechnical user still needs the correct host account credentials or owner assistance during Beta 1.

A declined credential dialog, unreachable server, timeout or wizard closure cannot be reported as successful enrollment. The deployed GUI and authentication still require device-level acceptance; mocked Python and installed GTK smoke tests cover only simulated operation.

## Engineering gates

GitHub CI compiles, checks packaging, runs unit checks and GTK smoke tests. The release workflow publishes only new version tags. Neither substitutes for fresh-client pairing, real gameplay, live audio/input, or backup restore.

Technical details: [Pairing contract](WOLF-PAIRING-HOST-CONTRACT.md), [Host installer](HOST-INSTALLER.md), [Wolf adapter/fork policy](UPSTREAM-FIRST-WOLF-INTEGRATION.md), [Beta acceptance](BETA-ACCEPTANCE.md).
