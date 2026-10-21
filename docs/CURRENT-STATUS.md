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

## Native-code diagnostics (development CI)

An independent `native-sanitizers` CI job tests the extracted C modules under AddressSanitizer (memory access) and UndefinedBehaviorSanitizer, with stricter warnings on the graphical SSH/Tailscale helper modules. It runs on disposable GitHub runners, does not need the streaming host, and **does not modify the packaged binary, users' systems, or release compiler flags**. GLib/GIO process-global leak detection is disabled for these runs; memory bounds and undefined-behavior checking remain enabled. The still-large legacy GTK `main.c` is not covered by this isolated instrumented test target, and real end-to-end device validation remains required.

## Host monitoring refactor (development source)

The host telemetry parser now has a GTK-independent C module with compiled tests for key-value extraction, disk-section boundaries, excluded recovery/boot mounts, missing sections and malformed fields. The dashboard also shares the wizard's structured Tailscale status helper. Background SSH monitoring and power actions no longer use `StrictHostKeyChecking=accept-new`; they require a trusted host key, which must be established through explicit authorization. These are source/CI checks only: real host power management and status must still be regression-tested, and the shipped v1.16.1 package is unchanged.

## Immutable background host targets (development source)

Remote hardware inventory, Wolf PIN-link lookup, wake, suspend, reboot and poweroff jobs now snapshot the selected SSH host and account before leaving the GTK thread. Relay wake also snapshots its configured command. Background workers no longer read live `cfg[]` settings, so changing Settings cannot silently redirect an already requested remote operation. Results for an endpoint no longer selected are ignored instead of being displayed as the status of the new host. A separate GTK-free contract tests snapshot isolation, changed settings and bounded fields; regular CI and the native sanitizer job compile it. This has not yet been verified against two real hosts, and a command already sent to the originally selected host cannot be recalled by switching Settings.

## Asynchronous encrypted backup UI (development source)

Full encrypted client-identity export and restore now invoke the existing v1 `optiplex-now-backup` helper through a separate `src/backup_async.c/.h` GIO subprocess bridge. The password is supplied on stdin only, carried by a short-lived explicitly wiped buffer, never embedded in arguments or environment. A modal progress dialog keeps the GTK event loop responsive while ensuring that users cannot accidentally start an overlapping backup or restore. Unlike independent installer downloads, restore cannot safely support forced cancellation: the unchanged helper replaces several SSH/Moonlight/configuration files and interruption may leave partial state. The interface waits for completion rather than presenting an unsafe Stop control. An isolated fake-helper test covers both operations, invalid paths, missing executable, nonzero exit codes, password isolation and main-context responsiveness; native ASan/UBSan and package CI run it.

This change does not alter the v1 encrypted archive format, identity handling, stored paths, source host, or the published v1.16.1 release. Real export/restore with a trusted spare device, invalid password and power interruption still require device-level acceptance. The helper itself is not an all-or-nothing transactional restore.

## Tray modularization (development source)

Tray selection masks, saved action order, Desktop caption preferences and service labels are now parsed and persisted by `src/tray_prefs.c/.h` instead of `main.c`. The existing tray UI and AppIndicator/GTK fallback remain in the GTK controller. Compiled tests cover malformed order files, duplicate indices, mask fallbacks, the existing XDG order-file path and legacy Desktop caption path, atomic permissions-restricted saves, and generated service labels. This is an incremental architecture improvement, **not** a full tray rewrite, and the physical tray/minimize/restore experience is not yet acceptance-tested on a new desktop.

## Tray action dispatch (development source)

The GTK tray controller now delegates action-ID interpretation to a GTK-free `tray_actions.c/.h` dispatcher with explicit host-UI callback hooks. The ordered behaviors are preserved: opening NOW before Settings/System Info, displaying NOW before launching Games when Moonlight is unavailable, and direct restart/quit commands. Unknown or stale action IDs are ignored rather than passed to a service launcher. Native and sanitizer behavior tests exercise all eight service IDs, five utility IDs, missing callbacks and invalid IDs. GTK/AppIndicator creation and icon/minimize/restore logic remain in the controller; this is not full tray extraction. Real desktop regression is still pending.

## Cross-process onboarding simulation (development CI)

