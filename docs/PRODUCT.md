# Product direction

Status: product intent. Only capabilities in [Current status](CURRENT-STATUS.md) are shipped or verified.

## Purpose

OptiPlex NOW makes an existing personal Linux host accessible from another computer for games, video, files, and basic host control. The intended experience is **install, sign in, choose Games or Videos**. Simplicity is the product. NOW integrates established tools rather than claiming to replace their engines.

The primary audience is an individual or household using a self-managed Linux host and inexpensive client devices. A second audience is a person willing to install a supported NOW Host bundle on an existing machine. Support for arbitrary hardware and paid demand remain unproven.

## Product rules

1. **One clear path.** Normal setup must not require users to understand Moonlight, Wolf, Docker, SSH, ports, VPN topology, or certificates. Technical controls belong in diagnostics.
2. **Fast reconnection.** A previously approved device opens its authorized host without repeating pairing. Never silently authorize an unknown device.
3. **Low-end clients matter.** Test older laptops and modest networks. Offer measured 720p/30 and other profiles when appropriate, without promising frame rates or codecs on unsupported hardware.
4. **Host independence.** The owner's OptiPlex is a reference fixture, not a baked-in dependency. Host address, services, credentials, and deployment layout must be configurable.
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
