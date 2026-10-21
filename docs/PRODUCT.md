# Product direction

**Authority:** This document defines intended scope and delivery order. [Current status](CURRENT-STATUS.md) records what is implemented and verified; [Beta acceptance](BETA-ACCEPTANCE.md) and [Host acceptance](HOST-INSTALLER.md#physical-host-acceptance-before-alpha-sign-off) determine release readiness.

## Purpose

**Product:** a personal entertainment server that makes one compatible computer usable remotely for games, movies, files and controlled downloads. The main promise is *your own GeForce NOW-style remote gaming and Netflix-style media library*, using hardware and lawful content you control, not the catalogs or services of those companies.

**Gaming requirement:** games stream through an independent session without commandeering the host PC's physical screen, inputs or desktop. The host may remain usable for another person, subject to shared CPU/GPU capacity. This is not yet a claim of securely isolated multi-user accounts.

**Media requirement:** watch Jellyfin remotely while queuing an authorized download to the home server, browse and organize files remotely, and keep **only selected download applications** behind a VPN gateway. Neither Jellyfin nor the rest of the home server should depend on that downloader VPN. Confirm isolation and playback under load with measurements, not container labels.

**Experience target:** on two supported, OS-ready computers, roughly 15 minutes from NOW installation to an authenticated remote stream, without manual Docker, VPN or Moonlight/Wolf setup. Select gaming and media modules independently. Linux hosts and clients come first; **Windows clients are planned**, and **Windows hosts are a longer-term goal** with independent-session technical/licensing questions to resolve.

**Optional music:** DroppedNeedle and related music servers are proven possible on the reference machine but not an established general product integration. Keep a configurable Music link and existing-host profile utility; native music discovery/recommendations and bundled provisioning require separate reliability, licensing and maintenance review. Do not market NOW as a Spotify replacement yet. Books/comics and other library categories may be optional future additions, not roadmap gates.

## Product rules

1. **One clear setup path.** Normal users should not need a terminal, administrator instructions or manual image digests. Technical options belong in diagnostics.
2. **Approved devices reconnect.** Do not request a new PIN for a previously authorized Moonlight device, but do not silently authorize an unknown client.
3. **Respect low-end clients.** Validate actual video, input, audio and latency on modest hardware; do not promise specific performance without measurements.
4. **Host independence.** No developer IP, username, container, domain, account or file path becomes a universal customer default.
5. **Preserve systems.** Only change services NOW explicitly owns after an authorized operation. Do not adopt, overwrite or remove unrelated containers or user data.
6. **Accurate state.** Reachable, running, healthy, paired and active-session are different claims; unknown is not healthy.
7. **Upstream first.** Integrate Wolf/Moonlight, Jellyfin, Gluetun, qBittorrent and authenticated APIs rather than rebuilding their protocols.
8. **Independent networking.** Do not force all server traffic through a download VPN; verify downloader routing, fail-closed behavior, service availability and bandwidth effects.
9. **Modular entertainment.** Users can enable gaming, media and download features separately. Music and other library types are optional, not mandatory installation dependencies.

## Product phases

| Phase | Delivery | Evidence / remaining gate |
| --- | --- | --- |
| Existing-host Linux client | GTK3 Debian app with Moonlight/Wolf controls, service links, Tailscale/SSH onboarding and diagnostics | v1.17.0 closed-beta prerelease published; fresh-client acceptance pending |
| **Private Beta 1 client** | Install on a truly fresh Linux client, authorize an existing host, stream and reconnect with minimal guidance | [Client checklist](BETA-ACCEPTANCE.md) not complete |
| **NOW Host technical alpha** | One clean, supported Ubuntu/Pop!_OS 24.04 AMD/Intel/NVIDIA machine can install a managed Wolf service without disturbing other services | Real install code in development source; **clean-host stream, reboot and recovery not yet verified** |
| Managed host product | Versioned dependencies, automatic prerequisites, upgrades, repair, removal, diagnostics and recoverable configuration | Later scope, [#98](https://github.com/SteezyMode/OptiplexNow/issues/98); not a 15-minute installer yet |
| **Media/download workflow** | Existing Videos, Downloads and SFTP links; owner-supplied Jellyfin/qBittorrent, Gluetun gateway | Actual remote use on reference machine; no NOW-managed media stack, native queue, VPN egress/leak certification or portable installer yet |
| Optional media stack | Guided Jellyfin setup, VPN-isolated downloader, safe library mapping, remote queue and bandwidth controls | After game-host alpha and existing-server media acceptance; no mandatory services |
| Windows client | Native Windows installer and equivalent simple onboarding | Planned; no build or hardware acceptance yet |
| Windows host | Independent game session leaving physical host desktop usable | Longer-term feasibility and Windows licensing gate |
| Music/library extensions | Optional music integration, potentially DroppedNeedle; books/comics later if justified | Exploratory only, not part of current alpha or turnkey promise |
| Account/device approval | Owner-approved enrollment and revocation for a new device without repeated first-time pairing | Future scope, [#94](https://github.com/SteezyMode/OptiplexNow/issues/94) |
| Independent user desktops | Distinct durable user profiles, sessions, isolation and authorization | Feasibility only, [#85](https://github.com/SteezyMode/OptiplexNow/issues/85) |

**Scope distinction:** the *existing-host client beta* does not install Wolf, Docker, Jellyfin or the VPN download stack. The separate *new-host alpha* currently provisions Wolf only. Current client media/download functions link to an already running owner's stack. No native downloader management, automatic music discovery, NOW-managed accounts, email approval or secure multi-tenant isolation is shipped.

## Immediate development sequence

1. **Stop expanding architecture.** The current host installer and GUI are implemented enough to attempt a physical test. No new orchestration framework or simulated installer path without a test-discovered need.
2. **Prove a clean-host independent game session.** Use [Host installer acceptance](HOST-INSTALLER.md#physical-host-acceptance-before-alpha-sign-off) on an independent GPU PC and separate client. Check real encoder output, host physical display independence, pairing, video/audio/controller, conflict refusal, restart and recovery.
3. **Fix only observed blockers.** First-install NVIDIA volume code exists; driver-update migration and repair remain unimplemented. Package dependencies and image selection are still too manual for nontechnical users. Prioritize defects and missing steps found in the hardware trial.
4. **Complete existing-host client Beta 1 acceptance.** Use an unpaired supported Linux client for Tailscale login, SSH trust, Wolf/Moonlight authorization, Games/Videos, reconnection and upgrade preservation.
5. **Verify the already-working media pattern.** Remote Jellyfin playback while adding a legal download through the configured qBittorrent Web UI; inspect SFTP organization, downloader-only VPN routing, kill-switch refusal and streaming performance under load. Keep this independent of automatic server provisioning.
6. **Then reduce setup friction.** Standardize host prerequisites and managed updates. Add optional Jellyfin/downloader install and native API controls only when they demonstrably help; do not build a music manager or broad media catalog now. Test Windows clients before Windows host engineering.

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

**Existing approved host:** install NOW, sign into Tailscale, discover or select the host, confirm SSH identity when needed, pair a new Moonlight client once, then launch an independent game session or owner-configured Videos, Downloads and Files. Jellyfin playback should continue on normal networking while the separately VPN-routed downloader adds media. Tailscale membership does not replace Wolf, qBittorrent or Jellyfin authorization.

**New clean host:** check prerequisites, authorize installation, provision a managed Wolf service, prove gaming independent of the physical host desktop, then enroll a trusted client. The current advanced alpha still needs manual immutable-image inputs and Docker/Compose, and does not provision media or VPN stacks.

**Future existing-account device:** sign into a NOW account, obtain owner approval for that device, use revocable rights to an already permitted host, and reconnect without unnecessary prompts. Not implemented.

## Boundaries and measures

NOW does not own Wolf, Moonlight, Tailscale, Jellyfin, Gluetun, qBittorrent, DroppedNeedle, game licenses, media rights or user content. OptiPlex Studio is independent. Streaming-service brand comparisons are illustrative, not affiliations or promises of a licensed catalog. No blanket promise of Windows games, every GPU, multi-tenant security, legal access to any particular download or commercial readiness.

Measure time to a first independent stream, host-desktop usability, reconnection, low-end-client performance, media accessibility during concurrent downloading, actual VPN-only downloader routing, kill-switch behavior, and support burden. Expand scope only from real failures and user needs.

References: [Architecture](application-design.md), [Host installer](HOST-INSTALLER.md), [Wolf pairing contract](WOLF-PAIRING-HOST-CONTRACT.md), [upstream/fork policy](UPSTREAM-FIRST-WOLF-INTEGRATION.md).
