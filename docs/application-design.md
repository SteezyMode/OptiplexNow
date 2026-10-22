# Client architecture

Status: implemented client boundaries and future contracts. See [Current status](CURRENT-STATUS.md) for observed test coverage.

## Runtime

The installed package provides a GTK3 desktop launcher, supporting scripts, status/tray UI, and optional host-management helpers. NOW invokes separately installed Moonlight for streaming and configured browser/SSH/SFTP programs for other access. Tailscale provides a supported path to remote peers; Tailscale is not a NOW account service.

The published v1.17.0 application is a client for an **already configured Linux host**. Unreleased development source includes a separate Server Setup GTK window and an owner-confirmed, privileged **clean-host Wolf installation pilot**. Its ordinary check is read-only; its advanced install can provision one dedicated Wolf Compose project, but cannot configure media software, NOW accounts, a VPN or arbitrary existing hosts. Physical installation and streaming are not yet accepted. See [Host installer](HOST-INSTALLER.md).

## Boundaries

| Owner | Owns |
| --- | --- |
| NOW client | Connection/configuration UI, discovery, allowed host actions, status presentation, client backups |
| NOW Host installation pilot (unreleased) | Owner-approved, root-rechecked clean-host Wolf deployment in a dedicated project; **not** yet full repair, upgrades, removal, service registry or client enrollment |
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

## Personal Server identity and access contract

**Architecture decision:** Personal Server is the **one-owner configuration of the future Shared Server model**, not a second or temporary identity system. It ships first and works without hosted NOW accounts, multi-member administration or an extra user-selection screen. The server, not a client-provided profile name, decides which workspace an approved device may launch. **This is a required design for future code, not yet implemented server-side enforcement.**

### Durable entities

| Entity | Independent identity and lifetime | Rule |
| --- | --- | --- |
| Host | Locally assigned immutable server ID | DNS, Tailnet IP and SSH username are connection coordinates, not host identity or proof of user permission |
| Principal | Stable server-local ID; exactly one **owner** initially | A person authorized on this host. Shared Server later adds individual **members**, never extra owners merely because more devices pair |
| Device enrollment | Own revocable credential bound to a host and principal | Moonlight certificate, Tailscale connectivity and SSH trust are independent transport credentials, not authorization to choose any Steam profile |
| Gaming workspace | Durable logical profile ID, owner principal ID and Wolf adapter reference | One persistent Steam home per principal by default; profile data never follows the device ID and must not be cloned into a client |
| Service grant | Principal + service + permitted operations | Games, Videos, Downloads, Files, Power and Admin require distinct server-side checks; media playback never implies Docker/SSH/file access |
| Session/lease | Transient owner principal, device and gaming workspace binding | A reconnect is not a new profile. Coordinate simultaneous requests to one mutable Steam home; no double-writer promise |

A **Personal Server** creates one owner principal with multiple independently revocable devices, one owner gaming workspace, and the existing authorized Jellyfin/media endpoint. The initial UI hides this machinery. The same persisted schema can add member principals, separate workspaces and narrower grants later without reassigning or moving the owner's Steam data.

### Owner enrollment and first Games launch

1. **Clean managed server:** initialize server-local owner identity and one durable named Wolf gaming workspace. **Adopt existing host:** inspect the already working Wolf/Steam profile **read-only** and request specific owner approval before associating it. Do not reinstall Steam, generate a new empty profile, reset login, or migrate owner data automatically.
2. **Enroll another device:** the server owner approves the exact requesting client credential and binds it to the **existing owner principal**. Reuse that owner's grants and workspace. The device itself is not a new Steam user; it has its own revocation record.
3. **Launch Games:** the device sends a request to a narrow **local host authority**. Validate its host-bound enrollment and principal/grant, resolve the authorized workspace, coordinate any existing active session, then call Wolf through a tested supported path. A device-supplied Wolf profile ID or filesystem path is never trusted. The eventual GUI simply launches Games.
4. **First sign-in:** Steam login/Steam Guard occur inside the remote owner's Steam application, not inside NOW. Steam authentication stays stored on the host in the owner's profile; NOW never collects, embeds or copies those credentials.
5. **Return/reconnect:** resolve the same durable workspace regardless of which approved device connects. After host/client restart and NOW upgrade, saved Steam state and other provider logins remain intact. If a device is revoked, it loses access; the workspace is not deleted.

