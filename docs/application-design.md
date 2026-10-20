# Client architecture

Status: implemented client boundaries and future contracts. See [Current status](CURRENT-STATUS.md) for observed test coverage.

## Runtime

The installed package provides a GTK3 desktop launcher, supporting scripts, status/tray UI, and optional host-management helpers. NOW invokes separately installed Moonlight for streaming and configured browser/SSH/SFTP programs for other access. Tailscale provides a supported path to remote peers; Tailscale is not a NOW account service.

The app is a client for an **already configured Linux host**. The New Server Setup surface does not provision Wolf, media software, credentials, containers or a VPN.

## Boundaries

| Owner | Owns |
| --- | --- |
| NOW client | Connection/configuration UI, discovery, allowed host actions, status presentation, client backups |
| NOW future host manager | Opt-in installation, service registry, config lifecycle, health/diagnostics, scoped enrollment, update/repair/backup |
| Wolf | Streaming server, application and desktop sessions, Moonlight protocol endpoints |
| Moonlight | Video/audio/control client and device certificate identity |
| Tailscale or a future supported alternative | Network membership and reachability |
| Media software | Jellyfin authentication, media playback, libraries and service internals |
| OptiPlex Studio | Local-first creative projects, tools and AI-assisted workflows |

Do not put server admin power in an ordinary client. The Wolf Unix management socket and Docker control must stay host-local behind an authenticated, narrow mediation layer.

## Identity and data model

Do not conflate the following:

- **User:** principal entitled to access a specific host or logical desktop.
- **Device:** individually paired client certificate and future NOW enrollment credential; revocable separately.
- **Host:** server with a stable ID and explicit ownership.
- **Desktop/profile:** durable workspace definition, owner and data home; not necessarily a current container.
- **Session:** transient connection and running stream state; never infer a connected user from container count.

The current beta uses Tailscale peer access, SSH trust and native Moonlight/Wolf pairing, **not** one unified NOW identity. Future email approval authorizes a new device under an existing account. It cannot bypass host-owner authorization or grant a new host automatically.

## Configuration compatibility

- Persisted client settings: `~/.config/optiplex-desk/config.ini` (or configured XDG config directory). Preserve indexed fields and user-defined links during upgrades.
- Display name, Debian package ID, desktop executable, config directory, preset format and backup format are different compatibility surfaces. Never bulk-rename them.
- `.onp` presets export only allowed non-secret connection settings. Keep legacy files readable.
- `.onb` backups are encrypted and may include SSH/Moonlight identity; protect them like credentials and test restore on a trusted spare client.
- Primary action and tray action selections are separate masks. Migration must retain both.
- Existing host services and user data are outside the client's installation lifecycle unless explicitly opted into an owned management operation.
- Optional Videos, Music, Downloads, and Web Gaming URL settings belong to the user's host and are never hardcoded to the development server. Adding a new optional key to config and portable presets must preserve older config and v1/v2 preset imports.

## Health and capability contracts

Report state and source independently: Tailscale is connected/disconnected, Wolf can be reachable/running, desktop container count is not client session count, and Gluetun health is a container-defined probe rather than an independently verified tunnel exit IP. Missing data is unknown, not healthy.

An eventual host installer must publish managed service IDs and health capabilities instead of requiring a name such as `gluetun`. Avoid accidental Docker permission expansion and application-specific host assumptions.

## Engineering gates

GitHub CI compiles, checks packaging, runs unit checks and GTK smoke tests. The release workflow publishes only new version tags. Neither substitutes for fresh-client pairing, real gameplay, live audio/input, or backup restore.

Technical details: [Pairing contract](WOLF-PAIRING-HOST-CONTRACT.md), [Host installer](HOST-INSTALLER.md), [Wolf adapter/fork policy](UPSTREAM-FIRST-WOLF-INTEGRATION.md), [Beta acceptance](BETA-ACCEPTANCE.md).
