# Server setup and backups

Fresh-server provisioning is not implemented in 1.11.9. These notes distinguish the existing server configuration from the remaining automation work.

## Backups

These are separate features:

| Backup | Included in the client? | Scope |
| --- | --- | --- |
| Export My OptiPlex | Yes | Connection preset; excludes authentication material |
| Export Full Backup | Yes | Encrypted client settings, SSH keys and supported Moonlight configuration |
| Scheduled server configuration backup | No | Separately installed server-side job |

Full client backups contain sensitive credentials. Keep them private and restore them only on trusted computers. Tailscale requires separate authentication. None of these features should be treated as a backup of games, media or every game save.

The existing reference server has a daily configuration backup with seven retained copies on a separate physical disk. It covers Wolf configuration, custom system services, `/usr/local/bin`, mount settings and Wolf container metadata. This is a limited configuration snapshot, not a full server recovery image. Installing the client on another PC does not create that job.

## Music server profiles

In **Setup Wizard → Server → Music server profiles (this PC)**, export the existing music stack or import a profile into a new folder. Run export on the server itself. This tool currently supports the four-service JSON Compose layout described below.

Export asks for the Compose file and output archive path. It stops the stack while reading its state and then starts only the services that were running beforehand. Expect a music/download interruption. It saves Compose and env files, container metadata, slskd state, qBittorrent settings, and Dropped Needle configuration, database, cache, plugins and imports. Separate media/download mounts are excluded. Imports and caches can still make a profile large; the tool shows an estimate before confirmation.

The archive contains secrets and is **not encrypted**. Files are created with private permissions. Keep it off GitHub. Dropped Needle's `.env` encryption key must stay with its database: the database contains service connections, ListenBrainz/Last.fm preferences, playlists and listening history. Schema presence does not confirm that a particular account is connected.

Import checks paths and file checksums and extracts into a new private folder. It never overwrites a destination, installs services or starts containers. Symlinks and special files are currently unsupported. A profile is a preservation/staging step, **not an automatic migration**: deployment still needs path, ownership, networking and credential checks for the destination server. Container metadata is retained as reference; runtime-only configuration is not automatically converted into Compose.

## Existing music and VPN setup

This stack is already deployed on the reference server. Recreating it through the wizard is not implemented yet.

Two separate networks serve different purposes:

- **Tailscale** connects clients to the server and its web interfaces.
- **AirVPN**, managed by **Gluetun**, carries the download applications' VPN traffic. It does not replace Tailscale or route the entire host through AirVPN.

| Service | Network and role |
| --- | --- |
| Gluetun | AirVPN over WireGuard; Japan server selection; owns the shared download network |
| slskd | Shares Gluetun's network; web UI on 5030; observed peer listener on 47037 |
| qBittorrent | Shares Gluetun's network; web UI on 8085; observed peer listener on 6881 bound to the VPN interface |
| Dropped Needle | Separate container network; music service on 8688; access to the music/download storage |

The three host-published web ports (5030, 8085, 8688) bind to the server's Tailscale IPv4 address. Gluetun allows inbound web access on 5030 and 8085 and VPN-side incoming traffic on 47037. Its outbound subnet exceptions include the Tailscale range and the reference server's LAN subnet; these exceptions must be reviewed for each new installation.

The observed slskd listener matches the VPN firewall port. This does **not** verify that the corresponding AirVPN account-side port reservation is active or reachable externally. qBittorrent listens on a different port and is not established as externally forwarded. Do not assign both applications the same listening port: they share one network namespace.

Gluetun receives settings from a separate `vpn.env` file using Compose's raw env-file format. The file contains the AirVPN WireGuard private key, preshared key, tunnel addresses and MTU, plus server selection and firewall settings. It must stay private. The container uses `NET_ADMIN` and `/dev/net/tun`.

Both download applications wait for Gluetun's healthy state at startup. A systemd service waits for the configured Tailscale IPv4 address before running `docker compose up -d`; containers use `unless-stopped` restart policies. This avoids attempting to publish ports before the Tailscale address exists. Startup health checks alone are not a verified VPN leak test or a complete recovery strategy after VPN container replacement.

Persistent storage is mounted separately for slskd configuration/downloads, qBittorrent configuration/downloads, and Dropped Needle configuration, cache, plugins and imports. The deployed Dropped Needle container can access a broad storage mount; a fresh installation should ask for explicit folders and grant only the access needed.

### What the setup wizard must handle

1. Select the optional music and download components; preserve existing installations.
2. Import the user's AirVPN WireGuard configuration locally without printing or bundling its secrets.
3. Ask for server region, folders, account credentials and any AirVPN-reserved incoming ports. Account-side reservations must be supplied or verified, not assumed from a firewall rule.
4. Generate protected configuration files, independent app listening ports, and explicit LAN/Tailscale access exceptions.
5. Bind management interfaces to the selected Tailscale address and install startup ordering.
6. Check VPN health, download-app routing, service access and recovery after a VPN interruption before reporting completion.
7. Include relevant configuration in scheduled backups and document restoration. Backups containing VPN or application credentials need appropriate protection.

These are automation requirements derived from the working deployment. The current client does not yet perform them.

## Fresh-server setup: planned

The intended flow is **check compatibility → select services → select storage → install → connect → test**. The current New Server Setup screen is a placeholder.

Initial target: a clean Ubuntu/Pop!_OS 24.04 server with an NVIDIA GPU. This is a proposed support scope, not a claim that an automated installer has been tested.

Selectable components:

| Component | Intended setup |
| --- | --- |
| Gaming | Wolf, GPU/container prerequisites, game storage and Moonlight pairing |
| Video | Jellyfin, media folders and client access |
| Music | Optional recipe based on the reference music stack, including Dropped Needle |
| Music/download tools | Optional slskd and qBittorrent, with Gluetun VPN configuration where selected |
| Remote access | Tailscale sign-in, device selection and startup checks |
| Backups | Configuration backup destination, schedule, retention and documented restore steps |
| Scheduled TV | Optional ErsatzTV integration with Jellyfin |

The installer should detect existing services, explain proposed changes, preserve existing data and resume safely after an interrupted run. Music and download tools must remain optional. Users supply their own credentials and paths; personal secrets or addresses must not be embedded in installer defaults. The inspected music/VPN topology is documented above; credential import, application integration and end-to-end installation still need implementation and validation.

Moving a client to a different network is already supported through Tailscale. Building an entirely new server ecosystem is the planned work above.

## ErsatzTV and Jellyfin

ErsatzTV is a separate server service that turns a media library into scheduled channels. Configure channels in ErsatzTV, then add its M3U tuner and XMLTV guide URLs under Jellyfin's Live TV settings.

Viewers watch through Jellyfin's Live TV section. OptiPlex Now's existing Videos shortcut can open Jellyfin; a separate client feature is not required. A future server installer can offer ErsatzTV as an optional component. It is not installed by this client release.

- [ErsatzTV installation](https://ersatztv.org/docs/installation/)
- [Connect ErsatzTV to Jellyfin](https://ersatztv.org/docs/clients/jellyfin/)