**Single-owner concurrency rule:** Default to one active writer to a single Steam workspace. If an old game session remains active, reconnect to it only if Wolf supports safe handoff; otherwise display an actionable "already in use" result and require deliberate owner intervention. Do not silently spawn another Steam container against the same mutable home, stop someone's stream, or share a second account by reusing owner credentials.

### Shared Server compatibility without implementing it now

Adding Joe later means adding an **independent member principal**, explicitly granted services and a separately owned gaming workspace, not just pairing Joe's Moonlight certificate to the owner's profile. Members never inherit owner SSH credentials, privileged Wolf/Docker APIs, host filesystem mounts, profile-data directories, or owner-service admin tokens. Media-only member access can use Jellyfin's native accounts/library permissions; it does not require granting Steam access or creating another Jellyfin server.

A future storage pool is a **service resource separately permissioned to principals**. It is not the workspace, never grants a Steam game license, and never merges Steam login/saves. Every future public interface must be subject to server-enforced authorization, including direct upstream Wolf application selection, API calls, direct Jellyfin URLs and alternate client paths; merely hiding an option in NOW is not isolation.

The host administrator remains technically capable of inspecting server-local data. We must promise privacy between ordinary members where verified, **not secrecy from the owner of the physical host**.

### Integration and migration constraints

- **P0 uses one narrow host-side authority**, not a broad multi-tenant platform or hosted sign-in service. Separate policy/identity resolution from Wolf profile IDs so an eventual provider/OS adapter can change without changing a person's identity. A Python/GTK client must not gain unrestricted Docker or Wolf management socket access.
- Current Wolf direct `moonlight stream HOST Steam` selects the special `moonlight-profile-id` application with per-device state. Physical tests also found a named `user` Wolf profile with persistent Steam state. **Do not assume the Wolf client-wide `app_state_folder` API selects that named profile.** Verify upstream named-profile launch semantics in a disposable test. The existing per-device Steam symlinks are a temporary reference-host workaround, not the intended data model.
- Use explicit, versioned local state for host/principal/device/workspace/grants and an idempotent migration path. A new owner enrollment must not overwrite or regenerate unrelated Wolf configuration, Steam files, Jellyfin libraries, client certificates, Tailscale state or SSH keys. Refuse ambiguous mappings rather than guess.
- Preserve `~/.config/optiplex-desk/config.ini`, `.onp` presets and `.onb` backups. These are connection and device settings, **not authoritative server permissions**. Old client installs may continue working while adoption is opt-in; never infer that old client access is equivalent to a newly verified member grant.
- Do not start the Shared Server permissions UI, second Steam account support, pooled games or private Jellyfin instances until the Personal Server acceptance test below passes.

### Implemented local policy foundation (not yet launch enforcement)

The development source includes `src/owner_access.py` and the developer-only `src/owner-access-local.py`. They provide a versioned, root-owned local JSON store and allow an administrator to **explicitly** adopt one existing named Wolf Steam profile and bind specific already-paired Moonlight certificate-derived client IDs to the one owner. The policy stores separate host, principal, workspace and device identifiers; a lookup refuses unknown, revoked, malformed or no-longer-paired devices. All changes are atomic and limited to the separate NOW-owned local policy file. A second approved owner device resolves the same persistent workspace, without moving or reading Steam files.

**Not a security boundary yet:** Wolf itself still accepts any paired client according to upstream permissions. Nothing in this policy intercepts direct Moonlight requests, disables Wolf UI, controls Steam sessions, unpairs devices or limits host SSH permissions. The existing NOW Games button remains unchanged. Installing, bootstrapping or running this developer-only CLI on the reference host is **not** part of the current beta instructions. Approval here represents a host administrator's explicit assertion, not proof that an unattended NOW account login is the owner.

