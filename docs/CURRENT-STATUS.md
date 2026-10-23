# Current implementation and verification

Updated October 23, 2026 (JST). **Source code, published releases, CI and physical acceptance are different evidence levels.** This is the current status page, not a chronological PR log.

## October 23 — Jellyfin zero-URL discovery on existing host (PR #183)

**Physically exercised, source PR and manual host rollout; not yet a tagged client release or full Video acceptance.** The owner verified the existing Jellyfin instance at host loopback `127.0.0.1:8096` and via approved Tailscale address `100.121.156.34:8096`, both identifying the server as `OptiPlex`. After backing up the restricted Games broker and installing read-only `media_endpoint.py` plus its narrow `media` action, the owner tested the PR #183 MacBook build: authenticated discovery returned `available`, and clicking Videos reached Jellyfin without entering an address. No Jellyfin/Caddy/Wolf/Docker/Tailscale services or libraries were modified. Host rollback backup: `~/.local/share/optiplex-now/backups/jellyfin-discovery-20261023-135345/`.

**Still open:** Real playback audio through the newly discovered route, negative unauthorized-device/incorrect-host and outage behavior, supported clean-host adoption/provisioning, viewer roles and CSS appearance differences between direct Tailnet and custom reverse-proxy addresses. The subsequent `media_flow.c/.h` modularization has not been physically retested. PR #183 is not merged or released as of this observation. The Videos fallback to a preconfigured address is preserved for existing installations.

## October 23 — NOW-managed Steam Games live acceptance (PR #182)

**Physically exercised on the existing reference OptiPlex and Linux Mint MacBook; not a clean-host or full private-alpha acceptance.** The owner installed PR #182 test package `1.18.0+pr182.496` on the MacBook and the narrowly authenticated host Games broker on the existing OptiPlex. Direct Wolf Steam advertisement was backed up then removed; the persistent owner Steam directory, Wolf configuration, legacy links and independent physical desktop were preserved. The owner clicked NOW **Games** and observed automatic Moonlight launch, Steam Big Picture, usable mouse/keyboard, playable Resident Evil 2 Remake, Steam exit and subsequent Moonlight closure. A second managed Steam launch also succeeded without restarting Wolf. The game-to-Steam exit once took approximately one minute; the Wolf UI appears briefly during transitions and a Steam window initially appeared minimized/behind other windows. Those are recorded UX/performance observations, not game-streaming failures.

**Lease lifecycle physically verified:** Initial closed Moonlight left one registered Wolf UI session and a joined owner Steam lease with no lobby and no Steam writer. An authenticated guarded Stop recovered one test. The revised non-mutating `reconcile` accepted only an authorized owner's residual Wolf UI session with zero lobbies and no Steam writers, archived the lease, and returned `wolf_ui_connected`. After a subsequent natural Steam exit, a fresh restricted `status` returned `wolf_ui_connected`, evidencing **automatic cleanup** and readiness for another start. Host module rollback backup: `~/.local/share/optiplex-now/backups/owner-launch-pre-reconcile-20261023-131943.py`. Do not generalize to multiple owners or unrestricted direct Wolf access.

**Still open:** Fresh unassisted owner-device enrollment, second device and writer-conflict tests, audio/controller independently verified, supported clean-host GUI setup/adoption, safe recovery across reboots/outages, Videos discovery, downloader VPN isolation and server-enforced viewer roles. PR #182 tests passing is distinct from those physical release gates. Latest PR head tested in CI: `4af7e3c`; physical client package was built from an earlier PR revision, with the subsequently tested host reconciliation update deployed separately. v1.18.0 remains the published prerelease until a new tagged build is actually published.

## Release status

