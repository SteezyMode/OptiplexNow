# Contributing to OptiPlex NOW

Read [Product direction](docs/PRODUCT.md), [Current status](docs/CURRENT-STATUS.md) and [Beta acceptance](docs/BETA-ACCEPTANCE.md) before proposing new scope.

NOW is currently an amd64 GTK3 Linux client for an already prepared server. It does not own Wolf's streaming protocol, Jellyfin's media service, Tailscale's network or Studio's creation features. The future host manager must remain separately installable.

## Source map

| Path | Responsibility |
| --- | --- |
| `src/main.c` | GTK3 UI, wizard, launcher, tray, state presentation and user-triggered actions |
| `src/config.c/.h` | Persisted client configuration, defaults, legacy key migration and atomic saves |
| `src/process.c/.h` | Subprocess execution and executable lookup |
| `src/presets.c/.h` | Non-secret connection preset parsing and legacy compatibility |
| `src/backup.c` | Explicit encrypted client identity/settings backup |
| `src/find-servers.py` | Peer discovery |
| `src/wolf-pair-client.py` | SSH-mediated client pairing requests |
| `src/wolf-pair-local.py` | Privileged host-side Wolf socket mediation; not auto-installed on the host |
| `src/server-profile.py` | Existing music stack export/staged import; not a host installer |
| `src/open-remote-files.sh`, `src/open-web-gaming-admin.py` | SFTP and opt-in browser administration |
| `src/restart-streaming.sh`, `server/` | Explicit host maintenance tools with narrow documented assumptions |
| `Makefile`, `package.py`, `assets/` | Build, pinned embedded fonts, package manifest and icons |
| `tests/`, `.github/workflows/` | Regression tests, CI and immutable release publishing |

`src/main.c` is still a large GTK controller, with shared indexed settings and synchronous onboarding operations. New modules should keep GTK widgets and remote I/O out of parsing/persistence code. Split one responsibility at a time with behavioral tests; do not replace the GUI or mix a large formatting-only diff with a functional change.

A shared `.clang-format` defines four-space C indentation and a 100-column target. Format newly extracted or edited functions, not the entire legacy `main.c` in unrelated PRs. Preserve the existing serialized config index order, file path and legacy preset inputs.

The active [six-item Beta 1 engineering work order](docs/PRODUCT.md#beta-1-engineering-execution-plan) is applied within existing product milestones. For the first Wolf slice, separate transport/parsing from GTK before changing blocking calls. Any worker result must return to the GTK main context, respect cancellation and dialog lifetime, and be checked against the intended client identity. Keep formatting-only changes out of behavioral PRs. Sanitizers belong to a separately tested diagnostic target, not a surprise change to release build flags.

## Local build

Target tested CI environment: Ubuntu 24.04 amd64 with GCC, make, binutils, Python 3, GTK3/fontconfig headers, OpenSSL headers, curl, Pillow and Xvfb/test GUI dependencies. A clean build downloads two fonts from pinned upstream revisions with integrity and size verification.

```sh
make check-process check-presets check-config
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
