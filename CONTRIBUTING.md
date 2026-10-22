# Contributing to OptiPlex NOW

Read [Product direction](docs/PRODUCT.md), [Current status](docs/CURRENT-STATUS.md), [Engineering trail](docs/ENGINEERING-TRAIL.md) and [Beta acceptance](docs/BETA-ACCEPTANCE.md) before proposing new scope.

**Mandatory iteration handoff:** Every behavior-changing PR includes evidence, design and rejected alternatives, exact tests (mock/CI/physical distinguished), unsafe boundaries, rollback, and the next executable acceptance step. Append a dated entry or update its existing iteration entry in `docs/ENGINEERING-TRAIL.md`; update `docs/CURRENT-STATUS.md` only when an implementation/evidence claim changes. The PR template is the review checklist, and #154 is the running Steam continuity issue. No undocumented live-host adjustments. Never imply a passing CI test means the reference machine was physically tested.

Published v1.17.0 is an amd64 GTK3 Linux client for an already prepared server. Unreleased development source additionally includes a **clean-host Wolf installation pilot** with separate GTK setup and a root-authorized helper, not yet physically accepted. NOW does not own Wolf's protocol, Jellyfin's service, Tailscale's network or Studio's tools. Keep privileged host operations outside the ordinary client; see [Host installer](docs/HOST-INSTALLER.md).

## Source map

| Path | Responsibility |
| --- | --- |
| `src/main.c` | GTK3 UI, wizard, launcher, tray, state presentation and user-triggered actions |
| `src/host_setup.c` | Separate Server Setup GUI; read-only host review and explicit opt-in clean-host install confirmation |
| `src/config.c/.h` | Persisted client configuration, defaults, legacy key migration and atomic saves |
| `src/host_metrics.c/.h` | Host telemetry key-value/disk parsing and mounted-drive filtering, independent of GTK/SSH |
| `src/tray_prefs.c/.h` | GTK-free tray order, shortcut masks, legacy Desktop caption, action labels and private atomic persistence |
| `src/tray_actions.c/.h` | GTK-free explicit tray action routing and callback contract; validates IDs and launch order |
| `src/wolf_pairing.c/.h` | GTK-independent pending-client validation and PIN request generation; no SSH privilege or remote approval |
| `src/wolf_transport.c/.h` | Asynchronous worker-backed GIO request transport for the existing Python SSH bridge; no GTK widgets or Docker access |
| `src/tailscale_async.c/.h` | Cancellable background Tailscale helper invocation and strict discovery parsing; no GTK widgets or network configuration |
| `src/wizard_network.c/.h` | GTK-free orchestration of two independent setup requests, duplicate suppression, timeouts, cancellation and shutdown |
| `src/wizard_services.c/.h` | GTK-free independent validation and application of entered Videos/Music/Downloads URLs |
| `src/service_probe.c/.h` | GTK-free asynchronous HTTP availability checks with cancellation, timeout, bounded results and verified URLs |
| `src/tailscale-status.py` | Read-only Tailscale JSON status normalization for wizard; never performs sign-in or enrollment |
| `src/tailscale_install.c/.h` | Unprivileged GTK-independent GIO wrapper invoking PolicyKit to request a specific root installation operation |
| `src/tailscale-install.py` | Opt-in signed upstream apt repository installer with a finite Debian/Ubuntu release allowlist; never invoked on an existing Tailscale installation |
| `src/ssh_authorize.c/.h` | Async, cancellable GUI SSH key authorization caller; GTK widgets belong to the caller, not the worker |
| `src/ssh-authorize.py` | Restricted OpenSSH key-generation and ssh-copy-id orchestration; process group cleanup and bounded timeouts |
| `src/ssh_askpass.c` | Separate, GTK-only host fingerprint confirmation and masked SSH password/passphrase prompt, invoked by OpenSSH |
| `src/moonlight_install.c/.h` | Cancellable per-user Flatpak installation of Moonlight; fixed command arguments; no terminal or network dependency in tests |
| `src/process.c/.h` | Subprocess execution and executable lookup |
| `src/presets.c/.h` | Non-secret connection preset parsing and legacy compatibility |
| `src/backup.c` | Explicit encrypted client identity/settings backup |
| `src/find-servers.py` | Peer discovery |
| `src/wolf-pair-client.py` | SSH-mediated client pairing requests |
| `src/wolf-pair-local.py` | Privileged host-side Wolf socket mediation; not auto-installed on the host |
| `src/owner_access.py` | Host-local owner/device/workspace policy: strict grant resolution, private atomic state; no Wolf session launcher |
| `src/owner_lobby.py` | Pure, offline Wolf named-profile Steam lobby request planner; does not call Wolf or bypass upstream access checks |
| `src/owner-access-local.py` | Developer-only root/admin enrollment CLI; no NOW client integration or host deployment yet |
| `src/server-profile.py` | Existing music stack export/staged import; not a host installer |
| `src/open-remote-files.sh`, `src/open-web-gaming-admin.py` | SFTP and opt-in browser administration |
| `server/host_install.py`, `server/host_nvidia.py`, `server/nvidia-driver.Dockerfile` | Guarded Wolf clean-host install and version-specific NVIDIA driver userspace volume; unverified on physical host |
| `src/restart-streaming.sh`, other `server/` tools | Existing-host maintenance and review-only prototypes; do not treat their simulations as live deployment |
| `Makefile`, `package.py`, `assets/` | Build, pinned embedded fonts, package manifest and icons |
| `tests/`, `.github/workflows/` | Regression tests, CI and immutable release publishing |

