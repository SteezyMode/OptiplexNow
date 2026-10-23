## October 24 — PR #184 test package #616 MacBook physical smoke pass (reported)

The owner installed and tested unreleased test build `optiplex-now-pr-184-616` on the existing Linux Mint MacBook and reported **"works all good"** following the requested Games, Videos, Downloads, Files, tray and Settings smoke checks. This is a user-reported no-regression pass on the **already enrolled** normal `macbook` Linux account, not instrumented acceptance for every pillar or proof that an unapproved new account can enroll through the GUI. PR #184 exact-head build-and-test plus native sanitizer jobs passed for commit `268cd182ac0bbc15d9d296cc28c3f41a2ac7c0e4`. Its new diagnostics work in code; the observed manual enrollment was on the earlier PR #608 client and cannot establish that #616 automates it. **Next:** finish owner-approved, no-terminal restricted-device enrollment for a genuinely fresh client and verify its denial/revocation behavior before merging the PR.

## October 23 — Fresh Linux-profile owner enrollment failure (physically reproduced; diagnostic fix source-only)

A second Linux account on the same Mint MacBook had valid saved host/user settings, working ordinary owner SSH and a Moonlight profile already paired to the reference Wolf server. PR #184 build #608 nonetheless displayed a perpetual-looking Downloads discovery state and refused managed Games because `~/.local/share/optiplex-now/games-client/id_ed25519` was absent. The Setup Wizard's `AUTHORIZE SSH KEY` step provisions the **different, ordinary** `~/.ssh/id_ed25519` and does not enroll the restricted owner credential. The reference owner identified the correct Wolf client by observing it disconnect, then manually granted that client an owner-policy entry and restricted forced-command SSH public key; **Downloads subsequently worked**. No Wolf, qBittorrent, VPN or other service was restarted. This establishes one owner-profile failure/recovery on the reference system, not supported graphical enrollment.

Source fix in this PR: Downloads now checks for a missing local restricted key before any SSH request and gives a specific enrollment message; unsuccessful queue requests no longer leave the discovery label appearing active; the wizard distinguishes ordinary SSH/Moonlight pairing from separate owner-device approval and does not label that flow fully ready. Python and source-contract tests cover the new failure message and fail-closed no-key check. **Graphical owner-approved restricted-key enrollment, binding to the verified Wolf client ID, revocation and clean-client acceptance remain unimplemented alpha blockers.** Do not call this incident an auto-enrollment fix.

## October 23 — Read-only Adopt Existing / Set Up New host plan (source-only)

Added `server/host_adoption.py`, a deterministic, fail-closed recommendation layer over the existing local Docker service inventory. It recommends inspection of one running/stopped Wolf/Jellyfin/qBittorrent/Gluetun candidate, blocks ambiguous/inaccessible inventories, refuses to infer that a missing Docker container means no native installation, and explicitly blocks unsafe downloader/Gluetun topologies. It never copies service names, paths, container IDs, credentials or Docker environment into its output and **never authorizes adoption or installation**. The local GTK Host Setup review now prints these recommendations after the hardware, install-plan and service-census steps; packaging and mock/installed-package tests cover the new read-only tool. This is progress towards understanding what to preserve on a real host, NOT a working adoption installer. No reference service was touched; fresh-host/client, privileged approval, configuration backup, media mount mapping, viewer denial, and actual VPN fail-closed tests remain open.

## October 23 — Downloads page uses full available window (source-only, awaiting MacBook retest)

The owner pointed out that the two temporary top-of-page buttons (“VUE TORRENT” and “QUEUE SNAPSHOT”) waste precious space on the 2012 MacBook Air. Removed the toolbar and suppressed the informational status label while an authorized WebKitGTK VueTorrent view is active; the authenticated read-only queue is still rendered automatically if an embedded view cannot be opened. This changes only GTK layout and does **not** touch VueTorrent, qBittorrent, server processes or VPN. CI runs independently from physical acceptance; latest client build must be visually checked before claiming release acceptance.

**Next critical path:** host-side safe install/adopt (Wolf, Jellyfin, Gluetun/qBittorrent/VueTorrent with reviewed search plugins), authenticated owner/viewer access isolation and VPN fail-closed testing. Existing reference host is not an installation test; do not replace it in the name of alpha readiness.

## October 23 — MacBook automatic Downloads discovery ACCEPTED on reference devices