- **Published closed-beta prerelease:** [v1.18.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.18.0), October 21, 2026. Download the versioned `OptiPlex-Now_1.18.0_amd64.deb` and verify the release `SHA256SUMS`. This package includes the existing-host client plus a **guarded experimental clean-host Wolf pilot**, not the full three-pillar installer. [Release process](RELEASE-PROCESS.md).
- **Physical client acceptance and follow-up:** [October 21 MacBook test report](QA-MACBOOK-2026-10-21.md) on Linux Mint XFCE v1.18.0 observed Tailscale/server discovery, Moonlight pairing, Wolf XFCE and Jellyfin playback **after manual URL Settings correction** (audio not separately measured). Steam initially failed. On **October 22**, direct Moonlight Steam launch succeeded on the MacBook **after backing up its fresh Wolf Steam directory and manually symlinking it to the existing owner Steam state** (details in [#152](https://github.com/SteezyMode/OptiplexNow/issues/152) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154)). This verifies a working streamed Steam application, **not** a complete game/input/performance acceptance or zero-terminal first-run setup. Pairing and persistence defects remain; **Beta 1 not accepted.**
- **Source and release distinction:** [PR #142](https://github.com/SteezyMode/OptiplexNow/pull/142) removed Music Server Profiles from the onboarding wizard on `main` after v1.18.0 was tagged. [PR #143](https://github.com/SteezyMode/OptiplexNow/pull/143) proposes collapsed optional wake controls. Neither should be represented as included in the tested v1.18.0 install. CI and existing host pilot checks do not prove a clean host deployment or an actual Steam game stream.

## October 23 physical owner Steam acceptance (source-only pilot)

**Physically exercised, not released:** After safely backing up the Wolf
configuration, owner Steam workspace and uncertain launch lease, the owner
cleared a stale lobby with a Wolf-only restart. A new host-local pilot run
using verified legacy NVIDIA `video/x-raw` caps passed CreateLobby and
JoinLobby on the actual OptiPlex. The MacBook transitioned from Wolf UI to
Steam and ran **Resident Evil 2 Remake with working gameplay**, while the
OptiPlex physical desktop remained independently usable. The named Steam
workspace was backed up and verified before launch. See [issue
#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

**Physically verified managed lifecycle on reference host:** After the user
exited RE2R and disconnected Moonlight, Wolf reported zero lobbies/sessions.
With no Steam writer active, merged PR #175's `reconcile` archived the old
v1 lease without Wolf restart. A new v2 Create+Join opened Steam and stored
a private PIN; the operator's guarded StopLobby returned
`{lease_archived:true,status:"idle",success:true}` and returned the MacBook
to Wolf UI. Another preflight passed and a further v2 Create+Join reopened
Steam **without restarting Wolf or manually touching leases**. This proves
the host-local **Create → Join → Play RE2R → Stop → Relaunch** path while the
physical OptiPlex desktop remains usable. Steam audio was not separately
verified.

**Not a completed NOW Games workflow:** The shipped NOW Games button still
runs direct `moonlight stream HOST Steam`. A separate restricted Games SSH
transport has since passed real device-bound status and rejection checks on
the MacBook, but the GTK button does not invoke it. As of the subsequent
read-only October 23 physical check, the reference host had **no active
owner lease**, no detected Steam processes or Steam containers, one Wolf UI
session and zero lobbies. These are point-in-time observations, not a
license to create another Steam session. Automated first-run enrollment,
multi-device handoff, client-side Games orchestration and a clean-host
installation remain unaccepted. **Private Alpha 1 remains unaccepted.**

## October 22 owner Steam source-only development (unreleased)

Following the physical MacBook/Mac mini tests, merged PRs #162, #163 and #164
added **read-only Wolf profile inventory**, **developer-only owner/device
policy**, and an **offline named Steam lobby request planner**. PR #165
added a guarded **host-local Create/Join transaction** with a durable
fail-closed launch lease and simulated failure-path tests. These files are
source-level preparation, not installed operational host services. Normal
client Games still launches the legacy direct Moonlight Steam app, Wolf's
direct-app permissions are not restricted by NOW's policy, and fresh-owner
client P0 remains **unaccepted**. The host-local source work subsequently
passed real Create+Join and a full lifecycle check on October 23, above. See [engineering trail](ENGINEERING-TRAIL.md) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## October 22 Wolf protocol fixture (PR #166, source-only)

The repository now has a bounded allowlisted Wolf socket adapter,
a fixed host-side Docker bridge, and a disposable AF_UNIX HTTP daemon
fixture covering create/join transport and persisted lease behavior.
This is **not an actual Wolf image integration test**, has not been deployed
on the reference host, and does not change the Games shortcut, authenticate
a remote client, or prevent direct Wolf bypass. The fresh-client owner Steam
acceptance gate remains open (#154). See [engineering trail](ENGINEERING-TRAIL.md).

## Real Wolf read-only API compatibility (PR #167)

**Verified actual upstream Wolf daemon, read-only:** GitHub Actions run
`39757247197` started Wolf in a disposable, network-isolated Ubuntu 24.04
container with empty temporary Wolf state and no GPU/input devices or Docker
management socket. The actual daemon's five API GETs returned success:
`apps=2`, `profiles=1`, `clients=0`, `sessions=0`, `lobbies=0`.
This is **not** physical GPU streaming, native lobby Create/Join, an authorized
owner broker, or accepted fresh-client Games. Earlier probe failures were
caused by test assertion, scratch cleanup and restrictive image-volume
validation; all fixes are recorded in [engineering trail](ENGINEERING-TRAIL.md).
The exact image digest is recorded by the workflow, and no owner-host data or
running services were involved. See [real Wolf validation](REAL-WOLF-VALIDATION.md).

## Wolf lobby protocol verification (PR #168, disposable state only)

[Actual Wolf run 39761010450](https://github.com/SteezyMode/OptiplexNow/actions/runs/39761010450)
confirmed the pinned daemon's Create/Join schema and **accepted one real
disposable process-lobby Create POST** via NOW's HTTP adapter. No Join was
attempted and no Steam account, Moonlight session or GPU was used. The source
Steam planner was tightened to reject incomplete tagged Docker runners; older
mock fixtures omitted required fields. **The owner's Games shortcut and host
remain unchanged. Fresh-client P0 still fails acceptance.** See
[validation levels](REAL-WOLF-VALIDATION.md) and
[engineering trail](ENGINEERING-TRAIL.md).

## October 22 host-local owner launch pilot (source only)

The repository now includes a read-only host operator entry point at
`server/owner_steam_pilot.py inspect`, using actual Wolf inventory and the
existing named-profile lobby planner. Enrollment requires explicit host owner
and device consent; a later live Create+Join is guarded by additional host
operator flags and the existing durable lease. This **is not remote device
authentication, a deployed host service or a NOW Games-button change**. The
MacBook's active Wolf UI session, paired identity and complete `user` Steam
runner were observed physically, but native owner Steam Create+Join and
fresh-owner one-click access remain **unaccepted**. See
[the guarded host pilot](HOST-OWNER-PILOT.md) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## October 23 Wolf Steam video producer caps guard (PR #174, source only)

Physical CreateLobby returned a GStreamer pipeline syntax error followed by a
20-second setup timeout. Code inspection found NOW passed an empty
`video_producer_buffer_caps`; upstream Wolf uses that string in the video
producer. This is a strong candidate, **not a verified root-cause fix**.
Source PR #174 requires explicit host-verified software or NVIDIA-zero-copy
caps and refuses a create attempt otherwise, without writing a lease.
The previous failed lobby and uncertain lease were subsequently reconciled
in supervised recovery. GitHub tests were fixture/protocol evidence on merge;
the corrected caps subsequently passed real Steam + RE2R and relaunch tests.
See [host pilot](HOST-OWNER-PILOT.md) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## Games button integration boundary

`server/owner_games_request.py` is the narrow `status/start/stop` host
policy handler; `server/owner_games_ssh.py` accepts those operations over
an owner-approved, forced-command SSH key bound to an existing Wolf device.
That restricted path has now passed a real MacBook `status` request and
negative shell and remote-forwarding tests. The application is **not**
connected to the installed NOW Games button, and a generic client has no
zero-terminal Games-key enrollment. Source/CI tests do not replace full
live Start/Stop through the new transport or a physical GUI acceptance.

## October 23 physical restricted SSH and Steam alias audit

**Physically tested on the existing reference OptiPlex, not released:** The
MacBook generated its own independent Ed25519 Games key. The owner verified
the existing Wolf device grant and installed an OpenSSH
`restrict,command=...` entry binding the key to that device. With the
host-only Games policy still **disabled for Start/Stop**, the MacBook's
restricted-key `status` request returned `wolf_ui_connected`. A request
to run ordinary remote `id` failed with a denied JSON response and SSH
exit 1; reverse SSH port forwarding was refused with exit 255. These
checks verify this credential's narrow behavior, **not** all key-revocation,
multi-tenant isolation or production onboarding cases.

The host preflight reported `enabled:false`,
`legacy_links_reviewed:false`, caps `video/x-raw`, no active Steam
lease, and no matching Steam processes or containers. A top-level,
nonrecursive inventory completed across **8** Wolf per-device folders:
**5** `Steam` paths are symlinks to the same existing
`profile-data/user/WolfSteam` workspace; **3** use separate directories.
The earlier recursive scan was incomplete at 500 directories, but the
top-level per-device inventory completed. No files or links were edited.

The real Wolf apps inventory still exposes **Wolf UI, OptiPlex Studio
Desktop and direct Steam** to Moonlight. The named `user` profile also
includes Steam. Consequently, direct Steam can bypass NOW's single-owner
Games lease and potentially write the shared Steam workspace. Keep the
five symlinks and owner profile untouched; **do not enable remote
Start/Stop or delete direct Steam until the GTK managed Games flow and
controlled bypass-removal/rollback plan are ready**. The currently installed
NOW Games button still targets direct Steam. Full details in
[owner Games SSH](OWNER-GAMES-SSH.md) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## Capability status

| Capability | In current source | Real-world acceptance |
| --- | --- | --- |
| GTK3 client, saved settings, Games/Videos entry points, tray, diagnostics | Implemented for preconfigured hosts | v1.18.0 Mint client test passed Videos launch and playback after a manual URL fix; wizard URL persistence failed (#147); tray resize failed (#146) |
| Tailscale graphical setup, discovery and SSH trust/enrollment | Implemented GUI and helpers | v1.18.0 real client recognized existing Tailscale, discovered Wolf host, presented native SSH fingerprint and password dialogs; new login, verification outcome, reconnect and negative paths not accepted |
| Wolf/Moonlight connection and pairing | Pairing bridge implemented | Genuine Flatpak/AppImage pairs observed; Wolf XFCE AppImage stream passed; Steam AppImage streaming passed October 22 **only after manual Wolf server-state symlink repair** (#152, #154); buried approval window, manual refresh and missing completion feedback (#144, #145) |
| Moonlight and encrypted backup GUI | Flatpak guided install and AppImage selection implemented | Fresh client Flatpak install observed; legacy Intel Flatpak codec warnings; AppImage XFCE streamed; backup and upgrade preservation not tested |
| Owner-configured media, downloads and files | Videos/Music/Downloads URLs, SFTP and Gluetun status; no managed media install | Jellyfin content playback on existing host physically passed from Mint client with manually saved URL; audio not separately measured; downloads, files, VPN leak and managed Jellyfin **not** tested; no-URL service onboarding is #148 |
| Optional music service | Music link and existing-host profile export for a DroppedNeedle/slskd/qBittorrent/Gluetun configuration | Experimental for general users, no bundled DroppedNeedle installation, recommendations or Spotify-like catalog |
| Server Setup review | Separate GTK window; real read-only preflight and plan shipped in PR build | Real hardware observation useful, but **not** an installation certificate |
| Clean NOW-managed Wolf installation | Developer/alpha implementation in `server/host_install.py` and GUI, AMD/Intel/NVIDIA; immutable image, root recheck, dedicated state | **No confirmed clean physical host install** |
| NVIDIA userspace driver volume | `host_nvidia.py`: version-specific build with official installer SHA256 check; no host-driver replacement | Physical encode and driver-update migration/rollback **unverified** |
| Separate game sessions preserving host display | Wolf named-profile Steam Create/Join/Stop source pilot; installed NOW Games button not wired | **Physically verified on reference OptiPlex:** MacBook played RE2R while host desktop stayed free, followed by managed v2 Stop/relaunch. **Not accepted on fresh client or clean host through NOW GUI.** |
| Restricted owner Games credential | Forced-command per-device SSH status/start/stop code on `main`, manually installed on reference host | Physical MacBook `status` succeeded; shell and reverse forwarding denied. Start/Stop **disabled**, wrong-key/revocation and GTK Games handoff **not** physically accepted; 5 shared legacy Steam aliases and direct Steam bypass remain. |
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

**Next implementation:** integrate the restricted Games client with GTK without blocking the UI: verify the dedicated credential, start `Wolf UI` through Moonlight, wait for a matching authenticated `wolf_ui_connected` status, issue at most one managed Start, and provide meaningful busy, failure, reconnect and guarded Stop behavior. No implicit fallback to direct Steam on a denied/uncertain managed launch. Validate through NOW, then plan a reversible, backed-up removal of only **direct** Steam from Moonlight's app list while preserving the named owner profile and existing symlinks. Keep host Games write controls disabled until bypass/isolation and race issues are reviewed. After this, address first-run pairing and settings persistence, test a second household device, and separately validate a clean host (#154).** Use the [Host installer acceptance checklist](HOST-INSTALLER.md#physical-host-acceptance-before-alpha-sign-off) for a **clean server plus a second client**. Record OS, GPU/driver, Docker/Compose, Wolf digest, package build, observed video/audio/input and recovery behavior.

Continue [Beta 1 client acceptance](BETA-ACCEPTANCE.md) against an owner-approved existing host. The [MacBook report](QA-MACBOOK-2026-10-21.md) is a partial device pass and a set of blocking defects; restart/upgrade/reconnection, new Tailscale sign-in and full gaming remain open. The two acceptance tracks must not be conflated.

**Do not announce a validated alpha or commercial readiness based on source and CI alone.** Fix physical-test defects before adding more server frameworks, simulated lifecycle features or general-purpose dashboards.

## Tracked decisions and references

- [Product direction and phased roadmap](PRODUCT.md) defines scope; [Architecture](application-design.md) defines privilege/data boundaries.
- [#76](https://github.com/SteezyMode/OptiplexNow/issues/76): existing-host client acceptance.
- [#98](https://github.com/SteezyMode/OptiplexNow/issues/98): reproducible NOW Host install, operational readiness and recovery.
- [#94](https://github.com/SteezyMode/OptiplexNow/issues/94): future existing-account device authorization.
- [#85](https://github.com/SteezyMode/OptiplexNow/issues/85): long-range Wolf/desktop feasibility.

For individual module changes, consult [merged GitHub PRs](https://github.com/SteezyMode/OptiplexNow/pulls?q=is%3Apr+is%3Amerged) instead of maintaining another chronological PR catalogue here.
