# NOW application design — maintained architecture

**Current application:** native GTK3 Linux client/launcher for an **already configured** server. The independent [Studio](https://github.com/SteezyMode/OptiplexStudio) is a creative workspace; neither application replaces Wolf or Moonlight. Start with [contributor guidance](../CONTRIBUTING.md) and [current status](CURRENT-STATUS.md).

The earlier browser synthesizer proposal formerly named "Studio" has been [archived](archive/2026-10-16-studio-synth-design.md). It is **not** the active Studio product, a dependency, or a NOW 2.x commitment.

## Component ownership

| Component | Responsibility |
| --- | --- |
| NOW client (src/main.c) | GTK launcher, settings, connection UI, user-triggered actions, status/tray |
| Process helpers (src/process.c) | Bounded subprocess execution, detached launch and executable discovery |
| Portable presets (src/presets.c) | Allowlisted non-secret connection export/import; legacy headers remain readable |
| Encrypted backups (src/backup.c) | Explicit client backup/restore for selected preferences, SSH keys and Moonlight state |
| Supporting scripts | Tailscale discovery, SSH/SFTP and explicit opt-in server maintenance |
| Future NOW server manager | **Proposed** fresh-host setup, provisioning, ownership, recovery, Wolf management |

NOW 1.13.0 **requires a prepared server**. New Server Setup is a placeholder, not an installer.

## Compatibility contracts

- Current client configuration path: ~/.config/optiplex-desk/config.ini (or under XDG_CONFIG_HOME); existing indexed keys and user preferences must survive upgrades.
- Primary and tray actions use **independent masks**, so upgrading must not silently reset a user's layout.
- Portable .onp files include only a narrowly allowlisted set of non-secret remote settings; never include SSH private keys, passwords or Moonlight pairing.
- Encrypted .onb backups hold sensitive client data; keep them private and test recovery off-host.
- Visible brand, installed package ID, config directory and preset/backup format IDs are **not interchangeable**. Read [public brand migration](https://github.com/SteezyMode/OptiplexSuite/blob/main/docs/PUBLIC-BRAND-MIGRATION.md) before any rename.

## Streaming and identity

NOW launches Moonlight against existing Wolf apps. A Wolf **app**, **profile**, **user/device identity** and **running stream session** are different entities. Two devices opening the same shortcut do not necessarily reconnect to the same live desktop. Native Moonlight pairing and web administrative certificate identity are separate mechanisms.

Preserve existing Wolf volumes, current desktop sessions, persistent homes, credentials, and working Jellyfin/VPN/Caddy services. The future manager must enforce access at the native streaming layer—not merely hide unauthorized desktops in NOW's UI. It must not expose Docker or privileged Wolf management sockets to ordinary client devices.

See [upstream-first Wolf integration](UPSTREAM-FIRST-WOLF-INTEGRATION.md) and [multi-user feasibility](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md). These are plans, not shipped server capabilities.

## Engineering and release gates

The [contributor guide](../CONTRIBUTING.md) has development commands and a source map. Unit and C tests cover helper behavior and portable preset compatibility; Debian package checks cover packaging; Xvfb launches a real GTK window; the linker check ensures a non-executable ELF stack. Tag-only workflows publish new immutable releases, as specified in [release process](RELEASE-PROCESS.md).

A successful CI run still cannot prove Moonlight playback, tray integration, SSH authorization, project persistence, or the 1024x768 layout. Run these manually on a representative client before approving an installed release.

## Scope discipline

Keep UI, code, tests, and documentation synchronized. Record new features as issues with verifiable acceptance criteria. New creative tools and experimental games belong to Studio or their own explicit proposals, not a reintroduced browser synthesizer hidden in NOW's launcher.
