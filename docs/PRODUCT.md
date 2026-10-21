# Product direction

Status: product intent. Only capabilities in [Current status](CURRENT-STATUS.md) are shipped or verified.

## Purpose

OptiPlex NOW makes an existing personal Linux host accessible from another computer for games, video, files, and basic host control. The intended experience is **install, sign in, choose Games or Videos**. Simplicity is the product. NOW integrates established tools rather than claiming to replace their engines.

The primary audience is an individual or household using a self-managed Linux host and inexpensive client devices. A second audience is a person willing to install a supported NOW Host bundle on an existing machine. Support for arbitrary hardware and paid demand remain unproven.

## Product rules

1. **One clear path.** Normal setup must not require users to understand Moonlight, Wolf, Docker, SSH, ports, VPN topology, or certificates. Technical controls belong in diagnostics.
2. **Fast reconnection.** A previously approved device opens its authorized host without repeating pairing. Never silently authorize an unknown device.
3. **Low-end clients matter.** Test older laptops and modest networks. Offer measured 720p/30 and other profiles when appropriate, without promising frame rates or codecs on unsupported hardware.
4. **Host independence.** The owner's OptiPlex is a reference fixture, not a baked-in dependency. Host address, services, credentials, and deployment layout must be configurable. Distribution builds must not prefill the maintainer's usernames, private addresses, or service domains.
5. **Preserve user systems.** NOW may manage components it explicitly installs. It must not modify unrelated Docker stacks, host services, user files, or active streams without an explicit operation.
6. **Truthful status.** Separate reachable, running, healthy, paired, and active-session states. Unknown is not healthy.
7. **Upstream first.** Integrate supported APIs and interfaces. Fork only to solve measured, otherwise blocked user needs.

## Product phases