After the authenticated host-side `download_queue.py` update (WebUI port 8085; five torrents), the owner cleared the manually configured client **Downloads override** and reopened NOW Downloads. **VueTorrent successfully appeared automatically**, with no manually supplied address. This closes the *reference-device URL discovery test* only. Other physical successes: embedded VueTorrent login/search, tabs retaining the existing WebView, and tray Downloads navigation. Host module rollback backup: `/home/optiplex/.local/share/optiplex-now/backups/download-queue-20261023-171108-510144.py`.

The PR remains draft while release-facing access-control/failure and settings acceptance remain; the broader private alpha is NOT accepted. Specifically, an authorized client detecting an admin WebUI does not prove viewer/member denial at the service endpoint. Clean host provisioning, approved search-plugin packaging, VPN kill-switch test, protected media-root file browsing, and login persistence also remain open. No login secrets have been stored in the repository.

## October 23 17:11 JST — Downloader endpoint discovery host deployment verified

The reference OptiPlex owner ran a backed-up atomic update of the **existing host-side** `server/download_queue.py` module. The deployed code was compared to Git blob `d55d7a2c2e8943b25ec0696f6f5342eefdc35495` from commit `d6a62ef973195c1168dc63c9684bda5aeae8d382`. The host-local `inspect_queue()` health check succeeded and returned **`webui_port: 8085` and five torrents**. Host backup: `/home/optiplex/.local/share/optiplex-now/backups/download-queue-20261023-171108-510144.py`. No Docker, Gluetun, qBittorrent, Jellyfin or Wolf container changes were required. This verifies the host endpoint metadata, **not yet the full MacBook automatic discovery UX**. Owner's next test: clear client Settings > Downloads override, save and reopen Downloads; ensure embedded VueTorrent opens without manual URL. Viewer authorization, VPN kill switch, storage mapping, installer and login UX remain outstanding.

## October 23 — MacBook acceptance: Downloads persistence and tray routing

The owner **physically confirmed** on the MacBook that the latest Downloads client retains VueTorrent when switching NOW tabs and that choosing Downloads from the system-tray menu opens the existing in-app Downloads page. The embedded VueTorrent interface, login and torrent search were also previously verified on this machine. CI build #573 passed; the tested client is a branch artifact, not a published alpha release. The owner has not yet tested automatic WebUI endpoint discovery after deploying the updated restricted host-side queue descriptor, so manually entered Downloads URL remains the verified configuration on this reference system. Full viewer denial, VPN tunnel-failure isolation, server provisioning/search-plugin installation, permitted-root file management and clean-device onboarding are NOT accepted. Do not represent this page as shipped private alpha.

## October 23 — VueTorrent real-device acceptance and navigation fixes (PR #184)

The owner physically verified VueTorrent's login and torrent **search** using existing plugins inside NOW's MacBook GTK embedded Downloads view. This validates the existing adopted qBittorrent/VueTorrent/search environment, **not** automatic provisioning on a new server.

The owner also observed two client UX regressions: (1) reopening Downloads after visiting other NOW tabs reloaded VueTorrent and repeated the authenticated queue check; (2) choosing Downloads from the system-tray menu did not bring the app/window forward. Source fix now retains the existing WebKitGTK view, login state and JS search state when host/SSH user/Downloads override are unchanged, and rechecks/rebuilds only when a different host/config is selected or the prior attempt failed. The tray dispatcher restores the GTK app before invoking the standard Downloads navigation (same page as the top navigation button). Regression tests cover both paths. **Latest package CI and physical client acceptance still required.** This reuse cache is a client UX optimization, not server-side role authorization or revocation protection.

