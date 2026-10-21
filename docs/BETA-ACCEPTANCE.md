# Beta 1 acceptance

Status: test plan. An unchecked item is **not** validated by GitHub CI.

## Scope

Private Linux client beta against an **existing, owner-approved host**. Four preapproved Tailscale testers are the initial model. The beta distributes an amd64 Debian package; it does not install Wolf, Docker, Jellyfin, Gluetun, Tailscale accounts, or an OptiPlex account service on a new host.

## Graphical Tailscale setup acceptance

- [ ] On a fresh supported Debian/Ubuntu-family Linux desktop without Tailscale: select Install Tailscale, approve the system authentication dialog, verify upstream signed repository/package installation, and sign in using the browser. No terminal appears.
- [ ] On a client with Tailscale already installed and connected: use Connect without reinstalling, changing any network settings or requesting root access.
- [ ] Decline authorization, disconnect the network, and test unsupported OS/repository conflicts. NOW must show a clear non-technical failure, preserve existing package sources, and leave the user a way to retry or open official help.
- [ ] Do not infer that Tailscale membership grants server or Wolf permission. Existing trusted SSH/pairing and media login remain independent.

## Pre-release validation path

For **unreleased changes on main**, a PR's passing `Validate OptiPlex NOW` workflow can provide a short-lived **unreleased PR test installer** under that run's Artifacts section. The packaged Debian version is `CURRENT_VERSION+prNUMBER.RUN`, distinct from any immutable tagged version. These packages expire after seven days and are **not official releases or general-user installers**.

Download the artifact ZIP from a successful PR run while signed into GitHub, extract the .deb and SHA256SUMS, and verify its checksum before installing on a spare test client. Installation and streaming observations apply only to that exact PR commit/build. Do not promote a PR artifact as a Beta 1 accepted release.

After the code lands on main, a tagged closed-beta prerelease may be published specifically for device acceptance tests. This is not evidence of completed Beta 1 acceptance. Use the documented version bump and tag-only release process. Protect existing saved NOW and Moonlight identity; never delete either to manufacture a clean client.

## Simulated cross-process onboarding test

CI also runs `tests/test_onboarding_flow.py`, which executes the **real** Tailscale status/discovery scripts, SSH authorization bridge, Wolf SSH client and Wolf host helper as separate subprocesses. Only the external Tailscale CLI, SSH/ssh-copy-id and Docker API endpoints are simulated using executable stand-ins in an automatically deleted home directory. It covers signed-out/connected transitions, host selection, SSH key creation/reuse, pending/paired Wolf state, refusal, stale selection, unavailable SSH and recovery.

This is protocol integration evidence, **not** proof of the GTK wizard, PolicyKit, actual fingerprint/password prompts, live Tailscale enrollment or video/audio/controller streaming. The full real-device checklist below remains unchanged.

## Required end-to-end test

Use a Linux client with no prior NOW configuration or Wolf pairing. Preserve the existing known-good client for regression testing.

- [ ] Download the exact versioned closed-beta .deb and SHA256SUMS from its tagged GitHub prerelease (not the `releases/latest` stable link). Verify package metadata and checksum.
- [ ] Install through the normal supported desktop/software flow. Launch NOW without a terminal.
- [ ] Complete setup on the supported distribution and resolution. The client detects an existing Tailscale login or provides a clear sign-in path.
- [ ] Discover the intended authorized host, exclude the current device, and confirm address and identity. Wrong or offline hosts show actionable errors. Mock tests must cover signed-out/missing Tailscale, invalid status JSON, duplicate peers, malformed discovery rows, process cancellation and wizard closure; none of these alone proves real enrollment.
- [ ] Complete trusted SSH authorization where needed, without exposing long-term keys or bypassing host-key verification. Background status checks must not silently add a new host key; an unfamiliar or changed host key must require explicit owner investigation. Confirm the native host fingerprint/password dialogs, wrong password, declined fingerprint, cancellation, timeout, and successful reconnect without terminal or repeated password prompts. Verify host keys are never silently accepted.
- [ ] On a clean client without Moonlight, select Install Moonlight, confirm the Flathub per-user installation, and complete it entirely through NOW without a terminal. Test cancellation, offline failure and retry; check the AppImage fallback when Flatpak is missing.
- [ ] From **Connect to Game Host**, pair a **genuinely unpaired** Moonlight client with Wolf. Verify that a wrong or stale request cannot authorize a different client.
- [ ] Open Games, launch Steam, and confirm *actual video, input, and audio*, not just a container state or process spawn.
- [ ] Disconnect and reconnect. No PIN dialog for an already-paired device.
- [ ] Confirm a truly clean generic client has no maintainer domain, default SSH username, or assumed music/download endpoint. Enter the test media URL explicitly or import a trusted preset.
- [ ] Configure a Web Gaming URL if that optional browser feature is in scope; confirm Web Gaming settings and Steam launch use that URL rather than an embedded owner domain.
- [ ] Open Videos at the configured URL and reach the actual media login or library.
- [ ] Restart the app and then upgrade the package. Verify settings, user URLs, device pairing, and shortcuts survive.
- [ ] Show accurate disconnected/offline and recovered states without blocking the GTK interface. During Wolf pending-request refresh, authorization and Tailscale/server discovery, exercise a deliberately slow or unreachable endpoint; confirm the interface remains responsive and cancellation or closing a dialog cannot later update a destroyed widget.
- [ ] Reject a changed, expired, or ambiguously selected pending Moonlight request. A late worker response must not authorize a different device or create duplicate pairing attempts.
- [ ] Repeat on a low-resolution or older Linux client. Check tray behavior, scrolling, settings layout, and stream responsiveness. CI additionally boots disposable profiles at 1024×768 and 3440×1440 to check dashboard window bounds, but this does not establish user-device usability or first-time network enrollment.

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
