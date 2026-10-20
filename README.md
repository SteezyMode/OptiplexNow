# OptiPlex NOW

[![Validate NOW](https://github.com/SteezyMode/OptiplexNow/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SteezyMode/OptiplexNow/actions/workflows/ci.yml)

**Linux client for games, media, and remote access to an existing personal server.** NOW combines Moonlight/Wolf launch controls, media links, remote files, and basic host management in a GTK3 desktop application.

**Release channel:** [v1.16.1](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.16.1) is the published private closed beta build. Fresh-client acceptance remains pending.

**Current limit:** NOW is a client for an already configured host. It does not provision a new server, operate NOW user accounts, or send device approval emails. [Product direction](docs/PRODUCT.md) separates these future features from the released software.

## Download

- [Latest official release and checksums](https://github.com/SteezyMode/OptiplexNow/releases/latest)
- [Direct amd64 Debian package](https://github.com/SteezyMode/OptiplexNow/releases/latest/download/OptiPlex-Now_amd64.deb)
- [Current code, release and test status](docs/CURRENT-STATUS.md)

Supports compatible x86-64 Debian/Ubuntu-derived Linux distributions. Native Windows and macOS packages are not provided.

Download the `OptiPlex-Now_amd64.deb` package, then install through the system's software installer or from its download directory:

```sh
sudo apt install ./OptiPlex-Now_amd64.deb
```

Existing NOW preferences are intended to survive updates. Back up important client identity before changing pairing, configuration, or devices.

## Connect to an existing host

1. Install NOW and sign into Tailscale with an account already approved for the host.
2. In **Settings > Setup Wizard**, discover the host or enter its address and SSH username. Confirm the expected SSH fingerprint.
3. Choose **Connect to Game Host**. Install/select Moonlight if needed and complete Wolf pairing.
4. Use **Games** for the configured streaming apps or **Videos** for the media service URL.

**Release compatibility:** the published v1.16.1 household beta still contains reference-host defaults. New development code removes those defaults: a fresh client starts with empty Videos, Music, Downloads, and Web Gaming URLs. Configure services belonging to your own host, or import a trusted connection preset. Existing saved URLs remain intact; Tailscale does not sign into Jellyfin.

**Still manual:** first-time SSH authorization, a separately installed host pairing helper, and aspects of Wolf pairing. The development client accepts an optional **Web Gaming URL** in Settings > Gaming & Streaming; an existing installation must set it once after upgrading to a future release with this change. Streaming, Videos, Music, and Downloads are independent, configurable services. An already paired device should not be treated as proof that unpaired onboarding works. See [Beta acceptance](docs/BETA-ACCEPTANCE.md).

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
