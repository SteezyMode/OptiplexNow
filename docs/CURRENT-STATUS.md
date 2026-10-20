# Current implementation and verification

Updated: 2026-10-21 JST. GitHub Releases and CI are the authority for new publication events.

## Release state

- **Latest independently verified published release:** [v1.16.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.16.0). The GitHub release has a versioned amd64 .deb, a latest-name .deb, and SHA256SUMS.
- **v1.16.1 source:** merged into `main` as commit `e6df6d06206b359bd4c219bf6c7e4f06db7de2d6`. It includes [#96](https://github.com/SteezyMode/OptiplexNow/pull/96) and [#97](https://github.com/SteezyMode/OptiplexNow/pull/97); the related PR CI passed.
- **Publishing v1.16.1:** requires a new `v1.16.1` tag and a successful tag-triggered release workflow. At the time this document was updated, the tag/release had not been independently verified. Check [Releases](https://github.com/SteezyMode/OptiplexNow/releases), not this snapshot, for the latest published version.

Release publishing changes GitHub artifacts only. It does not modify the running reference server or upgrade installed clients.

## Included in current `main`

- Native GTK3 client, primary actions, tray controls, Settings and setup wizard.
- Tailscale connectivity and server discovery, SSH/SFTP access and host hardware dashboard.
- Moonlight streaming launch for configured Wolf apps, native Wolf pairing dialog, and generated four-digit pairing PIN transported through a dedicated helper.
- Browser launch for configured video, music, and download services.
- Power operations and explicit global Wolf restart with confirmation.
- Portable connection presets and encrypted client backups.
- Read-only VPN status lookup by Gluetun Docker image, not container name. Tailscale and running Wolf desktop indicators use active-state coloring.
- Optional reference-host-specific maintenance helpers. These are not a server installer.

## Evidence boundaries

| Area | Evidence available | Still required |
| --- | --- | --- |
| Package | PR CI compiles, runs tests and package smoke checks | Final tagged v1.16.1 release verification and installation of that .deb |
| UI | Owner has installed and exercised earlier builds on Linux clients | Complete fresh-device usability test for this exact package |
| Pairing | Host read-only helper and SSH transport tested; pairing UI implemented | Actual new-device Wolf authorization and repeat access without re-pairing |
| Streaming | Known existing owner streaming paths used in development | Recorded Games and Videos acceptance on a clean client |
| VPN | Test host has `music-vpn` Gluetun running/healthy; download containers share its namespace | Observe updated NOW widget on actual client; no exit-IP verification |
| Host installer | Design issues and local helper contract exist | Fresh-host installer not implemented |
| NOW-owned identity | Device approval requirement documented | Authentication service and emailed approval not implemented |

Do not call a code path fully verified because CI passed. The next milestone is [Beta 1 acceptance](BETA-ACCEPTANCE.md).

## Tracked roadmap

- [#76](https://github.com/SteezyMode/OptiplexNow/issues/76): private Beta 1 end-to-end gate.
- [#94](https://github.com/SteezyMode/OptiplexNow/issues/94): existing NOW credentials plus email approval for a new device.
- [#98](https://github.com/SteezyMode/OptiplexNow/issues/98): standardized, reproducible NOW Host installer.
- [#85](https://github.com/SteezyMode/OptiplexNow/issues/85): Headscale, low-end client performance, Wolf API/fork investigation.

The client requires an existing, separately configured server. OptiPlex Studio is a separate project. Detailed scope is in [Product direction](PRODUCT.md).
