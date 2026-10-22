# Product direction

**Authority:** This file owns product direction and long-term phases. **The active release milestone is [Private Alpha 1](PRIVATE-ALPHA.md)**, with three required end-to-end workflows and physical acceptance. [Public alpha](PUBLIC-ALPHA.md) is a separate later contract; [issue #137](https://github.com/SteezyMode/OptiplexNow/issues/137) tracks the broader three-pillar work. [Current status](CURRENT-STATUS.md) distinguishes implementation, tests and releases. The older [client beta](BETA-ACCEPTANCE.md) and technical [Host installer](HOST-INSTALLER.md) provide narrower evidence, not release acceptance.

**Name:** OptiPlex NOW is an internal development codename. The commercial product will have a different name.

## The promise

**Make your own entertainment server, without becoming a server administrator.**

One compatible host computer, with one simple client/server installation experience, lets an approved person play games and access personal media remotely. The owner's computer remains usable as a normal PC. Technical work such as network enrollment, streaming, containers, VPN routing, service health and recovery belongs behind the application.

**Three essential public-alpha workflows:** independent game streaming, Jellyfin video, and **Private Downloads** with qBittorrent behind an isolated VPN gateway. All three are **required for public-alpha acceptance**, while end users may select which services to install. This is a self-hosted system for personally controlled content and computing, not an entertainment catalog.

In particular, the **download VPN does not take over the server's network**. Only expressly selected download apps route through it. Jellyfin, Wolf, ordinary desktop activity and authorized remote access remain outside that tunnel. Downloads fail closed when the tunnel fails. This is service-level network independence, **not** a guarantee that heavy workloads cannot share/compete for disk, CPU or internet bandwidth.

File organization, download search, queue operations and per-item download destinations are **owner/admin-only**. Invited members may browse and play content they are authorized to see; they do not receive management access. Real service-side authorization is mandatory, not just different tabs.

**Target:** roughly 15 minutes from starting NOW installation on two supported, OS-ready PCs to a working authenticated game stream, with no required terminal steps. This excludes OS installation, game downloads, library import and purchase of VPN service. A genuinely easy unified login and approved-device experience is the goal; do not equate it to completed cross-service single sign-on.

**Immediate Games integration step within Private Alpha 1:** On the existing reference server, the owner can authorize multiple **owner-operated devices** to open the **same explicitly approved owner Steam workspace** and existing Jellyfin service without terminal commands, manual symlinks or repeated device pairing. A trusted household device may be delegated access to the owner's workspace **only by deliberate owner approval**. This beta is **not** a general invitation feature for colleagues or unrelated people. A new NOW member must never inherit owner Steam, host files or SSH rights merely from pairing. Do not rebuild, replace or migrate the working host stack. This is a closed-beta acceptance target, not public-alpha readiness.

Linux hosts/clients are first. Windows **client** builds are planned; Windows **host** support is a later technical and licensing project, particularly for sessions independent of the host display. Music (including DroppedNeedle), books, comics and extensive user-specific desktops are optional future research, not public-alpha prerequisites.

## Engineering and product principles

1. **One path for ordinary people.** Guided installation, enrollment, clear status, safe repair/removal and readable recovery. No Docker, Tailscale, SSH, certificate or port-forwarding tutorials as the normal workflow.
2. **Independent services.** Game, video and downloads are separately selectable and independently recoverable. Neither the commercial VPN nor a billing service may interrupt ordinary access to the user's computer, Jellyfin or Wolf.
3. **Protect the owner.** Never adopt, overwrite, delete or restart unrelated host services without informed approval. Keep managed data/versioning and least-privilege administrative operations separate.
4. **Server-enforced roles.** One owner/admin can manage downloads/files/services; restricted viewers can only use approved playback/game capabilities. Verify bypass attempts against direct upstream URLs, not merely NOW GUI buttons.
5. **Measured truth.** A running Docker container, successful CI test or green VPN health badge does not prove actual streaming, VPN public egress, fail-closed behavior or an accepted fresh setup.
6. **Upstream first.** Integrate supported Wolf/Moonlight, Jellyfin, qBittorrent, Gluetun and optional VPN-provider interfaces. Do not build custom streaming, identity or torrent engines without a demonstrated necessity.
7. **Practical low-maintenance product.** Prefer a small supported hardware matrix and reproducible recovery over speculative features, forced subscriptions or general-purpose homelab management.

## Phases and current evidence

| Phase | Purpose | Status |
| --- | --- | --- |
| **Existing-host closed client beta: household validation** | Two authorized household clients reach the owner's established Steam and Jellyfin services; preserve existing infrastructure and make Games/Videos one-click after authorization | Published v1.18.0; October 21 Mint beta partially passed. October 22 MacBook Steam launched **after a manual server-side Steam-state symlink**, proving streaming but **not** zero-terminal onboarding; #154 remains open |
| **Clean-host gaming technical alpha** | Start a NOW-managed Wolf instance and prove independent video/audio/controller stream on real hardware | Development installer exists; physical end-to-end test and recovery pending |
| **Private Alpha 1: three pillars** | Guided independent games, Jellyfin video and VPN-isolated qBittorrent, plus protected admin downloads/files and restricted viewers | **Active release gate**, not yet delivered as a supported installation; [acceptance](PRIVATE-ALPHA.md) |\n| **Public alpha: broader distribution** | Expand compatibility and release confidence after Private Alpha 1 passes | Future release milestone; [contract](PUBLIC-ALPHA.md) |
| **Product hardening** | First-run usability, owned-service repair, upgrades, removal, diagnostics, real external testers | Not yet accepted |
| **Windows client** | Access the same Linux host without requiring a Linux client | Planned, not implemented |
| **Windows host** | Comparable independent game session on a Windows PC | Longer-term feasibility/licensing work |
| **Optional modules/business** | Music, books, comics, referrals and potentially an optional branded VPN | Research only; none is a prerequisite for public alpha |
| **Deferred shared-server gaming** | Separate Steam accounts and simultaneous isolated sessions, with an optional central Steam installation pool so licensed users do not download the same game twice | **Parked**, pending profile isolation and physical tests; [#153](https://github.com/SteezyMode/OptiplexNow/issues/153) and [#157](https://github.com/SteezyMode/OptiplexNow/issues/157) |
| **Deferred private workspaces** | Optional user XFCE desktops, personal non-Steam games, suitably licensed shared files, private media/music/download mini-servers | **Parked**, not an alpha or closed-beta deliverable; [#155](https://github.com/SteezyMode/OptiplexNow/issues/155) |

**Video onboarding requirement:** For public alpha, an ordinary owner should not need to know a Jellyfin URL or have Jellyfin preinstalled. NOW must offer guided clean-host Jellyfin provisioning or safe existing-server connection and propagate an authorized endpoint to approved clients. Manual URL entry remains advanced-only. This is tracked by [#148](https://github.com/SteezyMode/OptiplexNow/issues/148) and is distinct from the v1.18.0 wizard persistence defect [#147](https://github.com/SteezyMode/OptiplexNow/issues/147). The [October 21 physical beta report](QA-MACBOOK-2026-10-21.md) records what was actually tested.

**Scope boundary:** the current Wolf host pilot is **not** a Jellyfin or Gluetun/qBittorrent installer. The reference PC's media/download/VPN stack is user-built. NOW currently opens its URLs and offers SFTP/health diagnostics; there is no verified native qBittorrent admin interface, server-side member role enforcement, automatic VPN kill-switch certification or one-login experience.

## Locked delivery order: functionality before expansion

This order controls **engineering implementation sequence**, not just documentation priority. Preserve the three-pillar public-alpha product vision while finishing one workflow at a time.

| Gate | Deliverable | Required evidence | Exclusions |
| --- | --- | --- | --- |
| **P0 Personal Server Games** | Clean approved owner client, one-click launch to the *existing persistent* Steam home, playable game, host desktop independent, safe reconnect/restart | Repeat from a truly fresh client **without terminal steps, Wolf UI selection or manual symlinks**; tested video/audio/input and concurrent-session handling | Independent member Steam accounts, pooled game installations |
| **P1 Videos** | Reliable authorized discovery of owner's existing Jellyfin service with no URL input; safe new Jellyfin setup/adoption before release sign-off | Fresh client automatic discovery, login, real playback, reboot and clean-host service setup | Plex integration, custom video transcoding/frontend |
| **P2 Private Downloads + Files** | Owner-only qBittorrent/VueTorrent queue, chosen safe download paths, protected file management and VPN-only downloader network | Real VPN egress, deliberate tunnel-failure kill-switch, admin-only permissions and unchanged Wolf/Jellyfin/host routing | White-label VPN, extra guest service instances |
| **P3 Turnkey provisioning and restricted viewing** | Install/adopt Wolf, install or safely adopt Jellyfin, provision downloader/VPN, graphical recovery, plus server-enforced media-only member permissions | Clean disposable host, independent unfamiliar tester, no shell, negative permission tests | Private member Steam sessions or shared media pools |
| **Later Shared Server** | Separate authorized people, independent Steam profiles/saves, optional pooled games/media, private service instances | Dedicated isolation/revocation/concurrency acceptance | **Not a prerequisite to P0–P2** |

The first three gates may be tested as **existing-host integration evidence** with working manually prepared services. **They do not by themselves meet [Private Alpha 1](PRIVATE-ALPHA.md)**: clean disposable-host GUI provisioning/adoption, restricted viewer permissions and complete recovery are also required before the release. Develop on the existing host without destructive migration, then validate managed installation on separate hardware. Do not advance to general multi-user Steam hosting to achieve minimum media-only playback permissions.

**Identity constraint from day one:** [Personal Server is one owner in the future Shared Server schema](application-design.md#personal-server-identity-and-access-contract). A device is not a Steam account; any approved owner device resolves the same owner workspace. No new colleague or member can access the owner's Steam credentials by simply connecting. Existing one-user shortcuts must remain upgradeable to server-enforced per-principal grants later.

**Media integration direction:** Jellyfin remains the first backend. NOW may provide guided provisioning, a branded NOW-facing interface backed by Jellyfin APIs and optional adapters to existing Plex or other servers, without forking media playback/transcoding. Preserve original service credentials and accounts; do not promise Plex white-label redistribution or proprietary rebranding rights. Review Jellyfin GPL obligations and official trademarks before distributing modified binaries/UI. Detailed implementation remains **after P0–P2**.

## Immediate work order

**Release objective: [Private Alpha 1](PRIVATE-ALPHA.md).** Finish user-visible workflows in this order, preserve the working reference host and do not pursue multiple parallel speculative infrastructure tracks.

1. **Games P0:** Solve the physical Wolf named-lobby initialization problem, confirm one persistent owner Steam home across approved devices and integrate authorized Create/Join with the actual NOW Games action. Verify playable game, input, audio, independent host desktop, reconnect and single-writer safety. [#154](https://github.com/SteezyMode/OptiplexNow/issues/154). Do not represent the older manual symlink workaround as a product feature.
2. **Video P1:** Ensure approved clients discover the correct Jellyfin endpoint automatically and play real content without a URL prompt. Then add safe graphical clean-host provisioning or existing-server adoption. [#171](https://github.com/SteezyMode/OptiplexNow/issues/171), [#148](https://github.com/SteezyMode/OptiplexNow/issues/148).
3. **Downloads/Files P2:** Prove an owner-only qBittorrent/Gluetun workflow on an adopted host, including reviewed search providers, constrained destinations, actual VPN egress, deliberate tunnel interruption, unchanged other services, and denied viewer/admin bypasses. Then support guided provisioning. [#137](https://github.com/SteezyMode/OptiplexNow/issues/137).
4. **Integration P3:** One Host/Client graphical setup across these three opt-in components. Support an explicitly narrow initial Linux hardware matrix, safe recovery/upgrade, and a separate clean disposable-host installation. Do not overwrite existing services. [#98](https://github.com/SteezyMode/OptiplexNow/issues/98).
5. **Release sign-off:** One unfamiliar tester, physical test evidence for the entire three-pillar system, explicit permission-negative tests, recorded setup/first-stream time, and an immutable check-summed installer. No beta or alpha label based on CI alone.

**Scope freeze:** No Windows host, separate member Steam accounts, pooled game installations, music/books/comics, commercial VPN billing, new UI embellishments or unrelated Studio work in this milestone. See [Private Alpha 1](PRIVATE-ALPHA.md).

## Deferred shared-server gaming: pooled Steam installations

**Future differentiator, not a public-alpha requirement.** Several authorized people could use one gaming host through **separate Steam accounts and independent Wolf sessions**, each with their own saves and settings. As a further option, NOW could offer a **centrally managed pool of installed Steam games** so eligible users do not each need to download and store the same game files.

**Example:** The server owner and a household member **each own a Steam license for Resident Evil 2**. The owner already has RE2 installed on the host. The member connects from a thin client, signs into their **own server-side Steam environment**, and plays from that **same physical game installation**, with their **own saves, settings, Steam userdata and Proton environment**. The intended result is **one copy of the core game files, two separate accounts**, not one shared Steam login. They might also run **two independent copies of the game simultaneously** if their two licenses, the game and the host's actual GPU/CPU/encoding capacity permit it. Steam Families is **not required** when both accounts own the game; license entitlement is separate from file storage.

**Engineering constraints:** Steam library registration and manifests must work across distinct profiles. Updates to shared game files require central coordination; writable saves, `steamapps/compatdata`, shader caches and user-specific files must remain isolated. Don't mount a full read/write Steam library into multiple unrelated players' containers. Games or launchers that modify installation files, enforce special DRM, or have other incompatibilities may need private installations. Independent Steam ownership alone does not make pooling or concurrent play universally guaranteed.

This is a **post-alpha testable feature**, tracked in [#157](https://github.com/SteezyMode/OptiplexNow/issues/157), dependent on securely isolated member gaming profiles [#153](https://github.com/SteezyMode/OptiplexNow/issues/153). First prove a single shared installation with two licensed users and separate saves, then test simultaneous lightweight sessions and update safety. Do not touch the current owner's working Steam installation to prototype it.

## Deferred expansion: optional private player spaces

**Ideas worth retaining, not committing to build in alpha.** The immediate product remains an uncomplicated existing-host games-and-video client/server. Turning every player into a tenant with general-purpose services would increase identity, filesystem, networking, billing/support and security complexity. Track detailed feasibility in [#155](https://github.com/SteezyMode/OptiplexNow/issues/155) and separate member Steam environments in [#153](https://github.com/SteezyMode/OptiplexNow/issues/153).

- **Optional per-player XFCE desktop:** a private, deliberately restricted workspace for game installs, mods and file management. Not a required first-run screen. Its container is separate from the Wolf Steam container; a controlled, member-owned games mount can make files available to both, but does not automatically transplant dependencies or launchers.
- **Personal non-Steam games:** DRM-free and other legally usable titles installed privately, with optional Steam non-Steam shortcuts where tested. An owner-approved shared files pool might avoid duplicate game downloads **only where licenses permit**. Steam Families applies to eligible Steam licenses; it does not authorize redistribution or sharing of arbitrary non-Steam games.
- **Private and pooled media/music libraries (optional):** a user may be granted **viewing access to selected Jellyfin libraries** without any Steam account, gaming resources, download permissions or NOW administrative access. Jellyfin already supports per-user library permissions; this does **not** require a separate Jellyfin instance. Later, separate members may keep **private movies/music** alongside an **explicitly opt-in shared pool** of permitted content. A Jellyfin library can index multiple mounted folder paths; private folders and the pooled directory need not be identical, but each media type should follow supported organization conventions. Default is private; the owner and contributor must explicitly approve pooling. Maintain independent watched state, access permissions and storage quotas, and distinguish server admin visibility from privacy between ordinary members.
- **Private media/music mini-server:** still later, an authorized user could operate an isolated personal Jellyfin instance, optionally with its own VueTorrent/qBittorrent-style download interface and verified VPN-isolated downloader. An owner-approved pooled folder could be mounted **read-only** into multiple media instances, while each person's private folders and metadata stay separate. The XFCE desktop would **manage** the space; background media/download services must remain active when that desktop is closed. Isolation, quotas, transcoding contention, VPN fail-closed behavior, copyright/content permissions and safe shared-file updates require independent testing. None of this should replace the existing owner's Jellyfin/download setup.
- **Safety boundary:** new services must be explicitly opted into, have server-enforced identities and mount permissions, and **never alter the owner's existing Steam profile, game folders, Jellyfin instance, downloader, VPN or host files by default**. The existing owner XFCE/Steam RW host mounts are not templates for invited members.

**Promotion gate:** revisit these ideas only after the single-owner/multi-device flow is reliable without terminal work, and at least one independently isolated additional member profile is proven. A user-requested shared server must not complicate the default personal-server onboarding.

**Later VPN business research:** A possible **$7/month optional VPN** covering protected server downloads and other personal devices could be explored via legitimate affiliate or wholesale partners. No provider contract, device allowance, $7 pricing or profit is confirmed. Bring-your-own VPN remains fully supported; white-label billing and provisioning must not delay public alpha.

## Compatibility and review boundaries

Preserve existing client settings (`~/.config/optiplex-desk/config.ini`), `.onp` presets, `.onb` encrypted backups, saved URLs, tray preferences and Moonlight identity. Follow [Contributing](../CONTRIBUTING.md) and [Architecture](application-design.md) for modular code ownership, CI, privilege boundaries and narrow changes. Do not rewrite the application solely to match the roadmap.

No ownership of Wolf, Moonlight, Jellyfin, qBittorrent, Gluetun, customer games or media rights is implied. Streaming brand comparisons are shorthand for convenience, not provider affiliation or access to their catalogs. A VPN changes network routing; it does not make downloading any particular content lawful or guarantee anonymity.
