# OptiPlex NOW

[![Validate NOW](https://github.com/SteezyMode/OptiplexNow/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SteezyMode/OptiplexNow/actions/workflows/ci.yml)

**Your games. Your movies. Your music. Your own server.**

OptiPlex NOW aims to make a compatible computer your private alternative to cloud gaming and media subscriptions: **a personal GeForce NOW-style game host, Netflix-style media library, and Spotify-style music library**, using software and content you control. These are product comparisons, not affiliations, supplied media catalogs, or claims that NOW provides licensed content.

### The product we're building

| Experience | Intended result |
| --- | --- |
| **Independent gaming** | Play remotely in a separate Wolf-managed session while the host's physical desktop stays usable. Shared GPU/CPU resources still limit simultaneous workloads. |
| **Movies and files** | Stream your own Jellyfin library, browse/manage server files remotely, and queue lawful downloads on the home server while watching from another device. |
| **Music** | Discover, request, organize and play your own collection with optional tools such as [DroppedNeedle](https://github.com/DroppedNeedle/DroppedNeedle), slskd and compatible media players. |
| **Private operation** | Keep ordinary gaming, media playback and file access on normal server networking, while routing configured download clients through their own VPN gateway. Verify isolation rather than assuming a green VPN indicator proves it. |

**Goal:** On supported, OS-ready host and client machines, approximately **15 minutes from installing NOW on both to a working private remote stream**, without requiring Docker, VPN, certificate or pairing knowledge. No NOW-operated website or central cloud service should be necessary for basic self-hosted use. The owner's existing services may still expose private web UIs; native controls can replace repetitive browser steps over time.

**Platform direction:** Linux host and client first; **Windows clients planned**, **Windows hosts a longer-term goal** with a separate technical and licensing feasibility gate for independent sessions. macOS is not promised. The initial implementation must not force every user to install gaming, Jellyfin, music and download stacks together.

**Release channel:** [v1.17.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.17.0) is the published **closed-beta prerelease**. Real fresh-client acceptance remains pending; [v1.16.1](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.16.1) is the previous published build.

**What ships today:** v1.17.0 is primarily a GTK3 client for an **already configured Linux host**, integrating Moonlight/Wolf, Tailscale/SSH, media links, SFTP and diagnostics. A guarded clean-host Wolf installer exists only in unreleased development builds. Independent-session behavior, complete fresh-host provisioning, native media/download/music administration and Windows builds are **not yet product-accepted or shipped**. See [Product direction](docs/PRODUCT.md) and [Current status](docs/CURRENT-STATUS.md).

## Download

- [Versioned releases and closed-beta installers](https://github.com/SteezyMode/OptiplexNow/releases)
- [v1.17.0 closed-beta release page](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.17.0)
- [Previous v1.16.1 installer](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.16.1)
- [Current code, release and test status](docs/CURRENT-STATUS.md)

**Available package:** compatible x86-64 Debian/Ubuntu-derived Linux systems. No Windows or macOS package yet; Windows client and host support are planned at different milestones.

Download the **versioned** `OptiPlex-Now_1.17.0_amd64.deb` from the tagged closed-beta prerelease. Verify `SHA256SUMS`, then install through the desktop software installer or from its download directory:

```sh
sudo apt install ./OptiPlex-Now_1.17.0_amd64.deb
```

Existing NOW preferences are intended to survive updates. Back up important client identity before changing pairing, configuration, or devices.

## Today's media and download integrations

NOW already opens owner-configured Videos, Music and Downloads services and offers SFTP access to remote files. On an existing home server, a useful optional configuration is **Jellyfin for normal-network streaming**, **qBittorrent behind a dedicated Gluetun VPN gateway**, and **DroppedNeedle with slskd** for music discovery, requesting and organizing. The reference server has a Gluetun/slskd/qBittorrent arrangement; this is **not automatically installed or independently VPN-leak-tested** by NOW.

**Future native integration:** use authenticated service APIs to manage download queues, music requests, library availability and file operations within NOW, without requiring a NOW website. This must be optional and must not expose Docker admin access, bypass service authentication, promise uninterrupted Jellyfin playback under heavy load, or silently route all home-server traffic through the download VPN.

## Unreleased development: NOW Host pilot

The current source includes a separate **Server Setup** GUI with real read-only hardware checks and a deliberately restricted advanced installer for a **new** Ubuntu/Pop!_OS 24.04 AMD, Intel or NVIDIA host. The pilot needs Docker/Compose, owner confirmation, OS administrator authentication and verified immutable image inputs. NVIDIA requires an exact driver-installer SHA256 and builds a new versioned userspace volume without changing host drivers.

**It is not in published v1.17.0, not a one-click installer, and not yet accepted on physical GPU hardware.** No complete streaming, automatic driver-update migration, repair or uninstall has been demonstrated. Do not install onto an already working Wolf host.

See [Host installer scope, safety and physical alpha checklist](docs/HOST-INSTALLER.md) and [Current verification](docs/CURRENT-STATUS.md).

## Connect to an existing host

1. Install NOW and sign into Tailscale with an account already approved for the host.
2. In **Settings > Setup Wizard**, discover the host or enter its address and SSH username. Confirm the expected SSH fingerprint.
3. Choose **Connect to Game Host**. Install/select Moonlight if needed and complete Wolf pairing.
4. Use **Games** for the configured streaming apps or **Videos** for the media service URL.

**Release compatibility:** v1.17.0 starts fresh profiles without the previous developer-specific host, SSH username, Videos, Music, Downloads or Web Gaming defaults. Configure services belonging to your own host or import a trusted connection preset. Previously saved URLs remain intact. Tailscale does not sign into Jellyfin.

**Still requires owner action:** server-side Wolf pairing support must already be configured; Tailscale sign-in, host fingerprint verification, and Wolf/Moonlight authorization require explicit owner participation. The client now offers GUI workflows, but none is confirmed end-to-end on a fresh physical client. On an existing installation, configure the optional **Web Gaming URL** once under Settings > Gaming & Streaming if you previously relied on the developer-specific fallback. Streaming, Videos, Music and Downloads are independent services. See [Beta acceptance](docs/BETA-ACCEPTANCE.md).

## Available functions

- Start Steam or a configured desktop through Moonlight and Wolf.
- Open configured video, music, download and optional Web Gaming services in a browser. These are user-supplied endpoints, not project-hosted services.
- Open an SFTP file browser and an SSH terminal.
- Show CPU/GPU/memory information and host service states for Tailscale, VPN, Wolf, and desktop containers.
- Configure primary and tray actions; request host power or global streaming-service restart with confirmation.
- Export non-secret connection presets and encrypted client-identity backups.
- Use optional server-specific maintenance tools with documented prerequisites.

A green VPN indicator reports the selected Gluetun container's own health check, not an independently verified exit IP. A running Wolf desktop container is not necessarily an active connected streaming client.

## Development

```sh
make check-process check-presets
python3 -m unittest discover -s tests -v
make package
```

A clean build fetches pinned, integrity-checked fonts. See [Contributing](CONTRIBUTING.md) for dependencies, source map, CI rules, and host safety. Only version-tagged workflows publish installers. Generated `.deb` files are not committed to source control.

## Documentation

| Subject | Primary reference |
| --- | --- |
| Scope, vision, principles, phases | [Product direction](docs/PRODUCT.md) |
| Implemented, published, unverified | [Current status](docs/CURRENT-STATUS.md) |
| First external tester acceptance | [Beta acceptance](docs/BETA-ACCEPTANCE.md) |
| Code layout and compatibility contracts | [Architecture](docs/application-design.md) |
| Build, release, rollback | [Contributing](CONTRIBUTING.md) and [Release process](docs/RELEASE-PROCESS.md) |
| Host preparation, pairing, future installer and fork policy | [Documentation index](docs/README.md) |

OptiPlex Studio is a [separate local-first creation application](https://github.com/SteezyMode/OptiplexStudio). NOW may stream its desktop but does not manage creative projects. The deprecated Suite is not a dependency.

Application-code licensing has not been selected. Public source availability does not by itself grant redistribution rights. This project is not affiliated with Dell.
