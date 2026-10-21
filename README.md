# OptiPlex NOW

[![Validate NOW](https://github.com/SteezyMode/OptiplexNow/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SteezyMode/OptiplexNow/actions/workflows/ci.yml)

**Your own entertainment server. Games, video, and private downloads.**

**OptiPlex NOW is an internal development codename, not the future commercial name.** The goal is a single, easy host-and-client application that makes one compatible personal computer a remotely accessible entertainment server. Think **your own GeForce NOW-style game streaming and Netflix-style personal library**, using your hardware and content, without needing to learn Docker, VPN networking, or streaming servers. These comparisons describe user experience, not affiliations or provided catalogs.

### The three public-alpha pillars

| Core experience | Product requirement |
| --- | --- |
| **Independent games** | Stream a real game from the home PC while its physical screen, desktop, keyboard and mouse stay independently usable. |
| **Personal video** | Stream an owner-managed Jellyfin library remotely, even while the server performs other tasks. |
| **Private Downloads** | Search reviewed sources, control qBittorrent and choose download folders remotely. Route **only designated downloader traffic** through an isolated commercial VPN, while the host, Jellyfin and gaming remain on normal networking. Downloads must stop safely if the VPN fails. |

**Owner/admin:** manages downloads, file organization, VPN settings and the server. **Member/viewer:** can play authorized media and permitted games, without file-management or downloader-administration privileges. Enforcement belongs on the server, not just behind hidden buttons.

**Goal:** approximately **15 minutes to a first authenticated game stream** between two compatible, OS-ready computers, using a simple graphical setup and approved-device flow. A single easy sign-in experience is the longer-term design goal; current separate upstream authentications are not yet unified. Linux first, **Windows clients planned**, Windows host support a longer-term feasibility target.

**Public-alpha definition:** all three experiences must be working and independently tested on supported hardware. Media and downloader components remain optional choices for individual customers; an alpha demonstration must qualify all three. Music, books and comics are later possibilities, not first-alpha requirements. VPN subscriptions, including a potential bundled ~$7/month plan, are exploratory and **not needed** for public alpha: customers may use a compatible existing VPN.

[Read the public-alpha requirements and acceptance checklist](docs/PUBLIC-ALPHA.md). [Product roadmap](docs/PRODUCT.md). [Current implementation status](docs/CURRENT-STATUS.md).

**Release channel:** [v1.17.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.17.0) is the published **closed-beta prerelease**. Real fresh-client acceptance remains pending; [v1.16.1](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.16.1) is the previous published build.

**What ships today:** v1.17.0 is a GTK3 **existing-host Linux client**: Moonlight/Wolf controls, Tailscale/SSH onboarding, owner-configured media/download links, SFTP and diagnostics. A guarded clean-host Wolf pilot is in unreleased development source, **not v1.17.0**. NOW does not yet deliver the full public-alpha stack, enforce owner/member roles across it, or offer Windows builds. See [Current status](docs/CURRENT-STATUS.md).

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

## Current media and download integration

On the existing reference server, NOW opens a configured Jellyfin library and qBittorrent/VueTorrent interface, provides SFTP access and reports a Gluetun container health result. The VPN-isolated download arrangement is **manually configured on that host**, not deployed by the NOW installer. A healthy Docker container does not prove VPN egress or leak prevention. Today's generic SFTP shortcut also does **not** enforce the intended future owner/member access rules. This is useful reference behavior, not accepted turnkey installation.

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
| Public-alpha three-pillar requirements and owner/member permission gates | [Public alpha](docs/PUBLIC-ALPHA.md) |
| Implemented, published, unverified | [Current status](docs/CURRENT-STATUS.md) |
| First external tester acceptance | [Beta acceptance](docs/BETA-ACCEPTANCE.md) |
| Code layout and compatibility contracts | [Architecture](docs/application-design.md) |
| Build, release, rollback | [Contributing](CONTRIBUTING.md) and [Release process](docs/RELEASE-PROCESS.md) |
| Host preparation, pairing, future installer and fork policy | [Documentation index](docs/README.md) |

OptiPlex Studio is a [separate local-first creation application](https://github.com/SteezyMode/OptiplexStudio). NOW may stream its desktop but does not manage creative projects. The deprecated Suite is not a dependency.

Application-code licensing has not been selected. Public source availability does not by itself grant redistribution rights. This project is not affiliated with Dell.
