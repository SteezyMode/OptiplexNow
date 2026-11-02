# Optional Music module — reproducible host reference (Nov 2, 2026)

**Stage: source-controlled reference only, not installed or alpha-accepted.**
The active [Private Alpha 1 contract](../../docs/PRIVATE-ALPHA.md) remains Games, Video, and VPN-isolated Downloads/Files. Music is optional and must not block that release. The reference OptiPlex already has a working independent DroppedNeedle/slskd deployment: **do not start this Compose over it**. A future host installer must adopt detected services or install only after owner confirmation, with backup and rollback.

## What is (and isn't) in this module

- [DroppedNeedle](https://github.com/DroppedNeedle/DroppedNeedle), AGPL-3.0, handles discovery, MusicBrainz requests, imports, tags and its own library. Its upstream Docker image is `droppedneedle/droppedneedle:v2.15.0` (released 2026-09-20). It is **not** a P2P client.
- [slskd](https://github.com/slskd/slskd), AGPL-3.0 **with additional license terms for modified distributions/forks**, is the Soulseek client. Its upstream Docker image is `slskd/slskd:0.26.2` (released 2026-10-23). The license is documented upstream at `LICENSE`/`FORKING.md`; do not fork/rebrand without review.
- [Amperfy](https://github.com/BLeeEZ/amperfy) remains an external iOS Subsonic player. This stack does not install or replace it.
- The existing qBittorrent/Gluetun stack is a **separate** torrent/VPN-isolation service, not a hidden dependency of the music engine. Do not reroute general Soulseek traffic into or out of Gluetun without an explicit, tested configuration.
- Optional integrations such as ListenBrainz, Last.fm, Jellyfin, Navidrome and library scans must be configured explicitly. Do not hardcode any user's access tokens or listening histories.

## Host preparation — disposable install only

Requires a Linux Docker Engine with Compose and access to media volumes. Change the sample paths to a dedicated **new**, writable location on the test host. Never point this recipe at an existing production library or container.

```sh
cd deploy/music
cp .env.example .env
# Edit .env with your HOST_UID, HOST_GID and absolute MUSIC_* roots.
# Make the directories below with suitable ownership for the chosen UID/GID:
#   $MUSIC_STATE_ROOT/slskd
#   $MUSIC_STATE_ROOT/droppedneedle/{config,cache,plugins}
#   $MUSIC_MEDIA_ROOT/{music,slskd/complete,soulseek-share}
docker compose config --quiet
docker compose pull
docker compose up -d
```

**Important:** The example container releases are tag-pinned, not yet image digest-pinned. To reproduce exact image bytes, record the resolved `RepoDigests` for your architecture, verify them upstream, and use immutable digest references in your deployment lockfile. A version tag alone is not a cryptographic guarantee. Do not update images opportunistically without a config/database backup.

The web UIs bind to localhost (DroppedNeedle `127.0.0.1:8688`, slskd `127.0.0.1:5030`) so they are not published to LAN or Tailnet automatically. Use an **already approved** owner-authenticated reverse proxy or an explicitly configured Tailscale Serve endpoint for remote access. Confirm its behavior first; do not overwrite another Tailscale Serve/Caddy configuration or create public Tailscale Funnel exposure.

slskd's `50300/tcp` port is the **Soulseek peer-transfer listener**, not a web admin port. Review the host firewall and the network's port-forwarding requirements before enabling external reachability.

## First-run setup in browser

1. On localhost, sign in to slskd. **Immediately replace its upstream default UI credentials**. Enter your own Soulseek credentials, set `directories.downloads` to `/data/slskd/complete`, and set `shares.directories` deliberately to a dedicated, reviewed path such as `/data/soulseek-share` (never casually share your whole personal media tree). Validate access and read/write permissions. slskd needs at least one intentional shared directory to participate in the network.
2. Open DroppedNeedle on localhost and create its initial administrator account. Configure its library as `/data/music`; inspect every matching/import and make the first scan read-only.
3. Under DroppedNeedle **Settings → Download Client**, point to slskd at the internal Compose name `http://slskd:5030`, supply an appropriate slskd API key, and test connectivity. Both services must resolve the same completed files under `/data/slskd/complete` so imports work.
4. Set quality floors, storage limits, and metadata preferences explicitly. Leave auto-request, auto-upgrade, library reorganization and retagging **off by default**.
5. Request a permitted test album or track, observe `requested → searching → download → verification → imported`, then confirm the file appears in the actual music player/library and survives service restart. Test unavailable tracks and manual review without losing state.
6. If optional personalized discovery is enabled, verify actual scrobbles are flowing from the player into ListenBrainz or Last.fm and that recommendations are not based on an empty account. Do not claim recommendations are individualized merely because an account is connected.

**Legal/operational:** the user is responsible for content permissions, applicable local law, and any files shared on Soulseek. Public distribution of modified AGPL software must follow its license and additional terms. Unmodified deployment of independently licensed upstream services is a simpler route than bundling or forking their source.

## Restore and acceptance

- Back up the complete `MUSIC_STATE_ROOT` (DroppedNeedle config/database, cache, plugins, slskd configuration and credentials) and the separate `MUSIC_MEDIA_ROOT` data as appropriate. Keep the backup private; it contains credentials and possible personal listening data.
- Test restore **on a different disposable host**, using exactly the recorded image versions/digests and mount paths. Verify preserved accounts, correct downloads-import mapping, recommendations (where configured), and no duplicates.
- An owner-authenticated web interface must not expose raw slskd or DroppedNeedle API credentials to browser JavaScript; use per-service authentication and an audited backend if a unified Bruiser Music web UI is added.
- Test connection failure, permission denial, auth revoke, offline UI, unavailable provider and partially completed downloads. The desktop NOW Music tab must degrade harmlessly when no Music service is installed.
- Keep the existing reference host untouched. Real slskd/DroppedNeedle version compatibility, the full restore procedure, an owner iPhone Safari + Tailscale check, and security tests **remain unverified** until physically performed.

## Release / branch status

Source and example Compose alone do **not** constitute a no-terminal installer. A later opt-in graphical host-adoption/install step should detect existing services and require explicit consent before any mutation. Music must never become a mandatory prerequisite for the current three-pillar Private Alpha 1 release.
