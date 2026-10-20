# ADR-001: Single NOW installer, optional server-service adapters

**Date:** 2026-10-20
**Status:** Accepted product direction; **implementation pending**.

## Context
NOW 1.x is a usable Linux client for a server configured separately. The costliest barrier for new users is setting up Wolf, network access and streaming, not opening preexisting services. NOW also offers shortcuts/maintenance for media and browser services, but those must not become required dependencies or distract from streaming.

## Decision
Maintain **one native `.deb` for NOW itself** and one application with selectable client/server/both workflows. Install additional server programs **on demand through their approved upstream distribution methods** after preflight, plan review and explicit consent. Do not bundle all server binaries or provision services inside Debian package post-install hooks.

Use separable service adapters:
- **Core server MVP:** Wolf streaming, a single desktop/game profile, verified native Moonlight pairing and diagnostics.
- **Optional:** Moonlight Web and Jellyfin; DroppedNeedle with optional ListenBrainz/Last.fm connections; an advanced Downloads & Music category with qBittorrent, VueTorrent (qBittorrent web interface), slskd and optional Gluetun/VPN routing. Components are selectable and adoptable independently; coordinated recipes may declare dependencies but never silently install the entire stack. Removing NOW management must not delete application data.
- **Separate product:** OptiPlex Studio; can be streamed as an ordinary desktop application, but has no dependency on NOW.

VPN/network recipes require explicit routing and port plans, secret-safe credential handling, and verified leak/recovery tests before claiming protection. Follow [existing reference stack documentation](../server-setup.md).

Prefer discover/adopt over takeover; preserve existing credentials, mounts, configuration, running services and pairing. Define safe rollback and uninstall/data retention. For privileged actions use a narrow authenticated boundary, never general exposed Docker/Wolf sockets. Prefer upstream supported APIs and configurations before considering forks.

## Alternatives considered
1. **All-in-one huge `.deb`: rejected.** Bundling unrelated upstream binaries complicates updates, licensing and optional service selection.
2. **Separate NOW server and client products: deferred.** Single UX and shared configuration are simpler to start; internal components can remain separately maintainable.
3. **Media-server-centered generic app store: rejected.** Makes NOW less distinctive and much harder to support.
4. **Leave everything as manual setup: rejected as long-term goal.** Retains the largest usability barrier.

## Consequences and validation
Benefits: one entry point, independent updates, optional services, clearer commercial positioning. Costs: version compatibility, privileged setup safety, maintenance and recovery testing. The decision is revisitable after actual clean-install evidence. It authorizes **no server deployment, Docker changes, new public ports, service restart or release**.

See [ARCHITECTURE](../ARCHITECTURE.md), [ROADMAP](../ROADMAP.md), and [UPSTREAM-FIRST-WOLF-INTEGRATION](../UPSTREAM-FIRST-WOLF-INTEGRATION.md).
