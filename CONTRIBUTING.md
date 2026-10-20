# Contributing to OptiPlex NOW

## Read this first (2 minutes)

**NOW is a native GTK Linux launcher/manager for an existing remote host.** It starts Moonlight streams to Wolf apps, opens configured media/download services, and provides controlled SSH/SFTP and power/status features. **It is not a streaming engine, not OptiPlex Studio, and does not currently install a new server.** [Current verified status](docs/CURRENT-STATUS.md).

**The next product direction** is a guided **host installer/manager** with persistent, independently owned Wolf desktops. This is a proposal, not current code. Start with [upstream-first architecture](docs/UPSTREAM-FIRST-WOLF-INTEGRATION.md) and [multi-user authorization gates](docs/MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md) before designing it. No direct Docker socket or privileged Wolf API exposure to clients.

## Code map

| Location | Responsibility |
| --- | --- |
| \`src/main.c\` | Current GTK UI, settings and host/streaming controls. **Large legacy module to split incrementally**, not rewrite wholesale. |
| \`src/process.c/.h\` | Executable discovery, bounded command execution, detached launches. No GTK dependency. |
| \`src/presets.c/.h\` | Portable .onp validation/import/export; legacy header compatibility. No GTK dependency. |
| \`src/backup.c\` | Encrypted trusted-device backup helper (separate binary). |
| \`src/find-servers.py\` | Tailscale/server discovery helper. |
| \`src/open-remote-files.sh\` | Remote file access. |
| \`src/open-web-gaming-admin.py\` | SSH-mediated administrative browser path. |
| \`src/restart-streaming.sh\`, \`server/wolf-driver-maintenance.py\` | Explicit opt-in host operations, not automatic client setup. |
| \`src/server-profile.py\` | Existing music stack profile export and staged import—not a service installer. |
| \`package.py\`, \`Makefile\`, \`assets/\` | Build, package manifest, desktop integration/artwork. |
| \`tests/\`, \`.github/workflows/\` | Regression checks and strictly separated validation/publication. |

**Boundary:** NOW owns client UI, configuration, onboarding and (eventually) host orchestration. Wolf owns streaming/sessions, Moonlight is a client, Studio owns creative projects and Codex. Don't merge these responsibilities just because the reference machine runs them all.

The experimental opt-in NOW Host discovery helper and client peer picker are documented in [now-host-discovery](docs/now-host-discovery.md). They are not an installer, authentication replacement, or implemented pairing flow. Do not start the agent on the production OptiPlex.

## Build/test on a disposable development machine

Target: amd64 Ubuntu/Pop!_OS 24.04 (other distributions unverified). Install the build requirements in [README](README.md), including GCC, make, binutils, Python, libssl-dev, Pillow and font-download prerequisites.

Run in the repository root:

\`\`\`sh
make check-process check-presets
python3 -m unittest discover -s tests -v
make package
dpkg-deb -f dist/OptiPlex-Now_1.14.0_amd64.deb Package Version Architecture
\`\`\`

Build downloads font sources from a pinned Google Fonts commit and verifies their exact upstream Git blob IDs and sizes; a network connection is needed for a clean build. To intentionally upgrade fonts, review the new upstream commit and update `FONT_REV`, both blob IDs and both byte counts in `Makefile` together. The atomic download recipe refuses partial or altered fonts. A passing build is **not** proof of working Wolf playback, pairing, GTK tray behavior or fresh installation. Do not execute host-maintenance helpers as part of testing. Never use the primary OptiPlex as a throwaway test host.

## Safe PR workflow

1. Open an issue or describe one focused change. Cite the user behavior it fixes. Separate **verified**, **proposed**, and **untested** claims.
2. Branch from \`main\`. Keep the changes narrow. Do not directly edit live host services, projects or user configuration.
3. For a refactor, preserve input/output, UI labels, config paths and backwards compatibility. Add behavioral tests where practical; text-only source assertions are insufficient by themselves.
4. Run the commands above and include the outcome in the PR. For UI/streaming changes, also enumerate *manual* on-device checks needed before a release.
5. Use the PR description to document scope, tests, risk, rollback, and whether anything touches Wolf, Docker, VPN, SSH, browser authentication or user data.
6. Do not declare completion until tests pass and the user-visible flow has been observed on the relevant device. Never auto-restart/recreate existing Wolf sessions or change services to pass a client test.

## Release and compatibility rules

Only \`.github/workflows/ci.yml\` (read-only main/PR checks) and \`release.yml\` (new version tags only) are active. The old 1.12/1.13 branch publisher workflows were retired. Changing this requires a deliberate security/release review and updates to \`tests/test_repo_contract.py\`. Follow [release process](docs/RELEASE-PROCESS.md): **no existing tag or artifact overwrite**.

Retain current \`optiplex-now\` / \`optiplex-desk\` compatibility and \`~/.config/optiplex-desk/config.ini\` until a tested migration exists. Keep existing .onp headers importable and .onb backups recoverable. A public brand name has not been selected; treat display names, Debian package IDs, config paths, GTK identifiers, Moonlight shortcuts and exported file headers as separate compatibility layers. Build explicit old-to-new migration and rollback tests rather than bulk renaming identifiers.

**Licensing is not resolved:** there is no selected application-code license yet. Do not assume public visibility automatically grants redistribution rights; choose an explicit license/contribution policy before outside distribution or accepting substantial third-party contributions.

## Good first areas

- Split config parsing from GTK without changing existing upgrade behavior; add real round-trip tests.
- Identify/remove obsolete hardcoded assumptions; retain working network endpoints and backward compatibility.
- Improve clean-host preflight diagnostics **in an isolated test environment**.
- Add tests around timeouts, resource cleanup, malformed settings and failed connections.

Do **not** start by forking Wolf, redesigning the UI, or implementing multi-user auth as a hidden NOW button. The actual authorization must be enforced on the native Moonlight streaming path.
