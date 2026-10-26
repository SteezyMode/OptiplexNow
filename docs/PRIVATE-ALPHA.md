# Private Alpha 1: release contract

**Status: NOT ACCEPTED.** This is the immediate, supported small-tester release target. It is not an announcement that the existing code, current beta, or reference server satisfies these requirements.

**Scope lock: one owner plus owner-operated devices only.** Independent member accounts, viewer/guest access, and their separate Steam profiles are later milestones. A member-facing release must independently pass server-side authorization tests.

**Product:** One personally owned compatible Linux PC becomes a private games, video and download server. An approved client uses graphical onboarding to play a game from an independent Wolf session, watch the owner's Jellyfin library, or manage their own VPN-isolated downloads and files. The host remains usable as a normal computer.

**Priorities:** complete the three real user journeys before broadening feature support. Deliver one maintainable host/client experience, not a thin page of launch buttons or a custom rewrite of third-party services.

## What "private alpha" means here

- Distribution is limited to the owner and a small group of explicitly approved testers. It must still be installable, recoverable, and safe for those testers.
- Target initially a documented, narrow Linux x86-64 host/client hardware/OS matrix. A Windows client is a later milestone, and Windows independent-session hosting is separate future feasibility work.
- The development reference server may be used to test adopting existing services; acceptance of a shippable private alpha additionally requires a fresh supported host installation test on **separate, disposable hardware** and a clean client.
- A user may choose which services they want enabled, but all **three pillars must be demonstrated** and signed off for this release.
- Ordinary setup must not require terminal, SSH commands, editing Compose/TOML, manual Steam symlinks, entering a Jellyfin URL, or hand-installing a Docker stack. Advanced diagnostics may exist.
- The approximately 15-minute target is measured from starting NOW setup on two OS-ready supported computers to the first authenticated game stream; it excludes OS setup, game downloads, media import, and acquiring VPN credentials. It does **not** imply fully configuring three services in 15 minutes.
- The commercial brand is undecided. OptiPlex NOW is a development codename; no Dell relationship is represented or implied.

## Pillar 1: independent games

**User story:** The owner installs or safely adopts an approved Wolf host, enrolls a client, selects Games, and plays a real game while somebody can independently use the physical host desktop and its local input/audio.

Acceptance:
- [ ] Guided install/adopt of a supported Wolf host, with physical encoding, game video, sound, controller input and local desktop independence verified.
- [ ] A truly fresh NOW client can discover an authorized host, complete approval/pairing, launch Games and reconnect without repeated PINs, terminal commands, or manual profile-storage changes.
- [ ] Multiple owner-approved devices connect to the **same durable owner Steam workspace**, with session conflict/reconnect handling and no overlapping writers to the same writable home.
- [ ] Failed create, pipeline, encoder, pairing and session operations produce understandable errors and bounded recovery. Ambiguous state-changing requests are never blindly retried.
- [ ] Host/network restart preserves game/account state. Existing working Wolf/Steam installations are not silently migrated or overwritten.
- [ ] Release acceptance demonstrates a real game, not just a created lobby, Steam splash screen or successful Moonlight spawn.

