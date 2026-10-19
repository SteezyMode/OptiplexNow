# OptiPlex NOW — current status and operator handoff
Updated: **2026-10-19 JST**. Use with the dated [2026-10-16 operational inventory](operations-handoff.md) for service details; that inventory is historical and its release labels are outdated.

## Release and repository
- **Latest published GitHub release: [OptiPlex NOW v1.13.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.13.0)** (published 2026-10-16). Official release contains downloadable amd64 .deb installers and checksum list. 1.12.0 is also released, not an upcoming draft.
- `main` contains the merged [v1.13.0 release PR #7](https://github.com/SteezyMode/OptiplexNow/pull/7). The old [PR #1](https://github.com/SteezyMode/OptiplexNow/pull/1), labeled as a 1.12.0 draft, remains open and should be **reviewed for obsolete/unmerged changes** rather than treated as the current release branch or closed blindly.
- [PR #13](https://github.com/SteezyMode/OptiplexNow/pull/13) proposes renaming the visible desktop label to **Studio** and generalizing the streaming settings label. **Open, not merged** at this audit. The actual Wolf application identifier `OptiPlex Studio Desktop` remains as-is.
- Don't infer the exact app installed on the Mac mini, MacBook, or host from the latest release. A GitHub release does **not** upgrade installed applications.

## Source-only engineering cleanup since v1.13.0

The `main` branch has post-release source changes, **not a new installed package**: separated validation and publication workflows, removed obsolete release upload paths, extracted/tested process and portable-preset modules, replaced manual GTK function declarations with official GTK development headers and runtime type conversions, introduced Xvfb startup and ELF non-executable-stack tests, and added contributor/review guidelines. See Git history and PRs #16–#24 for individual changes.

The automated build/GTK smoke passed, but full real-device integration, low-resolution/tray behavior, stream reconnect and upgrade/rollback tests are **not yet signed off**. Existing compiler warnings and remaining old UI coupling are tracked engineering debt. Do not claim source passing CI means v1.13.0 has been re-released or deployed.

## Current NOW responsibilities
NOW is a separately installable Linux client for remote access/streaming and server conveniences. Its v1.13.0 release supports launching Steam and the Wolf Studio Desktop through Moonlight, configurable service shortcuts, browser-based services, SSH/SFTP and host controls, backup/preset export/import and opt-in Wolf maintenance. See [README](../README.md) for shipped app behavior and limitations.

**It is not the OptiPlex Studio game-development engine.** Godot projects, Blender assets, Codex agents, editable Studio source, Studio's shared runtime and project metadata belong in the separate [OptiPlex Studio](https://github.com/SteezyMode/OptiplexStudio) product. Wolf is a **streaming/presentation option**; local Studio must work without NOW.

## User-observed runtime versus still-open application work
- Tailscale-first SSH/streaming and the independent Wolf desktop were used successfully in the Oct 18/19 Studio session. Existing games, media and server services must remain untouched by release cleanup.
- Wolf inside a separate XFCE/XWayland desktop requires **Godot X11** (`DISPLAY=:0`, `--display-driver x11`, windowed) to display real draggable title bars. **That is Studio's demo launcher behavior, not a NOW release feature.** See Studio [issue #13](https://github.com/SteezyMode/OptiplexStudio/issues/13).
- Native Moonlight pairing and MoonlightWeb browser token/PIN are **separate authentication mechanisms**. Never commit tokens or key material.
- The documented Web Gaming Admin loopback SSH route worked in a manual MacBook check on Oct 16. Do not infer every v1.13.0 GUI path has passed outside-LAN and recovery tests.
- Server state, Docker images and config may drift independently from packaged NOW code. Nothing in this document claims a fresh-server install, automatic Wolf recovery, off-host backup or complete service provisioning.
- v1.13.0 did **not** deliver a turnkey New Server Setup installer; that UI remains a placeholder.

## Open roadmap, product ownership
- [#11](https://github.com/SteezyMode/OptiplexNow/issues/11): simplify Wolf, Steam and remote-access operations.
- [#12](https://github.com/SteezyMode/OptiplexNow/issues/12): quick persistent *development session* entry points, coordinated with **Studio-owned** Codex/tmux lifecycle and [ADR-001](https://github.com/SteezyMode/OptiplexStudio/blob/main/docs/ADR-001-LOCAL-FIRST-SHARED-STUDIO-RUNTIME.md). NOW does not own background agent processes.
- [#14](https://github.com/SteezyMode/OptiplexNow/issues/14): selectable independent Wolf desktops (names/profiles), not automatic new active desktops for every connection.
- [#10](https://github.com/SteezyMode/OptiplexNow/issues/10): VPN status and failure/reconnect alerts; not part of the current cleanup.
- [#8](https://github.com/SteezyMode/OptiplexNow/issues/8), [#9](https://github.com/SteezyMode/OptiplexNow/issues/9): Downloads/Gluetun reliability.
- [UI PR #13](https://github.com/SteezyMode/OptiplexNow/pull/13) needs review and tests before merge or a new release.
- Separate server backups, authenticated web gaming continuity and off-network tests remain tracked in [operations-handoff](operations-handoff.md).

## Next work / guardrails
1. **No automatic NOW release from cleanup commits.** Published version is v1.13.0; release only after device acceptance, version bump, and explicit new tag. Review old PR #1 and current UI PR #13 before deciding which changes are still relevant.
2. Verify only on an actual client before claiming successful deployment, tray behavior or reconnect support. No indiscriminate Wolf restart or volume replacement.
3. Keep game project source, creative integrations and Codex lifecycle in Studio, not NOW; NOW owns optional remote access and planned host provisioning only.
4. Maintain backwards-compatible client config and working `games.monumentrisk.com` public HTTPS. Do not bulk-convert working URLs to SSH/Tailscale-only endpoints or change server auth casually.
5. Preserve Wolf config/data, MoonlightWeb tokens, existing user preferences, Jellyfin/Caddy/VPN/music services and private backups. No credentials in GitHub.

## Source of truth hierarchy
- Published version and assets: GitHub release metadata.
- Frozen Studio v1 acceptance: Studio [issue #3](https://github.com/SteezyMode/OptiplexStudio/issues/3), not NOW's older 'Studio' synth experiment or outdated Oct 16 handoff.
- Actual installed client/runtime: device-specific observation and recent operator test.
- Planned product architecture: Studio ADR-001 and open issues, not proof of shipped behavior.