Before connecting the local policy resolver to real launches, the narrow host agent must authenticate a device/session credential at its own boundary, validate its Wolf identity and grant, and **also enforce** those permissions against direct upstream Wolf entrypoints. A disconnected mapping file that only controls the NOW button is insufficient for invited users. Implement safe session leases and proper revoke/unpair behavior before calling owner access secure.

### Required tests before shipping the owner-profile integration

- [ ] Fresh unpaired laptop with owner-authorized device enrollment, one-click Games, original Steam login/library, real game video/audio/input; **no terminal, symlink or Wolf UI profile selection**.
- [ ] A second approved owner device resumes the same persistent state after first device exits; restart/reboot and NOW package upgrade preserve Steam auth and configured Videos endpoint.
- [ ] A second concurrent launch of the same owner's active Steam home cannot create independent writable instances, and a safe reconnect or clear busy message works.
- [ ] An unknown/revoked client, forged client-reported principal, different Wolf app choice or profile ID cannot access the owner workspace via NOW **or direct accessible Wolf paths**.
- [ ] Existing-host adoption is explicit, non-destructive, fails safely for unknown/duplicate client IDs, preserves the original working state and has a tested rollback.
- [ ] Unit tests cover binding/permission decisions in a GUI-free module; host/Wolf integration tests use disposable identities and state; physical acceptance is recorded separately from CI.

**Next execution path:** [owner-device continuity #154](https://github.com/SteezyMode/OptiplexNow/issues/154) first, then verified physical onboarding and media access [Beta acceptance](BETA-ACCEPTANCE.md). [Multiple member Steam profiles #153](https://github.com/SteezyMode/OptiplexNow/issues/153) is deferred implementation but its isolation rules constrain all owner-code changes today.

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

## Host monitoring boundary

Host metrics and physical-disk filtering are parsed by `src/host_metrics.c/.h`, outside GTK. The worker fetches read-only telemetry and hands a typed, bounded set of values to the main thread for rendering. Tailscale status uses the same structured status helper as the setup wizard, not a substring match on an arbitrary `100.*` address.

**SSH trust:** background host probes and power actions require a known, preapproved SSH host key (`StrictHostKeyChecking=yes`). They must never create first-time trust as a side effect of an apparently read-only status check; a new host uses the explicit graphical authorization flow. Changed host keys require manual investigation, not automatic replacement. The client still uses the existing SSH account and does not grant additional host privileges.

## Background SSH operation identity

The worker-entry boundary captures a `NowHostJobTarget` value on the GTK thread before dispatch. It contains the exact selected host and account; relay wake additionally captures the approved wake command. Background SSH probes, hardware inventory, Wolf administrative lookup and power operations consume only this snapshot rather than rereading mutable `cfg[]`. Before presenting the result, the GTK callback checks whether the selected endpoint still matches and drops stale output. Never interpret a saved host change as permission to retarget an action that was already initiated. The GTK-free contract is in `src/host_job_target.c/.h`; test it independently, including sanitizer builds.

## Encrypted device backup execution boundary

`src/backup_async.c/.h` owns the GIO subprocess bridge to the existing encrypted `optiplex-now-backup` helper. GTK collects file selection and the password, then shows modal progress while the helper runs without blocking the GTK main context. The password is written to the child's stdin, never argv or environment, and its worker-owned memory is erased after I/O completes. The full backup helper and its v1 .onb file format remain unchanged.

Restoring SSH, Moonlight, and client configuration is not currently atomic as a group, so deliberately *do not* offer a forced cancellation action in the GUI. A forced kill during file replacement can leave a partially restored identity. Future transactional restore design can change this only after providing a reliable all-or-nothing or rollback contract and testing it. Mock command tests cannot substitute for a trusted-device restore rehearsal.

## Tray routing boundary

The GTK tray owns menu rendering, StatusNotifier/GTK status-icon integration and callbacks; `src/tray_prefs.c/.h` owns order, mask, saved labels and service metadata; `src/tray_actions.c/.h` interprets known action IDs through an explicit table of callbacks. The dispatcher has no GTK, network or SSH dependencies. Invalid IDs and missing handlers are rejected; launching Games still brings NOW forward first when Moonlight is missing. Do not turn this callback interface into a general app-wide event bus.

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