| Phase | Deliverable | State |
| --- | --- | --- |
| Current NOW client | Debian GTK3 app for an already configured host, game and media entry points, connection tools and diagnostics | Implemented; see current status |
| Private Beta 1 | Install a GitHub .deb on a fresh Linux client, connect to a preapproved Tailscale host, authorize game streaming, launch Games and Videos with minimal guidance | Acceptance pending |
| Device onboarding | Sign into an existing NOW account on a new device, approve device registration from the account owner's email, restore access to already authorized hosts | Proposed, [#94](https://github.com/SteezyMode/OptiplexNow/issues/94) |
| NOW Host installer | Idempotent, documented installation of a supported game-streaming host, with optional media, scoped permissions, diagnostics, upgrades, recovery, and removal | Proposed, [#98](https://github.com/SteezyMode/OptiplexNow/issues/98) |
| Independent user desktops | Logical user-to-desktop ownership, persistent data, device authorization, tested isolation and reconnect policy | Feasibility only, [#85](https://github.com/SteezyMode/OptiplexNow/issues/85) |

Beta 1 uses a small group of preapproved Tailscale accounts. It does **not** include NOW-owned accounts, email approval, Headscale, zero-touch game pairing, or automatic host deployment. Those are separate milestones.

## Beta 1 engineering execution plan

**Engineering checklist adopted October 21, 2026 (JST).** This is the continuing engineering standard for the existing Beta 1 client, not a new product phase. The five product priorities remain: **(1) finish Wolf pairing, (2) improve Tailscale sign-in, (3) simplify device authorization, (4) complete fresh-client acceptance, (5) build a standardized host installer later**. See [Beta acceptance](BETA-ACCEPTANCE.md) for the actual release gate and [Architecture](application-design.md) for implementation boundaries.

The October 21 configuration extraction in [PR #103](https://github.com/SteezyMode/OptiplexNow/pull/103) establishes the starting pattern. It does not mean the rest of `main.c` is modular or that pairing is nonblocking.

| Work item | When | Smallest useful deliverable | Completion evidence |
| --- | --- | --- | --- |
| **1. Nonblocking pairing and setup I/O** | First, alongside Wolf | Move the blocking Wolf pending-request and authorization calls off the GTK thread. Preserve bounded timeouts, meaningful failure messages, safe cancellation and owner-controlled selection. Address other synchronous SSH/Tailscale wizard probes when those flows are touched. | UI remains interactive with a disconnected/slow host, cancel or dialog close causes no stale widget updates, and fake-host tests cover timeouts and refusal. Real unpaired-device pairing remains a separate required acceptance check. |
| **2. Separate streaming logic from GTK** | During Wolf work | Extract one testable Moonlight/Wolf transport or pairing component with explicit inputs/results. Keep dialogs, tray actions and user messages in the GTK layer; do not redesign the host helper. | Compile/link and packaging remain unchanged in behavior; transport/parsing has behavioral tests; existing pairing and reconnection paths still work. |
| **3. Readable, consistent C formatting** | With each touched function | Apply the existing `.clang-format` conventions to new modules and functions being edited, with meaningful names and straightforward control flow. | Reviewable diffs and clean compilation; no unrelated full-file formatting or behavior changes mixed into a functional PR. |
| **4. Split status and tray responsibilities** | Later, alongside relevant client work | Extract host status parsing/probing first, then tray presentation or action mapping where worthwhile. Pass data through explicit interfaces instead of exporting GTK globals. | Status source and rendering stay distinct; offline/unknown/running/connected remain accurate; tray, restart and saved shortcut tests remain green. |
| **5. Upgrade test quality** | Every related PR | Add unit/behavior tests using simulated host responses and failure cases. Replace source-text assertions when the affected subsystem is extracted, not through a separate testing rewrite. | Tests demonstrate decisions and results (wrong/stale pairing request, failed SSH, timeout, cancellation, config compatibility); CI still runs package and GTK smoke tests. |
| **6. Add stricter diagnostics** | After affected modules are stable | Introduce an opt-in or separate CI sanitizer build for suitable native C tests (AddressSanitizer and UndefinedBehaviorSanitizer), then tighten warnings in the modules that are clean. | Diagnostic job runs reliably and is actionable; default package and release build are unchanged; pre-existing third-party/GTK warnings do not become a blanket release blocker. |

### Six-item progress register

The six engineering improvements are permanent review criteria, not separate product features.

| Improvement | Completed evidence | Remaining work |
| --- | --- | --- |
| **1. Nonblocking operations** | Wolf transport [#106](https://github.com/SteezyMode/OptiplexNow/pull/106), Tailscale status/discovery [#110](https://github.com/SteezyMode/OptiplexNow/pull/110), graphical SSH enrollment [#112](https://github.com/SteezyMode/OptiplexNow/pull/112) | Audit other GTK-triggered host/maintenance subprocesses and cancellation paths; test slow/unreachable hosts |
| **2. Modular responsibilities** | Config [#103](https://github.com/SteezyMode/OptiplexNow/pull/103), Wolf [#105](https://github.com/SteezyMode/OptiplexNow/pull/105) and [#106](https://github.com/SteezyMode/OptiplexNow/pull/106), Tailscale [#110](https://github.com/SteezyMode/OptiplexNow/pull/110), SSH [#112](https://github.com/SteezyMode/OptiplexNow/pull/112), host metrics [#114](https://github.com/SteezyMode/OptiplexNow/pull/114), tray prefs [#115](https://github.com/SteezyMode/OptiplexNow/pull/115) | GTK `main.c` still owns too much state, probing and presentation; tray action dispatch in [#116](https://github.com/SteezyMode/OptiplexNow/pull/116) is another narrow extraction |
| **3. Readable C** | New modules use straightforward interfaces and the repository's `.clang-format` conventions | Incrementally format touched legacy functions, reduce shared globals and indexed config access; avoid indiscriminate full-file rewrites |
| **4. Monitoring and tray separation** | Host telemetry parser [#114](https://github.com/SteezyMode/OptiplexNow/pull/114), tray settings [#115](https://github.com/SteezyMode/OptiplexNow/pull/115), tray dispatcher [#116](https://github.com/SteezyMode/OptiplexNow/pull/116) | Keep probing and rendering separate; later extract GTK tray presentation and preserve both StatusNotifier/AppIndicator and GTK fallback |
| **5. Behavioral tests** | Native config/Wolf/Tailscale/host/tray contracts; mocked failures [#109](https://github.com/SteezyMode/OptiplexNow/pull/109); disposable first-run GUI and Debian packaging checks | Integrated first-run error/reconnect tests and evidence from an actual unpaired client, browser login, SSH authentication and game streaming |
| **6. Stronger diagnostics** | Independent ASan/UBSan and stricter module compilation [#113](https://github.com/SteezyMode/OptiplexNow/pull/113) | Expand instrumented coverage as legacy GTK code becomes testable; do not silently change official package compiler flags |

**Current delivery sequence:** complete small, tested controller extractions and audit remaining synchronous operations; run an integrated simulated first-run and failure-path test; then test the full Tailscale → SSH → Wolf → Games/Videos experience on a real fresh client. Treat that last test as Beta 1's release gate. The reproducible host installer, NOW account approval and independent user desktops are separate future product milestones.

**Stop condition:** do not call a system accepted merely because GitHub CI is green. Record source, simulated, installed-package and physical-device evidence separately. Avoid speculative new features while architecture or acceptance work fails.

### Scope controls

- No full rewrite of `main.c`, blanket automatic formatter run, language/framework migration, new backend, new account service, Wolf fork or host installer implementation during this pass.
- Do not change production Docker, Wolf, Caddy, Jellyfin, Tailscale ACLs or working pairings as part of source cleanup.
- Preserve `~/.config/optiplex-desk/config.ini`, keys and indices, `.onp` presets, `.onb` backups, tray behavior, desktop actions, CLI aliases and existing packaging.
- Require one clear responsibility, a compatibility statement, behavioral checks, CI and review per PR. Do not publish a new `.deb` solely because an architecture PR passes CI.
- No artificial file-size or line-count target. Reduce coupling and actual failure risk, not just the number of lines in `main.c`.

## Portable client configuration

- A clean install must not default to the maintainer's Tailscale host, SSH account, or media and gaming domains.
- User-entered service URLs are optional; unavailable music/download/browser gaming services must not be fabricated from the server address and a guessed port.
- Saved client settings, portable presets, and encrypted backups retain their existing compatibility guarantees. A host can have a different gaming, video, and download endpoint.
- The private reference environment may be documented as an explicitly labeled test fixture. It is not a hosted NOW backend.

## Target first-run flows

**Beta 1:** Install .deb, authenticate with Tailscale, discover or enter a prepared host, confirm SSH trust if needed, connect the game client to Wolf, then launch Games or Videos. Service-specific credentials, including Jellyfin login, remain independent.

**Future existing-account device:** Install NOW, sign in with existing credentials, approve the new device from a short-lived owner email link, provision device-specific network and game access, then open the already authorized host. Approval is for a *new device*, not automatic access to somebody else's server. Device access must be revocable.

**Future new host:** Run an independent NOW Host installer on a supported Linux machine, pass capability and conflict preflight, select services, install a versioned managed stack, verify a real stream, and produce recoverable configuration. The client should then discover it through a controlled account/enrollment process.

## Boundaries and non-goals

- NOW is not the Wolf streaming engine, Moonlight client, Tailscale network, Jellyfin media server, Docker runtime, or a gaming-license provider.
- OptiPlex Studio is a separate local-first game development application. NOW may stream a Studio desktop but does not own Studio projects, Codex tasks, or creation tools.
- No promise of anonymous public streaming, arbitrary Windows game compatibility, every Linux GPU, commercial-grade untrusted multi-tenancy, built-in movie libraries, or a zero-configuration server on any PC.
- Optional VPN, downloads, music, developer terminals, and advanced host administration must not become prerequisites for basic Games or Videos.
- Do not merge NOW with Studio or revive the deprecated Suite as an application.

## Decision metrics

Measure fresh-device time to first stream, number of manual interventions, repeat-login/pairing friction, failure recovery, streaming stability on low-end clients, and installer impact on existing host services. Before expanding hardware support or committing to a fork, record reproducible test evidence and ongoing maintenance cost.

Details: [Architecture](application-design.md), [Beta acceptance](BETA-ACCEPTANCE.md), [Wolf integration and fork policy](UPSTREAM-FIRST-WOLF-INTEGRATION.md).
