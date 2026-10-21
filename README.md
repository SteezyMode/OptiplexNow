# OptiPlex NOW

[![Validate NOW](https://github.com/SteezyMode/OptiplexNow/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SteezyMode/OptiplexNow/actions/workflows/ci.yml)

**Linux client for games, media, and remote access to an existing personal server.** NOW combines Moonlight/Wolf launch controls, media links, remote files, and basic host management in a GTK3 desktop application.

**Release channel:** [v1.17.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.17.0) is the published **closed-beta prerelease**. Real fresh-client acceptance remains pending; [v1.16.1](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.16.1) is the previous published build.

**Current limit:** NOW is a client for an already configured host. It does not provision a new server, operate NOW user accounts, or send device approval emails. [Product direction](docs/PRODUCT.md) separates these future features from the released software.

## Download

- [Versioned releases and closed-beta installers](https://github.com/SteezyMode/OptiplexNow/releases)
- [v1.17.0 closed-beta release page](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.17.0)
- [Previous v1.16.1 installer](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.16.1)
- [Current code, release and test status](docs/CURRENT-STATUS.md)

Supports compatible x86-64 Debian/Ubuntu-derived Linux distributions. Native Windows and macOS packages are not provided.

Download the **versioned** `OptiPlex-Now_1.17.0_amd64.deb` from the tagged closed-beta prerelease. Verify `SHA256SUMS`, then install through the desktop software installer or from its download directory:

```sh
sudo apt install ./OptiPlex-Now_1.17.0_amd64.deb
```

Existing NOW preferences are intended to survive updates. Back up important client identity before changing pairing, configuration, or devices.

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