The Beta 1 regression suite now drives actual Tailscale discovery, SSH enrollment and both Wolf pairing helper processes together through synthetic command-line endpoints. The temporary fixture verifies first-run identity creation and reuse, selected-host and pairing identity behavior, reconnection and negative-path recovery without touching any real host, tailnet or user profile. Only the external command implementations are simulated. See `tests/test_onboarding_flow.py` and `tests/fixtures/onboarding_mock_cli.py`.

This test does not interact with GTK, verify true system authentication prompts, enroll a real Tailscale account or stream a game. Those still require a supported physical client. The host installation and device-approval backend remain future milestones.

## Terminal-free Moonlight installation (development source)

Moonlight installation previously launched a shell and terminal for `flatpak remote-add` followed by `flatpak install`. NOW now asks for explicit confirmation and runs the two fixed commands asynchronously as **per-user** Flatpak operations through `moonlight_install.c/.h`, reporting failure, completion, timeouts and cancellation in a GTK dialog. No sudo, administrator password, account system or host operation is introduced. Missing Flatpak directs the user to install it or choose a Moonlight AppImage; it does not silently invoke a terminal.

The native test uses a disposable fake Flatpak binary to prove argument ordering, failure handling, cancellation and main-context responsiveness. This does **not** prove live Flathub download, desktop integration, hardware decoding or game streaming. Real-client Beta 1 acceptance remains pending.

## GTK wizard network lifecycle extraction (development source)

The setup wizard's status and peer-discovery jobs, timeouts and cancellation now belong to `src/wizard_network.c/.h`. The GTK layer only launches requests and displays the results. Closing the wizard disables its callback before any outstanding work is cancelled; worker-held references keep the request manager alive until completion without retaining destroyed GTK widgets. A late discovery response no longer opens a chooser after the user navigates away from the Server page, and a second wizard cannot be opened over an active one.

Native and ASan/UBSan tests exercise duplicate submissions, concurrent slow/fast operations, timeout, successful retry, closing during an active operation and closing from inside a callback. The actual GTK wizard's page-navigation, authorization and video streaming still require device-level Beta 1 acceptance. Current official v1.16.1 package does not contain this code.

## Wizard service availability checks (development source)

The setup wizard's Videos/Music/Downloads URL checks now use `src/service_probe.c/.h`, a GTK-free cancellable GTask component using fixed curl arguments. The GTK wizard owns its labels and the specific URLs being checked; there are no global service labels or shared service-check thread state. Closing the wizard disconnects callbacks and cancels pending subprocesses. A URL edited after a check begins is shown as changed, not incorrectly reported healthy from an old result. HTTP 2xx through 4xx counts as responding (server reachable, not necessarily healthy or authenticated); missing entries remain NOT SET UP. The ordinary HTTP probe no longer uses shell expansion.

Native tests and sanitizers simulate responding/refused/HTTP-error endpoints, malformed URLs, duplicate requests, timeouts, successful retry and close-during-request. This is simulated evidence, not physical Beta 1 login or service verification.

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

CI passing is not device acceptance. The six-item [engineering progress register](PRODUCT.md#six-item-progress-register) tracks implemented config, Wolf, Tailscale, SSH, monitoring, tray and sanitizer improvements separately from physical verification. The current source has substantial modularization, but GTK `main.c` still contains tightly coupled state and UI actions. The next release gate is the [Beta 1 end-to-end checklist](BETA-ACCEPTANCE.md): graphical Tailscale sign-in, trusted SSH enrollment, initial Wolf pairing, Games/Videos and repeat reconnect on an actual fresh client. None of those outcomes may be inferred solely from simulation or CI.

## Tracked roadmap

- [#76](https://github.com/SteezyMode/OptiplexNow/issues/76): private Beta 1 end-to-end gate.
- [#94](https://github.com/SteezyMode/OptiplexNow/issues/94): existing NOW credentials plus email approval for a new device.
- [#98](https://github.com/SteezyMode/OptiplexNow/issues/98): standardized, reproducible NOW Host installer.
- [#85](https://github.com/SteezyMode/OptiplexNow/issues/85): Headscale, low-end client performance, Wolf API/fork investigation.

The client requires an existing, separately configured server. OptiPlex Studio is a separate project. Detailed scope is in [Product direction](PRODUCT.md).
