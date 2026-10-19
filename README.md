# OptiPlex Now

> **Current project/release status (2026-10-19):** See [Current Status](docs/CURRENT-STATUS.md) for the latest verified v1.13.0 release, unmerged UI PR #13, open reliability work, and the boundary between NOW and the independent OptiPlex Studio. The older [October 16 operations handoff](docs/operations-handoff.md) is a historical server snapshot, not a current release plan.


**Remote development:** [Persistent SSH/Codex sessions with tmux](docs/remote-development-tmux.md) — survive client disconnects (not host reboots).

**Operator handoff:** [Observed server stack, recovery, and outstanding verification](docs/operations-handoff.md). Read this before editing the reference server or resuming unreleased 1.13.0 work. The handoff separates verified observations from planned features.

A personal Linux launcher for a home server: games through Moonlight, video and music in the browser, file access, SSH and host controls.

**New to this repository?** Start with [CONTRIBUTING.md](CONTRIBUTING.md): a two-minute product brief, source-code map, exact build/test commands, safety boundaries and where to help. For the distinction between this client and the independent creative application, see [Suite architecture](https://github.com/SteezyMode/OptiplexSuite/blob/main/ARCHITECTURE.md).

**Current version: 1.13.0. Requires an existing server. Fresh-server installation is not implemented.** The New Server Setup screen is a placeholder. Music profiles can be exported and imported into a staging folder, but importing does not install or start services.

## Long-term product architecture

- [Turnkey server and upstream-first Wolf integration](docs/UPSTREAM-FIRST-WOLF-INTEGRATION.md): guided install and management, Wolf API adapter, version compatibility, safe updates and fork criteria. **Proposed strategy, not a shipped installer.**
- [NOW 2.x multi-user desktop feasibility](docs/MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md): Wolf stable/beta capability differences, user/device authentication and persistent storage design, safe isolation, staged experiment and acceptance criteria. **Review only; no live server changes.**

## Development

Version 1.13.0 adds opt-in Wolf maintenance, direct Desktop and Web Gaming actions, an SSH-backed Web Gaming Admin shortcut, and an optional Bruiser AI shortcut under Additional Services, automatically opening Open WebUI on the configured server's port 3000 unless overridden. Settings contains a separate Bruiser AI Admin shortcut. Settings now lets you choose any of the nine service actions as Primary Actions or move them into Additional Services, independently of tray shortcuts. Existing installs keep their previous eight featured actions; fresh installs start with six. Downloads still launches VueTorrent. Automated build checks do not replace on-device end-to-end tests. See [application structure](docs/application-design.md).

## Install

[Download OptiPlex Now 1.13.0](https://github.com/SteezyMode/OptiplexNow/releases/latest/download/OptiPlex-Now_amd64.deb)

```sh
sudo apt install ./OptiPlex-Now_amd64.deb
```

Quit and reopen the app after updating. Existing settings are retained. The link above downloads the latest release directly. Versioned installers and checksums are available on the [Releases page](https://github.com/SteezyMode/OptiplexNow/releases).

Supports x86-64 Debian/Ubuntu-based Linux, including compatible Linux installations on Apple hardware. Native Windows and macOS builds are not included.

## Connect

1. Sign into Tailscale on the server and client.
2. Open **Settings → Setup Wizard**. Choose **Find server on Tailscale**, then confirm the server and SSH username.
3. Authorize SSH, verifying the server fingerprint when prompted.
4. Install or select Moonlight and pair it with Wolf.
5. Set the video, music and download service URLs. For Dropped Needle, leave Music URL blank to use `http://SERVER:8688`, or enter its existing address. The Music button opens its controls in your browser; sign in there.

The Tailscale picker lists devices; it does not install services or grant access. Manual addresses also work. Both ends need to remain connected to Tailscale for remote access.

## Features

- Launch Steam or OptiPlex Studio Desktop directly through Moonlight; the Desktop shortcut uses Wolf's OptiPlex Studio Desktop application.
- Open the existing Downloads shortcut in VueTorrent using the configured server host on port 8085 (requires qBittorrent/VueTorrent installed on that server).
- Open video, music and download services in the browser.
- Browse server files over SFTP and open an SSH terminal.
- View server hardware and status; wake, sleep, restart or shut down the host when configured.
- Use tray shortcuts and restart the streaming service.
- Export connection presets or encrypted client backups containing SSH keys and supported Moonlight settings.
- Export the supported music server profile, including its configuration, credentials and database; verify and stage an imported profile in a new folder.

**Restart streaming service** interrupts active streams. It requires Docker, a `wolf` container, sudo access and `/usr/local/sbin/wolf-prepare-devices` on the host. A running container does not by itself confirm successful playback.

Music-profile export runs on the server itself and temporarily stops the music/download stack. Its archive is private but unencrypted. Import does not remap paths, configure networking or deploy containers. Keep profiles and credentials out of GitHub.

## Server setup

[Server configuration, VPN, backups and planned installer](docs/server-setup.md)

Those notes document the working AirVPN/Gluetun, slskd, qBittorrent and Dropped Needle arrangement, including the database and encryption key needed to preserve account integrations. They also describe Jellyfin/ErsatzTV and the remaining fresh-server work.

Installing this client does not install Wolf, Jellyfin, a VPN stack, ErsatzTV or scheduled server backups.

## Startup and troubleshooting

Add `optiplex-now --start-in-tray` to desktop startup. Edit an existing entry instead of adding a duplicate. The older `optiplex-desk` command remains as a compatibility alias.

- **Offline / Pair SSH:** check the address, Tailscale sign-in and SSH authorization.
- **Games do not open:** check Moonlight, pairing and Wolf's advertised Steam application.
- **No tray icon:** enable a StatusNotifier host or supported notification area. Without tray support, the app opens a window instead.
- **Files fails on COSMIC:** check GVFS SFTP and FUSE support.

## Build

Requires x86-64 Linux, GCC, make, binutils, curl, Python 3, GTK 3/Gio runtime libraries, fontconfig and OpenSSL development files. Pillow is required to package the current icon sizes. The profile helper requires Python 3.11 or newer.

```sh
make check-process check-presets
python3 -m unittest discover -s tests -v
make package
```

The build downloads Inter and Limelight fonts and writes the installer to `dist/`. Fonts are embedded; end users do not fetch them at runtime. See [font notices](FONT-NOTICES.md).

`src/` contains the application and helpers; `tests/` contains unit and regression tests; `assets/` contains icons. **Prebuilt installers are published only through [GitHub Releases](https://github.com/SteezyMode/OptiplexNow/releases)**, not stored in the source tree. Generated build folders and personal credentials are excluded.

The build and profile-tool tests pass. The new music-profile workflow has not yet been tested against the live reference server. No application-code license has been selected; clarify licensing before outside contributions or commercial distribution. This project is not affiliated with Dell.
