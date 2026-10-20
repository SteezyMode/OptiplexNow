# Beta 1 acceptance

Status: test plan. An unchecked item is **not** validated by GitHub CI.

## Scope

Private Linux client beta against an **existing, owner-approved host**. Four preapproved Tailscale testers are the initial model. The beta distributes an amd64 Debian package; it does not install Wolf, Docker, Jellyfin, Gluetun, Tailscale accounts, or an OptiPlex account service on a new host.

## Required end-to-end test

Use a Linux client with no prior NOW configuration or Wolf pairing. Preserve the existing known-good client for regression testing.

- [ ] Download the latest tagged .deb and SHA256SUMS from GitHub Releases. Verify package metadata and checksum.
- [ ] Install through the normal supported desktop/software flow. Launch NOW without a terminal.
- [ ] Complete setup on the supported distribution and resolution. The client detects an existing Tailscale login or provides a clear sign-in path.
- [ ] Discover the intended authorized host, exclude the current device, and confirm address and identity. Wrong or offline hosts show actionable errors.
- [ ] Complete trusted SSH authorization where needed, without exposing long-term keys or bypassing host-key verification.
- [ ] From **Connect to Game Host**, pair a **genuinely unpaired** Moonlight client with Wolf. Verify that a wrong or stale request cannot authorize a different client.
- [ ] Open Games, launch Steam, and confirm *actual video, input, and audio*, not just a container state or process spawn.
- [ ] Disconnect and reconnect. No PIN dialog for an already-paired device.
- [ ] Open Videos at the configured URL and reach the actual media login or library.
- [ ] Restart the app and then upgrade the package. Verify settings, user URLs, device pairing, and shortcuts survive.
- [ ] Show accurate disconnected/offline and recovered states without blocking the GTK interface.
- [ ] Repeat on a low-resolution or older Linux client. Check tray behavior, scrolling, settings layout, and stream responsiveness.

Record OS, package version, host version, results, and any manual intervention. A single owner-led test does not replace an independent tester session.

## Verification levels

| Level | Meaning |
| --- | --- |
| Code present | Implementation exists on `main` |
| CI passed | Compiles, unit/integration stubs and package/GUI smoke tests passed in runner conditions |
| Device tested | User observed the specific flow on a named supported machine |
| Fresh-client tested | No stored pairing or NOW configuration on that client |
| Beta accepted | Entire flow completed with documented failures and recovery on representative hardware |

Never infer a later level from an earlier one.

## Not a Beta 1 gate

NOW account sign-in, emailed new-device approval, Headscale, turnkey host installation, Jellyfin single sign-on, per-session Wolf termination, persistent private multi-user desktops, guaranteed cross-network performance, Windows/macOS clients, or commercial readiness.

## Release and feedback discipline

The official release is a versioned, immutable GitHub asset built from a matching `vX.Y.Z` tag. Record accepted package SHA256 and the corresponding source commit. Fix regressions on `main`, then publish a new version. Do not replace a published tag or .deb.

See [Current status](CURRENT-STATUS.md), [Release process](RELEASE-PROCESS.md), and [Host pairing contract](WOLF-PAIRING-HOST-CONTRACT.md).
