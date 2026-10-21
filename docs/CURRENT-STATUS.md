# Current implementation and verification

Updated October 21, 2026 (JST). **Source code, published releases, CI and physical acceptance are different evidence levels.** This is the current status page, not a chronological PR log.

## Release status

- **Published closed-beta prerelease:** [v1.18.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.18.0), October 21, 2026. Download the versioned `OptiPlex-Now_1.18.0_amd64.deb` and verify the release `SHA256SUMS`. This package includes the existing-host client plus a **guarded experimental clean-host Wolf pilot**, not the full three-pillar installer. [Release process](RELEASE-PROCESS.md).
- **First physical client acceptance:** [October 21 MacBook test report](QA-MACBOOK-2026-10-21.md) on Linux Mint XFCE v1.18.0. Existing Tailscale/server discovery, Moonlight installation and Wolf pairing were observed; Moonlight 6.2.0 AppImage streamed Wolf XFCE; Jellyfin playback passed **after manual URL Settings correction** (audio not separately measured). Steam streaming failed, pairing UX was obstructive, URL persistence and tray resizing failed. **Beta 1 not accepted.**
- **Source and release distinction:** [PR #142](https://github.com/SteezyMode/OptiplexNow/pull/142) removed Music Server Profiles from the onboarding wizard on `main` after v1.18.0 was tagged. [PR #143](https://github.com/SteezyMode/OptiplexNow/pull/143) proposes collapsed optional wake controls. Neither should be represented as included in the tested v1.18.0 install. CI and existing host pilot checks do not prove a clean host deployment or an actual Steam game stream.

## Capability status

| Capability | In current source | Real-world acceptance |
| --- | --- | --- |
| GTK3 client, saved settings, Games/Videos entry points, tray, diagnostics | Implemented for preconfigured hosts | v1.18.0 Mint client test passed Videos launch and playback after a manual URL fix; wizard URL persistence failed (#147); tray resize failed (#146) |
| Tailscale graphical setup, discovery and SSH trust/enrollment | Implemented GUI and helpers | v1.18.0 real client recognized existing Tailscale, discovered Wolf host, presented native SSH fingerprint and password dialogs; new login, verification outcome, reconnect and negative paths not accepted |
| Wolf/Moonlight connection and pairing | Pairing bridge implemented | Genuine Flatpak/AppImage pairs observed; Wolf XFCE AppImage stream passed; Steam stream failed; buried approval window, manual refresh and missing completion feedback (#144, #145) |
| Moonlight and encrypted backup GUI | Flatpak guided install and AppImage selection implemented | Fresh client Flatpak install observed; legacy Intel Flatpak codec warnings; AppImage XFCE streamed; backup and upgrade preservation not tested |
| Owner-configured media, downloads and files | Videos/Music/Downloads URLs, SFTP and Gluetun status; no managed media install | Jellyfin content playback on existing host physically passed from Mint client with manually saved URL; audio not separately measured; downloads, files, VPN leak and managed Jellyfin **not** tested; no-URL service onboarding is #148 |
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

- The [public-alpha product contract](PUBLIC-ALPHA.md) requires **all three** physically validated workflows: independent games, Jellyfin video and VPN-isolated remote download administration. The experience must keep the physical host desktop usable and ordinary services outside the download VPN. The role model is **owner/admin** (downloads, file management and settings) versus **member/viewer** (authorized playback and optionally approved gaming), enforced server-side. **None of that full stack or access boundary is accepted today.**
- Published v1.18.0 includes an **experimental, guarded clean-host Wolf-only installer** requiring a clean Ubuntu/Pop!_OS 24.04 amd64 host, an OS administrator prompt, Docker/Compose already present and manually verified immutable image inputs. It has **no clean physical host acceptance** and does not install Docker, Jellyfin, media services or VPN downloads. The main existing-host client does not automatically provision any service.
- Install code refuses preexisting NOW-managed workspaces/projects and Wolf port conflicts. It does not adopt or delete user containers. The live reference host is **not** an installation test target.
- NVIDIA's manual driver-volume first-install path exists, but automatic regeneration and safe migration after a driver update do not. The installer is not byte-for-byte reproducible because base image/apt dependencies are not fully pinned. [Host installer contract](HOST-INSTALLER.md).
- The client remains modularizing incrementally. `src/main.c` is still a substantial GTK controller; native tests and sanitizers do not cover every UI path or field condition.
- The source also retains separate experimental host staging, transaction and local-authorization modules. Their tests do **not** establish that these prototypes are deployed or connected to the operational installer.

## Immediate acceptance gates

**Next action: resolve the observed v1.18.0 Steam-stream failure and beta UX/persistence regressions, while preparing an independent physical clean-host test.** Use the [Host installer acceptance checklist](HOST-INSTALLER.md#physical-host-acceptance-before-alpha-sign-off) for a **clean server plus a second client**. Record OS, GPU/driver, Docker/Compose, Wolf digest, package build, observed video/audio/input and recovery behavior.

Continue [Beta 1 client acceptance](BETA-ACCEPTANCE.md) against an owner-approved existing host. The [MacBook report](QA-MACBOOK-2026-10-21.md) is a partial device pass and a set of blocking defects; restart/upgrade/reconnection, new Tailscale sign-in and full gaming remain open. The two acceptance tracks must not be conflated.

**Do not announce a validated alpha or commercial readiness based on source and CI alone.** Fix physical-test defects before adding more server frameworks, simulated lifecycle features or general-purpose dashboards.

## Tracked decisions and references

- [Product direction and phased roadmap](PRODUCT.md) defines scope; [Architecture](application-design.md) defines privilege/data boundaries.
- [#76](https://github.com/SteezyMode/OptiplexNow/issues/76): existing-host client acceptance.
- [#98](https://github.com/SteezyMode/OptiplexNow/issues/98): reproducible NOW Host install, operational readiness and recovery.
- [#94](https://github.com/SteezyMode/OptiplexNow/issues/94): future existing-account device authorization.
- [#85](https://github.com/SteezyMode/OptiplexNow/issues/85): long-range Wolf/desktop feasibility.

For individual module changes, consult [merged GitHub PRs](https://github.com/SteezyMode/OptiplexNow/pulls?q=is%3Apr+is%3Amerged) instead of maintaining another chronological PR catalogue here.
