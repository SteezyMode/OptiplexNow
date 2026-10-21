# Product direction

**Authority:** The vision, priorities and sequence live here. [Public-alpha contract](PUBLIC-ALPHA.md) defines the three required end-to-end workflows and role enforcement; [issue #137](https://github.com/SteezyMode/OptiplexNow/issues/137) tracks their implementation. [Current status](CURRENT-STATUS.md) records implemented, released and physically verified features. [Private client beta](BETA-ACCEPTANCE.md) and [Host installer](HOST-INSTALLER.md) cover narrower evidence. Do not treat them as proof of public-alpha completion.

**Name:** OptiPlex NOW is an internal development codename. The commercial product will have a different name.

## The promise

**Make your own entertainment server, without becoming a server administrator.**

One compatible host computer, with one simple client/server installation experience, lets an approved person play games and access personal media remotely. The owner's computer remains usable as a normal PC. Technical work such as network enrollment, streaming, containers, VPN routing, service health and recovery belongs behind the application.

**Three essential public-alpha workflows:** independent game streaming, Jellyfin video, and **Private Downloads** with qBittorrent behind an isolated VPN gateway. All three are **required for public-alpha acceptance**, while end users may select which services to install. This is a self-hosted system for personally controlled content and computing, not an entertainment catalog.

In particular, the **download VPN does not take over the server's network**. Only expressly selected download apps route through it. Jellyfin, Wolf, ordinary desktop activity and authorized remote access remain outside that tunnel. Downloads fail closed when the tunnel fails. This is service-level network independence, **not** a guarantee that heavy workloads cannot share/compete for disk, CPU or internet bandwidth.

File organization, download search, queue operations and per-item download destinations are **owner/admin-only**. Invited members may browse and play content they are authorized to see; they do not receive management access. Real service-side authorization is mandatory, not just different tabs.

**Target:** roughly 15 minutes from starting NOW installation on two supported, OS-ready PCs to a working authenticated game stream, with no required terminal steps. This excludes OS installation, game downloads, library import and purchase of VPN service. A genuinely easy unified login and approved-device experience is the goal; do not equate it to completed cross-service single sign-on.

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
| **Existing-host closed client beta** | GUI launch, Moonlight/Tailscale/SSH onboarding, Videos/Downloads links, SFTP and diagnostics | Published v1.18.0; October 21 physical Mint client run partially passed, game streaming and UX/persistence remain open |
| **Clean-host gaming technical alpha** | Start a NOW-managed Wolf instance and prove independent video/audio/controller stream on real hardware | Development installer exists; physical end-to-end test and recovery pending |
| **Public alpha: three pillars** | Guided gaming, Jellyfin and VPN-isolated qBittorrent, plus admin downloads/files and restricted viewers | **Product requirement**, not implemented as a single supported installation; [acceptance](PUBLIC-ALPHA.md) |
| **Product hardening** | First-run usability, owned-service repair, upgrades, removal, diagnostics, real external testers | Not yet accepted |
| **Windows client** | Access the same Linux host without requiring a Linux client | Planned, not implemented |
| **Windows host** | Comparable independent game session on a Windows PC | Longer-term feasibility/licensing work |
| **Optional modules/business** | Music, books, comics, referrals and potentially an optional branded VPN | Research only; none is a prerequisite for public alpha |

**Video onboarding requirement:** For public alpha, an ordinary owner should not need to know a Jellyfin URL or have Jellyfin preinstalled. NOW must offer guided clean-host Jellyfin provisioning or safe existing-server connection and propagate an authorized endpoint to approved clients. Manual URL entry remains advanced-only. This is tracked by [#148](https://github.com/SteezyMode/OptiplexNow/issues/148) and is distinct from the v1.18.0 wizard persistence defect [#147](https://github.com/SteezyMode/OptiplexNow/issues/147). The [October 21 physical beta report](QA-MACBOOK-2026-10-21.md) records what was actually tested.

**Scope boundary:** the current Wolf host pilot is **not** a Jellyfin or Gluetun/qBittorrent installer. The reference PC's media/download/VPN stack is user-built. NOW currently opens its URLs and offers SFTP/health diagnostics; there is no verified native qBittorrent admin interface, server-side member role enforcement, automatic VPN kill-switch certification or one-login experience.

## Immediate work order

1. **Test independent gaming on clean physical hardware**, including GPU encoder, remote input/audio, host desktop independence, reconnection, reboot and failed-install handling. Protect the working reference server.
2. **Validate real media + isolated downloading against the known-working host**: remote Jellyfin playback while another authorized download is queued; actual VPN egress and fail-closed conditions; usable file paths; impact of bandwidth/disk contention.
3. **Build the smallest safe, graphical host modules** for Jellyfin and a customer-supplied VPN with Gluetun/qBittorrent. Native download queue/search/per-item approved directory selection and owner-only file access must work, even if existing upstream players and media UIs remain in use.
4. **Prove owner/member enforcement** for playback versus downloader/files/configuration, including direct-request bypass attempts. Keep custom cloud SSO and universal user desktops out of scope.
5. **Run fresh-user installation tests on a narrow supported matrix**. Measure setup time, errors, recovery interventions and support hours, then decide whether it is viable to commercialize. Do not publish public-alpha claims prematurely.

**Later VPN business research:** A possible **$7/month optional VPN** covering protected server downloads and other personal devices could be explored via legitimate affiliate or wholesale partners. No provider contract, device allowance, $7 pricing or profit is confirmed. Bring-your-own VPN remains fully supported; white-label billing and provisioning must not delay public alpha.

## Compatibility and review boundaries

Preserve existing client settings (`~/.config/optiplex-desk/config.ini`), `.onp` presets, `.onb` encrypted backups, saved URLs, tray preferences and Moonlight identity. Follow [Contributing](../CONTRIBUTING.md) and [Architecture](application-design.md) for modular code ownership, CI, privilege boundaries and narrow changes. Do not rewrite the application solely to match the roadmap.

No ownership of Wolf, Moonlight, Jellyfin, qBittorrent, Gluetun, customer games or media rights is implied. Streaming brand comparisons are shorthand for convenience, not provider affiliation or access to their catalogs. A VPN changes network routing; it does not make downloading any particular content lawful or guarantee anonymity.