`src/main.c` is still a large GTK controller, with shared indexed settings and some synchronous advanced host operations. Core Wolf, Tailscale and SSH onboarding calls have been moved to asynchronous helpers; other UI and status responsibilities remain coupled. New modules should keep GTK widgets and remote I/O out of parsing/persistence code. Split one responsibility at a time with behavioral tests; do not replace the GUI or mix a large formatting-only diff with a functional change.

A shared `.clang-format` defines four-space C indentation and a 100-column target. Format newly extracted or edited functions, not the entire legacy `main.c` in unrelated PRs. Preserve the existing serialized config index order, file path and legacy preset inputs.

The active [six-item Beta 1 engineering register](docs/PRODUCT.md#six-item-progress-register) is applied within existing product milestones. Continue extracting one narrow responsibility per PR and put behavior tests next to the owning module. Any worker result must return to the GTK main context, respect cancellation and dialog lifetime, and be checked against the intended client identity. Keep formatting-only changes out of behavioral PRs. Sanitizers belong to a separately tested diagnostic target, not a surprise change to release build flags.

## Onboarding protocol integration tests

The offline `tests/test_onboarding_flow.py` checks the real Tailscale, SSH and Wolf **helper chain** with external service executables replaced by stand-ins. Run `python3 -m unittest discover -s tests -p 'test_onboarding_flow.py' -v`. It needs Python 3 and `ssh-keygen` from OpenSSH, but does not need a Tailscale account, Docker, a host or privileges. Every fake executable is confined to an automatically deleted test directory.

This does not automate the GTK setup wizard or authenticate a real server. CI GUI/package tests and the physical Beta 1 acceptance plan are separate requirements. Never reuse the fake commands outside this disposable test.

## Local build

Target tested CI environment: Ubuntu 24.04 amd64 with GCC, make, binutils, Python 3, GTK3/fontconfig headers, OpenSSL headers, curl, Pillow and Xvfb/test GUI dependencies. A clean build downloads two fonts from pinned upstream revisions with integrity and size verification.

```sh
make check-process check-presets check-config check-wolf-pairing check-wolf-transport check-tailscale
make check-host-metrics check-tray-prefs check-tray-actions check-moonlight-install check-wizard-network check-wizard-services check-service-probe
make check-sanitizers  # ASan + UBSan, separate binaries; no release flag changes
python3 -m unittest discover -s tests -v
make package
```

The resulting `.deb` is under `dist/`. Inspect the actual version in `package.py` before using its versioned filename. Do not commit binary installers or private backups.

## Pull request requirements

1. State one user-visible behavior or architectural contract, including its issue and non-goals.
2. State exact affected client files and any host-side effects. For server operations describe permissions, data retention, downtime and rollback.
3. Preserve compatibility: `~/.config/optiplex-desk/config.ini`, `optiplex-now` and the `optiplex-desk` alias, existing shortcut masks, `.onp` non-secret presets and `.onb` encrypted backups.
4. Avoid hardcoded reference-host assumptions. Use configured hosts, managed service identifiers or explicit compatibility fallbacks.
5. Add executable behavioral tests where feasible; source-string assertions alone are insufficient for security, SSH and streaming correctness.
6. Run build/tests and record the results. Mark real-client and live-host checks **not run** unless observed.
7. Never silently stop Wolf sessions, restart the owner's services, expose Docker/Wolf admin sockets, bypass SSH host verification or paste credentials into committed files.
8. Update authoritative documentation in the same PR if user behavior, service contracts, acceptance, or product boundaries change.

Only new `vX.Y.Z` tags trigger releases. Read [Release process](docs/RELEASE-PROCESS.md); CI success is not a declaration that a stream worked. Do not overwrite existing tags/assets.

## Review standard

Prefer fewer dependencies, narrow privileges, predictable failure modes and short operator instructions. Always distinguish planned, implemented, CI tested, host observed and fresh-device accepted. Long-term experiments, including Headscale and Wolf forks, require a recorded problem and an independent spike before inclusion in the default installer.

No application-code license has been chosen yet. Do not assume public visibility confers permission to reuse or commercially distribute code. Preserve third-party license and attribution material.