For alpha, owner-approved qBittorrent search engine plugins must be adopted or reproducibly provisioned during server setup (#187). Third-party search engines are Python programs; source inspection, pinned hashes, explicit owner authorization and preservation of existing engine configurations are mandatory. No new plugin was installed or fetched on the reference machine; no live Docker, qBittorrent, Gluetun or credential changes.

## October 23 — Download WebUI auto-discovery (PR #184, awaiting host deployment)

**Physical client observation:** the owner tested the embedded VueTorrent WebUI on the MacBook and reached the qBittorrent login screen after manually entering a Downloads URL. The user subsequently recovered access to their qBittorrent account. NO credentials, passwords, auth cookies, or personal account details have been recorded in this repository.

**Source changes:** `server/download_queue.py` now includes only the verified qBittorrent `webui_port` in its existing owner-authenticated bounded queue result. The Linux `download-queue-client.py --with-port` helper verifies the port (0 = older host) and emits a compact sanitized metadata line plus the same safe queue snapshot. The GTK Downloads module parses that port, combines it with the already paired host address, applies its local-host/private-origin policy, and opens the optional embedded WebView. A manually configured same-host URL remains fallback for older host versions. **Normal flow requires no Downloads URL entry.** The downloader's independent login is intentionally unchanged: no password injection, caching, login bypass, or single-sign-on is implemented.

**Validation:** CI/physical verification of the newest discovery patch and host deployment are separate gates. The reference host still needs an owner-controlled, backed-up update of `download_queue.py`; until then, only the pre-existing manual URL path works. The linked owner SSH preflight checks the device but cannot substitute for server-side owner/viewer controls over the qBittorrent WebUI.

## October 23 — Embedded VueTorrent pilot (PR #184; NOT physically verified)

The Linux client now has an optional, self-contained GTK3 WebKitGTK 4.1 renderer in `src/downloads_webview.c/.h`. It loads only when the user enters Downloads; systems without a WebKit runtime retain the already physically verified authenticated read-only queue. The Debian client merely **recommends** `libwebkit2gtk-4.1-0`, not a required dependency. The configured `Downloads URL` (`cfg[7]`) must use the same host as the connected NOW server (`cfg[0]`), HTTPS for domain names or private LAN/Tailscale IP HTTP, and must not contain userinfo or query parameters. There is no hardcoded reference IP or port. Unexpected top-level navigation, pop-up windows and browser-initiated file downloads are denied. The embedded WebUI uses qBittorrent's **own login**; no NOW credential, Docker socket, qBittorrent cookie, or bypass token is forwarded. Before constructing the WebView, the client must successfully complete the existing restricted owner-SSH `downloads_queue` request. This is a **client-side preflight only**, not yet a host-enforced permission boundary for raw qBittorrent WebUI access; future admin/viewer isolation and audited bridge remain open in #186.

**Not yet acceptance:** no real-device WebKitGTK rendering, VueTorrent content, login, form submission, streaming resource behavior, WebView RAM footprint, 640x500 usability, host-side qBittorrent authentication testing, or cross-platform webview have been verified. Existing VPN/qBittorrent and Jellyfin containers must remain untouched; this change is confined to the client and source-only tests. PR #184 stays draft pending physical GUI test. Private Alpha 1 is still NOT ACCEPTED per `docs/PRIVATE-ALPHA.md`.

# Current implementation and verification

Updated October 23, 2026 (JST). **Source code, published releases, CI and physical acceptance are different evidence levels.** This is the current status page, not a chronological PR log.

## October 23 — P2 authenticated qBittorrent queue physically verified (PR #184)

**Reference OptiPlex owner-only workflow passed.** On the Linux Mint MacBook, the paired restricted SSH credential sent `{"version":1,"action":"downloads_queue"}` to the reference host. The broker returned `success:true`, `service:qbittorrent`, `truncated:false`, and five sanitized queue entries containing only name, progress percentage and state. Four entries reported `missingFiles`; one reported `stalledUP`. No torrent was changed or automatically repaired. Live module install had backed up the prior broker at `~/.local/share/optiplex-now/backups/downloads-queue-20261023-143444-226917/`. Gluetun/qBittorrent were not restarted and no VPN settings changed. This validates only owner read-only queue retrieval, not viewer isolation, GUI presentation, queue mutation, path authorization or VPN kill-switch behavior.

## October 23 — P2 downloader authenticated status physically verified (PR #184)

**Existing reference host only, not alpha acceptance.** The owner's Linux Mint MacBook sent exactly `{"version":1,"action":"downloads_status"}` via its enrolled, forced-command SSH device credential to `optiplex@100.121.156.34`. The response was `success:true`, `version:1`, one `qbittorrent` record, `gateway_bound:true`, `gateway_healthy:true`, with `vpn_egress_verified:false` and `killswitch_verified:false`. This confirmed the new independent inventory module and authorization path on the existing host. The host modules were manually staged with an earlier backup at `~/.local/share/optiplex-now/backups/downloads-status-20261023-142321-251828/`; no containers or services restarted. A first SSH command accidentally used the MacBook login `test` and was denied; the corrected `optiplex` login succeeded immediately. Separately, operator-run public IP inspection observed distinct host and Gluetun exit addresses, but the module does not perform this inspection and does not claim tunnel kill-switch verification. Queue listing, queue actions, file permissions, VPN tunnel interruption and clean-host setup remain open.

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
