# Future NOW Host installer

**Status:** design contract only. No turnkey host setup is shipped. The developer's OptiPlex is a reference machine, not an installation template. Track delivery in [#98](https://github.com/SteezyMode/OptiplexNow/issues/98).

## Initial supported scope

Start with one explicitly supported Linux distribution and a verified hardware/driver matrix. Stream one Wolf application to one Moonlight device; optionally install Jellyfin with independent credentials. Add multi-desktop and multi-user features only after security and persistence gates pass.

VPN, qBittorrent, slskd, music, Caddy and Studio are optional. They must not be installed automatically for basic gaming or video service access.

## Installation contract

1. **Preflight:** OS/architecture, network interfaces, GPU codec/encoder, driver stack, available storage, ports, Docker/runtime presence, filesystem permissions, existing services and conflict report. Never claim compatibility from a device name alone.
2. **Plan:** show exact packages, images, paths, networks, ports, accounts, secrets and service interruptions before changes. Preserve unrelated resources.
3. **Ownership:** use a dedicated managed namespace/root directory for manifests, configuration, state, backups and logs. Track service IDs and installed versions in a versioned manifest with ownership metadata, not incidental container names.
4. **Deployment:** pin upstream images and install only selected services. Use explicit service dependency ordering and documented networks. No unreviewed privileged mounts or public admin endpoints.
5. **Identity:** register host ownership, local restricted management agent and permitted actions. Pair Moonlight devices through host-local Wolf APIs, never direct remote access to Wolf/Docker sockets. Future device approval should require owner confirmation without repeated manual SSH.
6. **Verification:** test that the service starts, a supported game/desktop stream launches with input and audio, optional media login works, and client status/health reports match observed state.
7. **Lifecycle:** offer safe plan/apply/retry/repair/update/rollback/uninstall. Preserve personal media, games, profiles, pairings and backups by default. Clearly separate removing software from deleting user data.

## Proposed organization

Paths and identifiers below are **candidate conventions**, not installed artifacts:

| Category | Candidate |
| --- | --- |
| Managed system configuration | `/etc/optiplex-now/host/` |
| Persistent app-managed data | `/var/lib/optiplex-now/host/` |
| Operator logs and diagnostics | systemd journal plus `/var/log/optiplex-now/` only when needed |
| Agent executable | `/usr/libexec/optiplex-now/` or distribution-standard libexec path |
| Versioned service manifest | `/var/lib/optiplex-now/host/manifest.json` |
| Managed Docker/Compose objects | `optiplex-now.*` labels and explicit service IDs; never rely on fixed display names |

Verify Debian conventions, permissions and backup semantics before adopting these paths. Secrets must be root/agent accessible only, absent from diagnostics and Git. User library paths must remain configurable and outside auto-deletion.

## Host health contract

A future host agent should return explicit versioned states for:

- Reachability and trusted identity.
- Wolf daemon health, API compatibility, available apps and active sessions.
- GPU codec/encoder availability and resource pressure.
- Optional media readiness and login endpoint.
- Optional VPN gateway health, with separate tunnel/external-route verification if actually implemented.
- Managed image versions, failed upgrades, migrations and pending repairs.

**Running**, **healthy**, **connected**, **paired**, and **currently streaming** must remain different values. Missing healthchecks do not imply a healthy tunnel.

## Existing host import

A host with existing `music-vpn` Gluetun, Wolf, Jellyfin or qBittorrent cannot be assumed to follow managed naming or directory conventions. Provide a read-only inventory, explicit ownership selection and non-destructive adoption path. Otherwise use the existing setup without taking control of it. Do not rewrite container networks or volumes merely to standardize display names.

## Acceptance before release

- Disposable fresh-host install and clean removal, then repeat to prove idempotence.
- Failed/partial install, rollback and retry without damaged data.
- Upgrade across two supported pinned versions without lost settings or credentials.
- Non-interference with separately installed and running unrelated services.
- Least-privilege review of the pairing/management agent.
- Fresh client can reach, pair with and use a working stream without the operator editing Compose or shell scripts.
- Diagnostics expose no SSH key, Moonlight certificate private key, VPN password, Wolf pair secret or token.

See [Wolf integration](UPSTREAM-FIRST-WOLF-INTEGRATION.md) for API and fork decisions; see [Multi-user feasibility](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md) for later user isolation.
