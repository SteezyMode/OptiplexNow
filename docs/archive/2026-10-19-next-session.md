> **ARCHIVED OPERATOR HANDOFF (2026-10-19).** This describes an earlier personal development session, not the live roadmap. For current repository state, use [CURRENT-STATUS.md](../CURRENT-STATUS.md) and the [docs index](../README.md).

---

# Next session — OptiPlex NOW
Updated: **2026-10-19 JST**. This replaces the obsolete Oct 16 assertion that v1.11.9 is current and v1.12.0 is unreleased.

## Read first
- **[Current Status](../CURRENT-STATUS.md)** — current published release, active PRs, product boundaries and near-term roadmap.
- **[Operations Handoff](../operations-handoff.md)** — historical Oct 16 server, Docker, auth and recovery inventory. Do not read historical version statements as current.
- **[Application Design](../application-design.md)** — NOW feature architecture and earlier feature proposals, with updated Studio boundary note.

## Release state
**NOW v1.13.0 is the latest published release** (Oct 16); `main` contains merged release PR #7. **Studio v0.3.0 is a separate app**, not a NOW version. GitHub changes do not update installed Linux clients or the server automatically.

## If resuming NOW work
1. **Do not restart running Wolf/game streams merely to inspect the repo.** Check PR #13 (proposed UI labels **Studio** and **Streaming Settings**) and verify live packaging/UI behavior before merging. The Wolf application target remains **OptiPlex Studio Desktop**.
2. Review old PR #1 carefully against released v1.13.0 and other merged changes. It is still open despite a 1.12.0 title; it may be stale, but do **not** close/merge it without diff review.
3. Reproduce unresolved Web Gaming Admin/Tailscale authentication paths on a real outside-LAN Linux client. Do not conflate native Moonlight pairing with MoonlightWeb certificate token.
4. Maintain working Caddy/public HTTPS `games.monumentrisk.com` alongside Tailscale SSH and optional web admin. Don't disable authentication or broadly reroute existing services.
5. For actual host maintenance, read service versions and config before changing them. Preserve Docker/Wolf volumes, Jellyfin, music/VPN/download services, backups and credentials.
6. Keep heavy AI task/session integration in **Studio**, using [ADR-001](https://github.com/SteezyMode/OptiplexStudio/blob/main/docs/ADR-001-LOCAL-FIRST-SHARED-STUDIO-RUNTIME.md). NOW may expose a *connection* to a persistent Studio workspace; it must not create duplicate host Codex sessions.

## Current active work
Owner is focused on a short zombie encounter game in **OptiPlex Studio**, after a functional V3 animation/encounter prototype and a fixed Wolf XFCE X11 demo window. NOW currently requires **no feature or release intervention** to continue that work.

## Unfinished, not automatically shipped
Fresh-server provisioner, Wolf workspace selection, secure backup/recovery beyond existing client scope, Gluetun and Downloads outage alerts, desktop-session reconnect UX, cross-client launch regression testing. See [issues](https://github.com/SteezyMode/OptiplexNow/issues) and [Current Status](../CURRENT-STATUS.md).

## Confidentiality and minimal-risk operations
No MoonlightWeb tokens, private keys, VPN secrets, full backups or service environment files in the public repo. One terminal command at a time during operator troubleshooting; read-only checks first.
