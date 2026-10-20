# Existing reference server

**This is an inventory of the owner's test machine, not an installer.** Use [Host installer](HOST-INSTALLER.md) for proposed reproducible deployment. Detailed older Compose, backup and operator procedures are preserved in [dated setup notes](archive/2026-10-20-server-setup-notes.md) and [dated operations notes](archive/2026-10-16-operations-handoff.md). Verify them before performing live maintenance.

## What is confirmed

| Component | Observed 2026-10-21 | Meaning |
| --- | --- | --- |
| Host OS | Pop!_OS 24.04 | Test fixture, not sole supported future host |
| `wolf` | Running Docker streaming service with a local Unix API | Container running is not proof of a connected client |
| Wolf socket | `/run/user/wolf/wolf.sock` inside the container | Privileged, host-local |
| `music-vpn` | `qmcgaw/gluetun:v3.41`, running, Docker health `healthy` | Gluetun health probe succeeded |
| `slskd-vpn` | `slskd/slskd:0.25.1`, running, healthy | Application health, not a separate tunnel proof |
| `qbittorrent-vpn` | `lscr.io/linuxserver/qbittorrent:5.1.4`, running, no Docker healthcheck | Running only |
| Network relationship | slskd and qBittorrent both reference the `music-vpn` container's network namespace | They share Gluetun's namespace; external exit routing was not separately tested |

The earlier status probe assumed a Docker container named `gluetun` and failed because the actual gateway is named `music-vpn`. NOW v1.16.1 code discovers a Gluetun image rather than the old fixed name. This is a reference-host fallback. Future NOW-managed hosts should publish owned service metadata instead of depending on arbitrary container naming.

## Client and host preparation

The client `.deb` does not install Wolf, Docker, Jellyfin, VPN, server backups or a new network. Current manual Beta 1 prerequisites include:

1. A prepared Wolf host exposing supported games/desktops over an authorized network.
2. Tailscale membership approved on client and host.
3. Trusted SSH host identity for status and mediated pairing functions.
4. Host helper at `/usr/local/libexec/optiplex-now/wolf-pair-local` with restricted invocation rights on the reference host.
5. Moonlight available on the client and correctly paired with the Wolf server.
6. Media URLs and independent service logins configured as needed.

Docker group permission is effectively host admin capability. Do not grant that role to arbitrary beta testers. See [Wolf pairing contract](WOLF-PAIRING-HOST-CONTRACT.md).

## Existing backup features

| Feature | Effect |
| --- | --- |
| `.onp` connection preset | Export/import a limited set of non-secret client settings |
| Encrypted `.onb` backup | Explicit client identity and settings backup for a trusted machine |
| Music profile export | Existing-host export; staging import does not deploy a stack |
| Server configuration snapshot | Separately maintained reference-host job; does not constitute full recovery of media, games or every saved state |

Old references to the precise scheduled backup, storage device, Compose layout, VPN credentials or music schema are **historical operator notes**. Do not treat them as a portable automatic setup contract.

## Future installation

The future NOW Host Setup application must own service versions, labels, consistent directories, credentials, networking, idempotent migrations, diagnosis and rollback. Adopt an existing host only after non-destructive inspection and explicit operator approval. See [Host installer](HOST-INSTALLER.md) and [Issue #98](https://github.com/SteezyMode/OptiplexNow/issues/98).