Critical issue: [#154](https://github.com/SteezyMode/OptiplexNow/issues/154). On October 23 the corrected legacy NVIDIA producer caps passed real owner Steam Create/Join, RE2R gameplay, and managed Stop/relaunch on the reference host while preserving the local desktop. The earlier missing-caps diagnosis is supported but not isolated as the only cause. **The GUI, authenticated broker, fresh-client, multi-device and clean-host gates remain open.**

## Pillar 2: personal video

**User story:** After connecting to the approved NOW host, the client opens Videos and reaches the right authorized Jellyfin service without knowing its URL.

Acceptance:
- [ ] GUI can provision Jellyfin and select owned library roots on a clean supported host, or safely adopt an existing Jellyfin without modifying unrelated containers and data.
- [ ] The host provides an authenticated, host-bound service descriptor to approved clients; client Videos opens the correct service without manually supplying a URL, public DNS, or port forwarding in the normal flow.
- [ ] Jellyfin's own account/session and library access controls remain in force. No Jellyfin administrator secret is included in shareable client settings.
- [ ] At least one real video plays with sound from an approved client while gaming/server desktop and download networking remain available.
- [ ] Service restart, address change and temporarily unavailable media yield understandable status and recovery without destroying libraries.

Critical issues: [#171](https://github.com/SteezyMode/OptiplexNow/issues/171), [#148](https://github.com/SteezyMode/OptiplexNow/issues/148).

## Pillar 3: private downloads and protected files

**User story:** The owner uses NOW to queue an authorized download, see where it landed on the real host, open that folder, organize media within their ordinary Linux account permissions, and then play it through Jellyfin. The downloader alone is VPN-isolated; gaming and video work independently. Invited viewers are not enrolled in Private Alpha 1.

Acceptance:
- [ ] GUI installs or safely adopts supported qBittorrent/VueTorrent + Gluetun + bring-your-own VPN configuration on the supported host without taking over the host network.
- [ ] Only designated download service traffic uses the VPN; actual public exit IP is independently verified.
- [ ] On a deliberately interrupted VPN tunnel, downloader transfers stop safely and do not leak through host routing. During failure, approved games, Jellyfin, remote access and host networking remain reachable.
- [ ] Owner/admin can search, choose a result and choose its destination before adding it, including **any nested genre folder within the owner's approved media-storage volumes**; preset categories and favorite folders must be optional shortcuts, not the only choices. Reuse native VueTorrent “Append to queue” save-path controls when compatible. On plugins that cannot be imported, explain the limitation rather than silently download elsewhere. Server-authorized browsable media roots, host-to-container path mappings, and viewer denial are essential for safe file-management; the refined per-search-result picker is a post-core-alpha UX improvement (#189).
- [ ] Server setup detects and preserves existing qBittorrent search plugins or provisions Python plus owner-approved, content-pinned search plugins automatically on a fresh host; verifies plugin operation, supports recovery and cannot install unreviewed Python engines silently. Track #187.
- [ ] Owner/admin can inspect, move and organize files **only within server-enforced permitted roots**. Avoid unrestricted SFTP or arbitrary client-supplied filesystem paths in the ordinary interface.
- [ ] Viewer/member can stream permitted media but cannot administer downloads, files, VPN, or host services via UI, direct URL or forged request. No downloader admin interface is exposed publicly.
- [ ] Downloads survive reboots and transient failures without data loss; show accurate status (VPN container health alone is not proof of egress or safety).

Tracking: [#137](https://github.com/SteezyMode/OptiplexNow/issues/137), [#98](https://github.com/SteezyMode/OptiplexNow/issues/98), [#37](https://github.com/SteezyMode/OptiplexNow/issues/37).

## Cross-cutting release gates

- [ ] Host/Client role choice and first-run path are understandable. Normal installation, enrollment and service setup are graphical, with clear authentication and approvals.
- [ ] Privileged actions occur only through trusted host-side authorization, not arbitrary SSH/Docker/sockets exposed to every paired client.
- [ ] One owner/admin is physically tested across at least two owner-operated devices. Non-owner member roles are deferred; a later member-facing release requires independently tested server-enforced privilege isolation.
- [ ] Reboot, reconnection, expected service outages, partial provisioning, upgrades and rollback leave unrelated owner data intact.
- [ ] Fresh client and independent disposable fresh-host setup are observed, hardware/software versions recorded, and at least one tester follows instructions without a developer shell.
- [ ] Installer/release artifacts are immutable, reproducible enough to verify by SHA256, and correspond to exact accepted source. There is a documented way to stop/remove NOW-managed components without wiping user media or game data.
- [ ] CI, mock integration, real upstream protocol, physical host, physical client and tester acceptance evidence are differentiated. **No release is called accepted until the physical checks pass.**

## Current blockers and next acceptance order (October 26)

**v1.20.0 Closed Beta publication is not Private Alpha 1 acceptance.** The work remaining is completion and validation of the original three product journeys, not broad architectural refactoring.

1. **P0—First-time owner enrollment and honest Games authority (#191, #192):** The private iPhone owner page and signed Wolf identity candidate were physically verified. Both real approval attempts used an already-authorized restricted key and were correctly denied; a genuine unapproved restricted credential must still be approved and verified via host restricted SSH, with wrong-phone/replay/expiry tests. An authorized device should show `ALREADY AUTHORIZED` (CI-tested, not physically installed). Direct Wolf-published Steam currently bypasses NOW's separate restricted credential; explicitly document/decide the one-owner access boundary before allowing independent testers.
2. **P0—Games fresh client (#154, #152, #76):** Re-run managed Steam/gamepad/audio/video on the v1.20.0 packaged client, confirm host desktop independence, reconnect/lease cleanup and session single-writer safety. Prove no manual terminal/PIN loop after initial approval and that existing owner data persists across reboot. Existing-host gameplay is positive supporting evidence, not a clean install pass.
3. **P0—Videos zero-URL discovery (#171, #148):** From an authorized *clean* client, click Videos and open the actual host Jellyfin login/library without typing an address; verify playback, Jellyfin native auth, wrong-host denial and restart/offline recovery. Preserve existing Caddy/Jellyfin configuration.
4. **P0—Private Downloads VPN/files (#137, #186, #187, #188, #190):** Establish owner-only VueTorrent/search/queue behavior; verify true VPN egress, stop-on-tunnel-loss/no leak while Games/Videos continue; browsing and file operations constrained to owner-approved roots; safely adopt or provision approved downloader + search plugins on clean host without moving existing content.
5. **P0—Turnkey integrated clean-host/client install and recovery (#98, #76):** On separate disposable compatible GPU hardware, prove install/adopt → approved client → real streamed game, Jellyfin and downloads; preserve owner Steam/Jellyfin; test reboot, failure recovery, uninstall/rollback and package checksums. Record a non-developer walkthrough and elapsed time (15-min target for first game stream only).

**Deferred beyond Private Alpha 1:** member accounts and separate Steam libraries, Windows binaries/hosting, email/hosted auth, subscription VPN reselling, broader GPU/OS support, design polish and further main.c refactoring unless required by a concrete blocker.

[Developer handoff, next commands and physical status](HANDOFF-2026-10-26.md) · [exact QR safety notes](OWNER-QR-ALPHA.md) · [issue tracker](https://github.com/SteezyMode/OptiplexNow/issues/137)

## Excluded from this release

Separate Steam accounts per member; simultaneous unrelated game tenants; pooled installations; Windows hosting and Windows client builds; custom single-sign-on provider; email approval infrastructure; paid/white-label VPN; music, books, comics; Plex adapter; customized Wolf/Moonlight/GStreamer replacements; in-stream overlays; Studio management; broad tray/UI redesign.

**Rule:** Work advances the accepted end-user workflows, fixes a safety/reliability blocker, or waits.
