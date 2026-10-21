# Product direction

**Authority:** This document defines intended scope and delivery order. [Current status](CURRENT-STATUS.md) records what is implemented and verified; [Beta acceptance](BETA-ACCEPTANCE.md) and [Host acceptance](HOST-INSTALLER.md#physical-host-acceptance-before-alpha-sign-off) determine release readiness.

## Purpose

OptiPlex NOW makes a personally managed Linux computer accessible from a second device for games, video, files and basic host control. The intended experience is **install, sign in, open Games or Videos**, without requiring users to understand Docker, Wolf, Moonlight, SSH or network topology.

Primary users are individuals and households with inexpensive client devices and an existing Linux host. A future audience may install NOW's supported managed-host bundle. Arbitrary hardware support and paying demand are unproven. NOW integrates upstream services, not replacements for them.

## Product rules

1. **One clear setup path.** Normal users should not need a terminal, administrator instructions or manual image digests. Technical options belong in diagnostics.
2. **Approved devices reconnect.** Do not request a new PIN for a previously authorized Moonlight device, but do not silently authorize an unknown client.
3. **Respect low-end clients.** Validate actual video, input, audio and latency on modest hardware; do not promise specific performance without measurements.
4. **Host independence.** No developer IP, username, container, domain, account or file path becomes a universal customer default.
5. **Preserve systems.** Only change services NOW explicitly owns after an authorized operation. Do not adopt, overwrite or remove unrelated containers or user data.
6. **Accurate state.** Reachable, running, healthy, paired and active-session are different claims; unknown is not healthy.
7. **Upstream first.** Fork Wolf or build a custom account service only if measured user requirements justify ongoing maintenance.

## Product phases

| Phase | Delivery | Evidence / remaining gate |
| --- | --- | --- |
| Existing-host Linux client | GTK3 Debian app with Moonlight/Wolf controls, service links, Tailscale/SSH onboarding and diagnostics | v1.17.0 closed-beta prerelease published; fresh-client acceptance pending |
| **Private Beta 1 client** | Install on a truly fresh Linux client, authorize an existing host, stream and reconnect with minimal guidance | [Client checklist](BETA-ACCEPTANCE.md) not complete |
| **NOW Host technical alpha** | One clean, supported Ubuntu/Pop!_OS 24.04 AMD/Intel/NVIDIA machine can install a managed Wolf service without disturbing other services | Real install code in development source; **clean-host stream, reboot and recovery not yet verified** |
| Managed host product | Versioned dependencies, automatic prerequisites, upgrades, repair, removal, diagnostics and recoverable configuration | Later scope, [#98](https://github.com/SteezyMode/OptiplexNow/issues/98); not a 15-minute installer yet |
| Account/device approval | Owner-approved enrollment and revocation for a new device without repeated first-time pairing | Future scope, [#94](https://github.com/SteezyMode/OptiplexNow/issues/94) |
| Independent user desktops | Distinct durable user profiles, sessions, isolation and authorization | Feasibility only, [#85](https://github.com/SteezyMode/OptiplexNow/issues/85) |

**Scope distinction:** the *existing-host client beta* does not install Wolf or Docker. The separate *new-host alpha* does. Neither stage currently includes NOW-managed accounts, approval by email, automatic user desktop isolation or commercial commitments.

## Immediate development sequence

1. **Stop expanding architecture.** The current host installer and GUI are implemented enough to attempt a physical test. No new orchestration framework or simulated installer path without a test-discovered need.
2. **Prove a clean-host install and stream.** Use [Host installer acceptance](HOST-INSTALLER.md#physical-host-acceptance-before-alpha-sign-off) on an independent GPU PC and a separate client. Check real encoder output, pairing, video/audio/controller, conflict refusal, restart and failed-install recovery.
3. **Fix only observed blockers.** First-install NVIDIA volume code exists; driver-update migration and repair remain unimplemented. Package dependencies and image selection are still too manual for nontechnical users. Prioritize defects and missing steps found in the hardware trial.
4. **Complete existing-host client Beta 1 acceptance.** Use an unpaired supported Linux client for Tailscale login, SSH trust, Wolf/Moonlight authorization, Games/Videos, reconnection and upgrade preservation.
5. **Only then expand polish and support.** Remove digest entry and other manual steps, standardize clean-host installation, and qualify additional hardware. No commercial positioning before repeated independent success.

**Stop condition:** green CI, GUI launch and a running container do not prove a working game stream. Record build/CI, package install and physical-device evidence separately. A test failure takes priority over speculative refactoring.

## Beta 1 engineering execution plan

The October 21 six-part quality plan remains engineering discipline, **not six new product features**. Large one-time extraction campaigns are no longer the delivery priority.

### Six-item progress register

| Principle | Current implementation | Next action |
| --- | --- | --- |
| Nonblocking I/O | Asynchronous Wolf, Tailscale, SSH, Moonlight setup, backup and wizard helpers | Exercise real slow/offline devices and cancellation |
| Modular responsibilities | Extracted configuration, Wolf, status, SSH, tray and wizard modules; Server Setup is a separate GTK executable | Split `main.c` only when active feature work reveals a concrete coupling problem |
| Readable source | New modules use named interfaces and existing `.clang-format` conventions | Format touched functions, not unrelated legacy files |
| Status/tray separation | Parsing, preferences and action dispatch extracted from GTK | Verify physical desktop behavior, offline/unknown state and tray fallback |
| Behavioral tests | Python/native tests, isolated GTK installed-package checks and client/onboarding fixtures | Record genuine hardware and first-run outcomes; do not substitute mocks for them |
| Diagnostics | Native ASan/UBSan CI and focused compiler warnings | Keep diagnostic builds separate from release flags; expand when touching affected code |

Preserve on-disk client settings (`~/.config/optiplex-desk/config.ini`), `.onp` presets, `.onb` backups, installed desktop/CLI aliases, tray action choices, Moonlight identities and existing URL settings. Do not rewrite all of `main.c`, switch frameworks or rename serialized keys as part of unrelated work. Keep one responsibility per functional PR with tests and a compatibility statement.

## Target user flows

**Existing approved host:** install NOW, sign into Tailscale, discover or select a host, confirm SSH identity when required, pair a genuinely new Moonlight client once, then launch Games or an explicitly configured media endpoint. Tailscale membership is not Wolf authorization or Jellyfin login.

**New clean host:** check prerequisites, choose a GPU, authorize installation, provision a managed Wolf service, prove a real stream, then enroll a trusted client. The current advanced alpha path requires manually supplied immutable image checksums and Docker/Compose prerequisites; this is not yet a consumer flow.

**Future existing-account device:** sign into a NOW account, obtain owner approval for that device, use revocable rights to an already permitted host, and reconnect without unnecessary prompts. Not implemented.

## Boundaries and measures

NOW does not own Wolf, Moonlight, Tailscale, Jellyfin, game licenses or user content. OptiPlex Studio is an independent game-development project. No blanket promise of Windows game support, every Linux GPU, anonymous public streaming, or commercial-grade multi-user isolation.

Measure time to first real stream, number of manual steps, pairing friction, disconnection recovery, stable video/audio/input, low-end-client latency, and impact on existing host services. Expand scope only from measured failures or user needs.

References: [Architecture](application-design.md), [Host installer](HOST-INSTALLER.md), [Wolf pairing contract](WOLF-PAIRING-HOST-CONTRACT.md), [upstream/fork policy](UPSTREAM-FIRST-WOLF-INTEGRATION.md).
