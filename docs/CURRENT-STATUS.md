# Current implementation and verification

Updated: 2026-10-21 JST. GitHub Releases and CI are the authority for new publication events.

## Release state

- **Published closed beta installer:** [v1.16.1](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.16.1). The tag points to `e6df6d06206b359bd4c219bf6c7e4f06db7de2d6`. The tag-triggered **Publish OptiPlex NOW** workflow completed successfully (run `39475111081`).
- **Official assets:** `OptiPlex-Now_1.16.1_amd64.deb`, `OptiPlex-Now_amd64.deb`, and `SHA256SUMS`.
- **Included fixes:** [#96](https://github.com/SteezyMode/OptiplexNow/pull/96) colors connected Tailscale and positive Wolf desktop states; [#97](https://github.com/SteezyMode/OptiplexNow/pull/97) detects the Gluetun image under a custom container name.
- **Acceptance:** The artifact is published for **private closed beta testing**, but a clean-client install, first-time pairing and actual stream have not yet completed the Beta 1 checklist.

Release publishing changes GitHub artifacts only. It does not modify the running reference server or upgrade installed clients.

## Included in current `main`

- Native GTK3 client, primary actions, tray controls, Settings and setup wizard. The source now sizes its dashboard using the usable monitor dimensions, rather than the former fixed 660×350 start window; a separate disposable-profile Xvfb layout test checks 1024×768 and 3440×1440 after installed-package build. The change is not included in v1.16.1.
- Tailscale connectivity and server discovery, SSH/SFTP access and host hardware dashboard. In current development source, wizard Tailscale status checks and peer discovery run as cancellable background jobs through `tailscale_async.c/.h`. Parsed connected/signed-out/offline/missing states and strict discovery validation have native/Python tests; real account enrollment remains manual and unverified on a fresh client.
- Moonlight streaming launch for configured Wolf apps, native Wolf pairing dialog, and generated four-digit pairing PIN transported through a dedicated helper.
- Browser launch for configured video, music, and download services.
- Power operations and explicit global Wolf restart with confirmation.
- Portable connection presets and encrypted client backups.
- Read-only VPN status lookup by Gluetun Docker image, not container name. Tailscale and running Wolf desktop indicators use active-state coloring.
- Optional reference-host-specific maintenance helpers. These are not a server installer.

## Portable defaults (development source, not v1.16.1)

New source changes after the v1.16.1 tag remove the reference-host video and Web Gaming domain defaults, the reference SSH username, and automatically guessed optional service ports. Web Gaming and Downloads use user-configured URLs. Previously saved client URLs stay unchanged, but existing users must configure a Web Gaming URL after installing a future release because the old fixed domain was never saved to their config. **The published v1.16.1 installer is unchanged and still has the historical household defaults.** Verify the new code through CI and a clean-client test before making a new release.

## Isolated fresh-profile GUI simulation (not device acceptance)

On October 21, 2026, the **unreleased PR #108** package `1.16.1+pr108.250` passed GitHub CI, including installation and GUI smoke checks. Its downloaded .deb passed the packaged SHA256SUMS verification. The binary was also launched in independent Debian 13 Xvfb/DBus sessions with empty HOME and XDG configuration at **3440×1440** and **1024×768**.

- First-run setup appeared without crashing and correctly showed Tailscale as not installed in the disposable environment.
- Initial dashboard window geometry was **1100×720** at 3440×1440 and **928×648** at 1024×768, compared with the previous 660×350 at both resolutions.
- With an isolated non-first-run config fixture, all four server power controls were visible without scrolling at 1024×768.
- Empty-profile startup did **not** create a `config.ini` or replace the owner's existing settings.

This confirms startup, packaging, and synthetic layout behavior only. It does **not** prove a new physical Linux install, Tailscale sign-in, trusted SSH enrollment, Wolf pairing or actual video/audio/input. Those Beta 1 checklist items remain open.

## Graphical Tailscale onboarding (development source, not v1.16.1)

The current source now offers an opt-in **Install Tailscale** action for validated Debian/Ubuntu amd64 clients and Pop!_OS/Linux Mint systems that declare a matching Ubuntu base. Installation uses a desktop PolicyKit password prompt, a finite distro allowlist and Tailscale's official signed apt repository. It does not execute a remotely downloaded shell script. Existing Tailscale installations are never reinstalled or reconfigured. The client opens the Tailscale device-local browser UI for sign-in rather than launching a terminal. Unsupported Linux releases are directed to upstream instructions.

This flow has mocked installer/packaging tests but has **not** yet been installed using PolicyKit and authenticated on a fresh physical computer. Installation may require a working desktop PolicyKit authentication agent and network access. System-wide Tailscale installation is a separate, explicitly approved operation and is not run by launching NOW.

## Graphical SSH authorization (development source)

The current development client replaces the former first-time `ssh-copy-id` terminal with a native GTK authorizing dialog and a separate graphical SSH password/fingerprint prompt. The bridge is asynchronous, bounded and cancellable; the helper uses only a selected host, SSH username and OpenSSH's standard public-key enrollment procedure. The user must approve the correct host fingerprint and enter an authorized account password when needed. CI mocks do not prove successful enrollment on a real server. No host SSH daemon or `authorized_keys` file is changed merely by upgrading NOW.

This removes a **normal first-run terminal requirement** but does not grant preapproved Tailscale users automatic host SSH access. Future host enrollment must use an owner-controlled, least-privilege broker.

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
