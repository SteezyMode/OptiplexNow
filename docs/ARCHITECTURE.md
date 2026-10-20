# OptiPlex NOW architecture and proposed boundaries

**Status:** Architecture direction as of 2026-10-20. This is **not** a description of currently shipped server provisioning. Check [CURRENT-STATUS](CURRENT-STATUS.md) and tagged source for implemented functionality.

## Product
One native `.deb` installs the NOW application. The app supports **client**, **server setup/management**, and **both** as user-selectable workflows in the planned generation. The package contains the NOW UI, setup orchestration, safety checks and service adapters—not vendored Wolf, Jellyfin, DroppedNeedle or media libraries. Initial target: a small documented compatibility matrix for supported Debian/Ubuntu-based x86-64 machines; expanding hardware/OS support requires testing.

### Responsibilities
| Layer | Owns | Does not own |
| --- | --- | --- |
| NOW client | Profiles, discovery, launching and user-facing status | Upstream streaming/media engines |
| NOW setup/manager (planned) | Preflight, plans, approved provisioning, narrow lifecycle actions, health, update, recovery | General-purpose Docker management |
| Wolf adapter (planned) | One tested streaming host/profile, pairing/status and version-safe operations | Wolf's streaming implementation |
| Moonlight Web adapter (optional) | Existing browser streaming endpoint discovery and supported maintenance | Wolf/Moonlight internals |
| Jellyfin adapter (optional) | Discovery, optional install, health and open native UI | Media transcoding, libraries and playback logic |
| DroppedNeedle adapter (optional) | Discovery, optional install, health and open native UI | Music discovery/acquisition business logic |
| OptiPlex Studio | Independently installed creative/project workflows | NOW server management |

Wolf and Moonlight/Web may use their upstream mechanisms and versions. Service integrations should be independently enabled, disabled, and upgraded. No optional service is a prerequisite to launch NOW.

## Provisioning flow (planned)
1. User chooses client/server/both; perform read-only OS, GPU/encoder, storage, networking and service discovery.
2. Show supported/unsupported combinations and whether each service is already installed, can be adopted, or needs installation.
3. Build a previewable plan listing packages/images, disk mounts, privileges, ports, credentials and impact on running services; require explicit user approval.
4. Apply idempotently with least privilege and pinned/compatible upstream sources; do not silently overwrite discovered setups.
5. Verify **actual** streaming/pairing or service health, not just process/container existence; provide diagnostics and recorded changes.
6. Offer documented update/recovery/uninstall with backup and retention choices. Rollback must specify what it can and cannot restore.

Do not perform privileged host actions directly from an untrusted client GUI/web request. Use an authenticated, narrowly scoped management boundary; avoid exposing Docker or Wolf administrative sockets externally. Secure remote connectivity may support Tailscale, but no mandatory proprietary cloud account is part of NOW's core design.

## Initial MVP
A reproducible Wolf deployment with a single usable streamed desktop/game profile, one paired Moonlight client, failure diagnostics, safe repeat installation and recovery on a fresh supported machine. User-selected media/browser services come afterward. Preserve existing NOW client utilities and legacy profiles through that transition.

## Source of truth
For existing implementation use tests/source + [CURRENT-STATUS](CURRENT-STATUS.md). For priorities use [ROADMAP](ROADMAP.md). For rationale use [ADR-001](adr/001-single-package-modular-provisioning.md) and the existing [upstream-first Wolf strategy](UPSTREAM-FIRST-WOLF-INTEGRATION.md). These planning documents authorize no live host changes.
