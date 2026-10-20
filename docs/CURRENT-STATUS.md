# Current implementation and verification

Updated: 2026-10-21 JST. GitHub Releases and CI are the authority for new publication events.

## Release state

- **Published closed beta installer:** [v1.16.1](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.16.1). The tag points to `e6df6d06206b359bd4c219bf6c7e4f06db7de2d6`. The tag-triggered **Publish OptiPlex NOW** workflow completed successfully (run `39475111081`).
- **Official assets:** `OptiPlex-Now_1.16.1_amd64.deb`, `OptiPlex-Now_amd64.deb`, and `SHA256SUMS`.
- **Included fixes:** [#96](https://github.com/SteezyMode/OptiplexNow/pull/96) colors connected Tailscale and positive Wolf desktop states; [#97](https://github.com/SteezyMode/OptiplexNow/pull/97) detects the Gluetun image under a custom container name.
- **Acceptance:** The artifact is published for **private closed beta testing**, but a clean-client install, first-time pairing and actual stream have not yet completed the Beta 1 checklist.

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

## Portable defaults (development source, not v1.16.1)

New source changes after the v1.16.1 tag remove the reference-host video and Web Gaming domain defaults, the reference SSH username, and automatically guessed optional service ports. Web Gaming and Downloads use user-configured URLs. Previously saved client URLs stay unchanged, but existing users must configure a Web Gaming URL after installing a future release because the old fixed domain was never saved to their config. **The published v1.16.1 installer is unchanged and still has the historical household defaults.** Verify the new code through CI and a clean-client test before making a new release.

## Evidence boundaries

| Area | Evidence available | Still required |
| --- | --- | --- |
| Package | PR CI compiles, runs tests and package smoke checks | Official artifact published; install and device validation of that .deb still pending |
| UI | Owner has installed and exercised earlier builds on Linux clients | Complete fresh-device usability test for this exact package |
| Pairing | Host read-only helper and SSH transport tested; pairing UI implemented | Actual new-device Wolf authorization and repeat access without re-pairing |
| Streaming | Known existing owner streaming paths used in development | Recorded Games and Videos acceptance on a clean client |
| VPN | Test host has `music-vpn` Gluetun running/healthy; download containers share its namespace | Observe updated NOW widget on actual client; no exit-IP verification |
| Host installer | Design issues and local helper contract exist | Fresh-host installer not implemented |
| NOW-owned identity | Device approval requirement documented | Authentication service and emailed approval not implemented |

Do not call a code path fully verified because CI passed. The next milestone is [Beta 1 acceptance](BETA-ACCEPTANCE.md). The [six-item engineering work order](PRODUCT.md#beta-1-engineering-execution-plan) is planning only: configuration extraction in `main` is implemented, but the Wolf pending-client parser and asynchronous request transport have **source implementations and CI tests only**. Nonblocking UI behavior is not yet device-tested; Tailscale discovery, other module extractions and sanitizer diagnostics remain pending.

## Tracked roadmap

- [#76](https://github.com/SteezyMode/OptiplexNow/issues/76): private Beta 1 end-to-end gate.
- [#94](https://github.com/SteezyMode/OptiplexNow/issues/94): existing NOW credentials plus email approval for a new device.
- [#98](https://github.com/SteezyMode/OptiplexNow/issues/98): standardized, reproducible NOW Host installer.
- [#85](https://github.com/SteezyMode/OptiplexNow/issues/85): Headscale, low-end client performance, Wolf API/fork investigation.

The client requires an existing, separately configured server. OptiPlex Studio is a separate project. Detailed scope is in [Product direction](PRODUCT.md).
