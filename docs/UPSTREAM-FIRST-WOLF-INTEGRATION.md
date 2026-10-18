# NOW product direction — turnkey server + upstream-first Wolf integration

**Status:** Proposed long-term commercial architecture; no server changes, forks or release approved.  
**Date:** 2026-10-19  
**Related:** [NOW current status](CURRENT-STATUS.md), [Studio integration architecture](https://github.com/SteezyMode/OptiplexStudio/blob/main/docs/ADR-002-UPSTREAM-FIRST-INTEGRATED-TOOLCHAIN.md), [Studio local-first ADR-001](https://github.com/SteezyMode/OptiplexStudio/blob/main/docs/ADR-001-LOCAL-FIRST-SHARED-STUDIO-RUNTIME.md).

## Product hypothesis and distinct positioning
NOW should convert a **specified set of supported existing Linux PCs** into dependable personal game-streaming / media / remote-access hosts through a guided installation and ongoing management, without a user hand-configuring Docker, SSH, Wolf, reverse proxy or update routines.

Customers would pay for **safe setup, cohesive administration, supportability, recovery and maintenance**, not for exclusive rights to upstream Wolf/Jellyfin/Moonlight. Compete initially on a tight combination of **remote gaming + independent desktops + optional media**, not a general-purpose all-app marketplace. The broad 'any old PC installs everything' promise is premature until hardware drivers, networking, codecs, permissions and failure modes are tested across supported platforms.

Commercial demand remains **unvalidated**. Development and user support time could exceed revenue if arbitrary unsupported machines are accepted. OptiPlex naming is placeholder; future commercial brand and trademarks require review.

## Core architectural boundary
- **NOW owns:** installer, compatibility preflight, safe host setup, UI, service catalog/profile, lifecycle/update/backup/recovery controller, remote-access setup, health/error diagnosis and user permissions.
- **Wolf owns (upstream):** game/desktop streaming session engine, video/audio encode sessions, Moonlight streaming protocol support and session/container machinery. Keep its process/container lifecycle as native Wolf behavior unless a specific gap proves otherwise.
- **Other upstream tools own:** actual media server and client functionality, rendering, media libraries and streaming playback.
- **Studio owns:** game project data, Codex tasks, Godot/Blender/Blockbench/LMMS integration and the development environment. NOW streams Studio as an optional **presentation option**, not its task engine.

The strategic move is **deep integration, not indiscriminate white-labeling**.

## Wolf: use APIs before forks
The [Wolf source repository](https://github.com/games-on-whales/wolf) declares **MIT** licensing (check actual repo and bundled dependency notices before redistribution). Its **newer beta branch** documents a [REST management API](https://github.com/games-on-whales/wolf/blob/beta/docs/modules/dev/pages/api.adoc) exposed through a **Unix socket** (configurable `WOLF_SOCKET_PATH`), distinct from the Moonlight-facing protocol. **Important version caveat:** the older [stable branch](https://github.com/games-on-whales/wolf/blob/stable/docs/modules/user/pages/configuration.adoc) inspected 2026-10-19 does **not** expose the same documented profile/session management endpoints; our reference host has used the `wolf:stable` image. Do not assume the API exists on the deployed host, or upgrade Wolf to beta on the production machine without a controlled compatibility/rollback test. [NOW 2.x multi-user feasibility review](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md) records the identity/storage authorization gaps. Wolf itself runs flexible streamable applications/desktops in containers.

**Recommended path:**
1. Pin and inspect a known-good Wolf release and the local working configuration. Implement a narrow **NOW-owned Wolf adapter** around documented APIs and supported config, never around brittle active container IDs/ephemeral IPs.
2. Manage known approved applications/profiles (Steam, a separate Studio desktop, later named workspaces), user pairing and session status safely. Preserve existing pairing, working clients, persistent homes and mount boundaries. Provide one-click rollback and no unnecessary duplicate desktops.
3. Build a diagnostics surface: missing GPU/NVIDIA driver matching, no encoder, permissions/devices, network and pairing failures, profile bind mounts, session leaks, unsafe new-image updates. Test on a clean supported machine.
4. Keep Wolf and NOW **separately upgradeable** with a tested compatibility matrix: Wolf version, Docker/Podman support, driver/encoder combinations, client compatibility and app container image version.
5. If an essential feature is unavailable, attempt plugin/config/API extension, upstream PR, then isolated patch set. **Full Wolf fork only when repeated customer evidence and patch burden justify it**.

**Security:** The Wolf Unix-socket API is a powerful host management surface; do not expose it directly to remote browsers, public WAN, Studio UI, or untrusted Wolf application containers. Restrict host socket permissions and use a dedicated, authenticated, least-privilege NOW mediation endpoint with an allowlisted action set. Don't mount the host Docker socket widely or give Codex server administration privileges.

## Product onboarding: smallest credible bundle
An installer should initially target **one or two supported Linux distributions / tested hardware combinations**, not arbitrary old PCs. Suggested first working path:
- Detect hardware, drivers, available encoding support, storage, network, OS and existing services; offer graceful unsupported-hardware errors rather than pretending a generic success.
- Install/configure **one** streaming profile with Wolf+Moonlight, plus optional independent desktop; pair and run a verified actual client test.
- Offer media server (e.g. Jellyfin) as **optional**, with its own user storage and permissions; no silent new public port exposure.
- Guided remote access (Tailscale can be one supported method); explain external account requirements and use TLS/auth rather than unauthenticated convenience.
- Safe updates, service health, redacted diagnostic bundle, backup/restore and uninstall (with clear data retention). **No data loss or drift** if NOW is removed.
- Support unattended recoverability through documented system services; avoid registering extra always-on daemons unless needed.

Do not assume the current `New Server Setup` screen is functional. [Published v1.13.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.13.0) is a Linux **client for an existing server**, not the desired turnkey installer.

## White-label, redistribution and vendor branding
- White-label **NOW's experience** (installer, manager, diagnostics, service profiles, custom icons for NOW). Display proper attribution and upstream names/licenses for included software.
- Avoid removing license notices or representing Wolf, Moonlight, Jellyfin, Tailscale, Godot or NVIDIA drivers as exclusively our IP.
- Fork/rebrand Wolf source only for demonstrated hard blockers or when legally and operationally justified. MIT is permissive but not the same as trademark permission and does not erase dependencies' licenses.
- A separate proprietary orchestration UI may be commercially viable subject to component-specific license, linking/distribution and trademark assessment. Perform a license bill-of-materials audit before customer distribution.
- Avoid maintaining a private copy of a rapidly evolving Linux codec/driver/streaming stack if upstream can be managed through interfaces.

## A practical fork-vs-adapter test
Before creating or maintaining a fork, record: blocked feature, intended user outcome, public upstream feature gap, API/config workaround tried, security impact, number of patches, rebase test on two consecutive upstream versions, QA cost and approximate support savings.

If the only reason is 'make ten applications appear to have our logo' or 'simplify the source tree', **reject the fork**.

## Roadmap order
1. Preserve running NOW v1.13 and working users; audit and consolidate outdated handoffs and unmerged PRs.
2. Prototype a **read-only Wolf API adapter** in an isolated setup (no unreviewed production socket exposure). Validate session/app discovery and list known profiles. An API is not itself a secure remote client protocol.
3. On a test machine, create a **wizard-guided install for one known-good environment** with an actual game-streaming smoke test and rollback. Don't use the owner's heavily configured production server as the 'clean install' testbed.
4. Add safe status/update/recovery, optional media, and narrow independent desktop choices.
5. Trial the first installer with outside users and collect setup duration, intervention rate, support hours, system compatibility, uptime and willingness to pay.
6. Only then assess licensing, commercial branding, paid software/support options and the business case for an upstream fork.

## Non-goals for this decision
This memo does **not** change the Studio v1 frozen milestones, merge the two apps, schedule new daemons, change Wolf config/containers, require Jellyfin/Caddy/VPN to be installed, publish a release, or approve removing working services. User preference for the current system is to preserve existing stream/game/media access while designing future products.
