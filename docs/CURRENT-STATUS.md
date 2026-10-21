# Current implementation and verification

Updated October 21, 2026 (JST). **Source code, published releases, CI and physical acceptance are different evidence levels.** This is the current status page, not a chronological PR log.

## Release status

- **Published closed-beta prerelease:** [v1.17.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.17.0), published October 21, 2026. Download the versioned `OptiPlex-Now_1.17.0_amd64.deb` and verify the release `SHA256SUMS`. [Release procedure](RELEASE-PROCESS.md).
- **Latest merged host source:** [PR #134](https://github.com/SteezyMode/OptiplexNow/pull/134) added NVIDIA first-install volume preparation after the clean AMD/Intel pilot. **This code is not included in v1.17.0.** Passing PR checks does not update installed computers or publish a new release.
- **Last verified PR #134 CI:** 200 Python tests passed, both workflow jobs passed; native diagnostics, a built and installed `.deb`, read-only host scripts and the real GTK review window ran on disposable CI infrastructure. **No live Wolf installation or streaming session was validated.**

## Capability status

| Capability | In current source | Real-world acceptance |
| --- | --- | --- |
| GTK3 client, saved settings, Games/Videos entry points, tray, diagnostics | Implemented; current release provides client functions for preconfigured hosts | Existing-host functionality only; exact v1.17.0 fresh-client run still pending |
| Tailscale graphical setup, discovery and SSH trust/enrollment | Implemented helpers and GUI, with automated negative-path checks | Fresh physical sign-in, PolicyKit and fingerprint/password paths pending |
| Wolf/Moonlight connection and pairing | Client bridge and asynchronous work implemented; tests include refusal and stale requests | Genuine unpaired-client pairing and actual stream pending |
| Moonlight and encrypted backup GUI | Install and backup/restore paths implemented with automated checks | Fresh-device install, failure handling and upgrade preservation pending |
| Owner-configured media, downloads and files | Videos, Music and Downloads service URLs, SFTP remote files, Gluetun Docker health status | Works against existing reference stack; **not** a NOW-installed media platform, native torrent client or validated VPN traffic-leak test |
| Optional music service | Music link and existing-host profile export for a DroppedNeedle/slskd/qBittorrent/Gluetun configuration | Experimental for general users, no bundled DroppedNeedle installation, recommendations or Spotify-like catalog |
| Server Setup review | Separate GTK window; real read-only preflight and plan shipped in PR build | Real hardware observation useful, but **not** an installation certificate |
| Clean NOW-managed Wolf installation | Developer/alpha implementation in `server/host_install.py` and GUI, AMD/Intel/NVIDIA; immutable image, root recheck, dedicated state | **No confirmed clean physical host install** |
| NVIDIA userspace driver volume | `host_nvidia.py`: version-specific build with official installer SHA256 check; no host-driver replacement | Physical encode and driver-update migration/rollback **unverified** |
| Separate game sessions preserving host display | Core Wolf-based product requirement; Wolf supports virtual app/session concepts | **Not yet physically verified end-to-end by NOW on a clean host** |
| Windows clients and hosts | Explicit roadmap: Windows client first, independent-session Windows host later | Neither is implemented; Windows host adds licensing/technical feasibility gates |
| Owner-mediated automatic device access by email | Future design only | Not implemented |
| Turnkey install, dependency setup, repair, upgrades, uninstall | No complete end-to-end implementation | Not alpha-accepted |

A running Docker container is **not** an active session, verified hardware encoder or successfully paired streaming client. Unknown service status remains unknown.

## Technical boundaries

- The product vision is a modular personal entertainment server, initially gaming plus remote media/download management. The first-run product promise includes independent game sessions leaving the physical host desktop usable; this is still an acceptance requirement, not an observed fresh-install result.
- NOW's released client does **not** provision Wolf, Docker or media services. The developer-only Server Setup install path requires a clean Ubuntu/Pop!_OS 24.04 amd64 host, an OS administrator prompt, Docker/Compose already present and manually verified immutable image inputs.
- Install code refuses preexisting NOW-managed workspaces/projects and Wolf port conflicts. It does not adopt or delete user containers. The live reference host is **not** an installation test target.
- NVIDIA's manual driver-volume first-install path exists, but automatic regeneration and safe migration after a driver update do not. The installer is not byte-for-byte reproducible because base image/apt dependencies are not fully pinned. [Host installer contract](HOST-INSTALLER.md).
- The client remains modularizing incrementally. `src/main.c` is still a substantial GTK controller; native tests and sanitizers do not cover every UI path or field condition.
- The source also retains separate experimental host staging, transaction and local-authorization modules. Their tests do **not** establish that these prototypes are deployed or connected to the operational installer.

## Immediate acceptance gates

**Next action: install and stream on independent hardware.** Use the [Host installer acceptance checklist](HOST-INSTALLER.md#physical-host-acceptance-before-alpha-sign-off) for a **clean server plus a second client**. Record OS, GPU/driver, Docker/Compose, Wolf digest, package build, observed video/audio/input and recovery behavior.

Separately complete [Beta 1 client acceptance](BETA-ACCEPTANCE.md) against an already owner-approved host: fresh desktop package install, browser Tailscale sign-in, verified SSH identity, genuinely unpaired Moonlight/Wolf client, Games and Videos, restart/upgrade and reconnection. The two acceptance tracks must not be conflated.

**Do not announce a validated alpha or commercial readiness based on source and CI alone.** Fix physical-test defects before adding more server frameworks, simulated lifecycle features or general-purpose dashboards.

## Tracked decisions and references

- [Product direction and phased roadmap](PRODUCT.md) defines scope; [Architecture](application-design.md) defines privilege/data boundaries.
- [#76](https://github.com/SteezyMode/OptiplexNow/issues/76): existing-host client acceptance.
- [#98](https://github.com/SteezyMode/OptiplexNow/issues/98): reproducible NOW Host install, operational readiness and recovery.
- [#94](https://github.com/SteezyMode/OptiplexNow/issues/94): future existing-account device authorization.
- [#85](https://github.com/SteezyMode/OptiplexNow/issues/85): long-range Wolf/desktop feasibility.

For individual module changes, consult [merged GitHub PRs](https://github.com/SteezyMode/OptiplexNow/pulls?q=is%3Apr+is%3Amerged) instead of maintaining another chronological PR catalogue here.
