# OptiPlex NOW — current status
Updated: **2026-10-20 JST**.

## Release

- **1.14.0 — Streaming & Maintenance**: accepted on a Mac mini after reinstallation of the revised candidate; GitHub PR #36 CI passed, and all 44 Python tests passed locally. Publication is by new immutable `v1.14.0` tag only. Check [GitHub Releases](https://github.com/SteezyMode/OptiplexNow/releases) for the authoritative published status.
- **Previous published version**: [1.13.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.13.0). Installed versions may differ between devices.
- [PR #36](https://github.com/SteezyMode/OptiplexNow/pull/36) contains the release candidate. The final accepted source commit before documentation updates was `bbb309b`.

## Included in 1.14.0

- Streaming Setup (Moonlight and Wolf), direct game/desktop launching, editable primary/tray shortcuts, server status, media links, SSH/SFTP, client backups and power operations.
- Web Gaming administration and opt-in **manual** MoonlightWeb maintenance on supported existing Docker deployments. Server helper must be installed separately on the host; a client-only install does not enable remote maintenance.
- Bruiser is **not** an integrated NOW service. The separate installation, containers and data are not modified. Previous configuration entries remain readable for compatibility.
- Existing NOW configuration is retained. No fresh-server provisioning is shipped.

## Verified versus not verified

- **Verified**: native AMD64 package build, 44 local Python unit tests, PR CI package/GTK verification, user-observed Mac mini install and Settings usability, isolated disposable Docker backup and rollback tests.
- **Not verified**: production MoonlightWeb image update and schema downgrade, uninterrupted Wolf desktop/session persistence, a full outside-LAN reconnect, or a new-server installer. Never imply these are complete.
- Production OptiPlex host was not upgraded simply by testing the client. Existing Wolf, Studio, Jellyfin, VPN, music and Bruiser services are independent.

## Roadmap / boundaries

- [#37](https://github.com/SteezyMode/OptiplexNow/issues/37): proposed optional Downloads → Files → Library → Play media module.
- [#38](https://github.com/SteezyMode/OptiplexNow/issues/38): clean Wolf Studio desktop installation and project persistence.
- [#39](https://github.com/SteezyMode/OptiplexNow/issues/39): Bruiser separation and future optional integration.
- [Multi-user desktop feasibility](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md), [upstream-first server installer strategy](UPSTREAM-FIRST-WOLF-INTEGRATION.md): proposals, not deployed capabilities.
- OptiPlex Studio remains a separate local-first game-creation application and project owner; NOW is its optional access/streaming companion.

See [release process](RELEASE-PROCESS.md), [MoonlightWeb maintenance](moonlightweb-maintenance.md), and historical [operations handoff](operations-handoff.md). Do not expose credentials or disrupt the live reference server as part of documentation or release cleanup.
