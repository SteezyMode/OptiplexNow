# Public alpha: product and acceptance contract

**Authority:** This document defines the **intended public alpha**, not the existing closed client beta or the current Wolf-only host installer. [Product direction](PRODUCT.md) owns strategy, [Current status](CURRENT-STATUS.md) owns implementation evidence, [Private client beta](BETA-ACCEPTANCE.md) and [Host installer](HOST-INSTALLER.md) own their narrower test tracks.

OptiPlex NOW is an internal development codename, **not the commercial brand**.

## The product

One personally owned computer becomes a private entertainment server: **independent remote games, video streaming, and VPN-isolated downloads**. The owner installs a host application and uses a client application from another supported device, at home or away. Normal users should not need to understand Tailscale, Docker, Wolf, Moonlight, Jellyfin, qBittorrent or Gluetun.

One coherent graphical setup should install or configure selected services, connect an approved client, show status, and provide understandable recovery. Modules should be selectable independently, although all **three workflows must be demonstrated for public-alpha sign-off**. The server's physical desktop remains independently usable. The user supplies hardware, content and compatible VPN access.

**First-stream target:** approximately 15 minutes from starting NOW installation on two supported, OS-ready computers to an authenticated remote game stream. OS installation, game downloads, building a media library, and acquiring VPN credentials are excluded. This is an **unverified objective**, not a guarantee or an assertion that all three server modules can be provisioned in 15 minutes.

The eventual ideal is a **single sign-in and approved-device experience**, including easy access to the owner's permitted servers. Public alpha must provide a coherent setup and authorization flow but may use separate, clearly explained service credentials while securely unified identity is unfinished. It must not claim single sign-on, silently bypass pairing or hand out administrator credentials to members. A NOW-hosted website is not necessary to operate the personally hosted server; locally/private-network hosted service interfaces can remain implementation details.

## Three required public-alpha pillars

### 1. Games: independent sessions

- Install or non-destructively connect to a compatible Wolf/Moonlight host through a guided flow.
- Start a real game from a separate authorized device with functional video, audio and controller input.
- The host computer's **physical monitor, desktop, keyboard, mouse and normal audio remain usable** without being taken over by the remote game.
- A previously approved client reconnects after network interruption or host reboot without needless re-pairing.
- Surface GPU/encoder failures and resource limitations. Separate game sessions still share physical GPU, CPU, memory and bandwidth.
- Explicitly distinguish a single independent game session from **secure multi-user workstation isolation**, which remains additional research.

### 2. Video: private library

- Guided setup of Jellyfin for a compatible clean host, **or** a non-destructive connection to an already configured server. New owners are not expected to know what Jellyfin is or install it before starting NOW.
- **No manual service URL required on the ordinary path.** Owner selects **Set Up My Video Library** or **Use Existing Jellyfin**. For a new installation, NOW safely provisions the managed service and lets the owner choose library folders. For an existing service, it obtains the correct instance by verified, owner-confirmed discovery without changing unrelated deployments. Manual HTTPS URL entry remains an **advanced fallback**, not onboarding's main input.
- Once an owner approves the service, eligible NOW clients learn its permitted address via trusted server/client configuration. **Do not require public DNS, reverse proxy or port forwarding by default**; retain proper Jellyfin authentication, client approval and TLS/network boundaries. Do not send Jellyfin administrator credentials in shareable presets. Track this public-alpha requirement in [#148](https://github.com/SteezyMode/OptiplexNow/issues/148).
- Owner selects approved library folders and can organize files using authenticated, bounded operations.
- Authorized members can browse and play the media available to their account; server file administration is **not** implied by media playback permission.
- Stream actual video remotely while the host computer remains usable and other NOW services are independently reachable.
- Reconnect and restart without recreating media accounts and libraries. Jellyfin handles playback and media-account permissions; NOW manages the supported installation and access experience.

### 3. Private Downloads: isolated VPN and remote queue

- Configure a supported qBittorrent service behind a dedicated Gluetun/WireGuard or OpenVPN gateway, or non-destructively adopt a verified existing arrangement. Public alpha permits **bring-your-own compatible VPN**; no NOW-sold subscription is necessary.
- **Only designated download traffic traverses the commercial VPN.** Jellyfin, Wolf, host desktop networking, local administration and private remote access remain outside that tunnel. Do not route the host's whole internet connection through it.
- Verify the downloader's actual public exit IP and deliberately interrupt the tunnel to demonstrate **fail-closed transfers**. A green Gluetun Docker health badge is not sufficient. Unrelated services must remain reachable through a VPN failure.
- From an authorized admin session, use supported qBittorrent queue controls: add lawful download links or torrent files, search through **reviewed, explicitly enabled search providers**, see progress, pause/resume and remove. Search plugins may run executable code; never blindly install arbitrary plugins or distribute unauthorized media indexes.
- **Choose a destination for each new download** from owner-approved server-side paths. Support staging, media folders and authorized moves/organization. Enforce mounted-volume and filesystem restrictions; never treat a client-supplied string as an unrestricted server path.
- While a member watches Jellyfin, an admin can queue a new download. Video and game network access must remain independent of VPN state. Shared disk, CPU and internet capacity can still cause contention; test with rate limiting rather than promising zero performance impact.
- Manage credentials securely, avoid exposing Docker-admin sockets or downloader credentials to viewers, and do not expose the qBittorrent admin endpoint publicly.

## Permissions: owner/admin versus member/viewer

| Action | Owner/admin | Member/viewer |
| --- | --- | --- |
| Watch permitted videos and browse permitted libraries | Yes | Yes |
| Start gaming session | Yes | Only when specifically authorized |
| Manage download search, additions, queue, paths and deletions | Yes | **No** |
| Browse/move/upload/rename/delete server files using NOW's management interface | Yes, inside permitted roots | **No** |
| Configure Jellyfin folders, network/VPN, approved devices and server lifecycle | Yes | **No** |
| See host/VPN/download secrets or unrestricted SSH/Docker administration | Never expose raw secrets without explicit authorized administrative need | **No** |

**Server-enforced boundary:** hiding an admin button in the client is not authorization. Any NOW endpoint or upstream service reachable by members must reject attempts to manage download queues, change paths, call qBittorrent directly, browse SFTP, manipulate Docker/Gluetun or overwrite host files. Give members only the streaming credentials/permissions they need. Validate a second account/device by deliberately attempting forbidden operations, including direct service URLs.

**Minimum alpha identity scope:** one owner/admin and at least one restricted playback member, with explicit per-device approval and revocation through supported components. A custom global identity provider, emailed approvals, cross-provider single sign-on and mutually untrusted multi-tenant isolation are **not required** for this alpha. Membership to a private network is not proof of admin authority.

## Physical public-alpha sign-off

- [ ] New supported Linux host plus clean client complete a graphical owner-guided configuration for **all three selected modules**, without entering terminal commands during the supported path. Record total time and separate first-stream time.
- [ ] A remote game actually runs while the physical host desktop remains usable; video, gamepad/audio and reconnection work.
- [ ] An owner without preinstalled Jellyfin can set up Video graphically, and an owner with existing Jellyfin can select it without destruction. A clean approved client discovers the authorized Video endpoint without typing a web address or requiring public DNS.
- [ ] Jellyfin streams from an owner-chosen library over the private remote connection, including while an admin starts another permitted download.
- [ ] qBittorrent uses the VPN egress, stops traffic when the VPN fails and never changes the route/availability of Jellyfin, gaming or host administration.
- [ ] Admin can search from reviewed providers, manage a download, choose a per-item approved directory, and subsequently inspect/move the file with a protected file-management path.
- [ ] Restricted playback member streams permitted content but **cannot** access download administration, file-management endpoints, VPN settings or server administration, including by direct URL or forged request.
- [ ] OS/host reboot, client reconnection, expected service failures and install recovery preserve unrelated host data and surface actionable errors.
- [ ] At least one unfamiliar outside tester completes the supported setup and workflows without developer shell intervention. Record versions, hardware, exact steps, failures and corrective action.

**Development order:** deliver **Personal Server Games first**: fresh approved owner device, durable existing Steam profile, independent real game stream, safe reconnect and no terminal or per-device symlink. Next prove the owner's **existing Jellyfin** Videos link survives first-run setup, restart and upgrades and plays actual media. Third, prove **owner-only VPN-isolated qBittorrent/VueTorrent downloads and safe file operations** on the existing compatible host, including fail-closed VPN and negative admin tests. These three successful existing-host integrations are an **integration alpha**, not proof of turnkey public-alpha readiness. **Only afterward**, validate clean-host Wolf installation, new Jellyfin library provisioning or safe adoption, downloader/VPN provisioning, recovery and **minimal server-enforced restricted playback membership**. Full public-alpha sign-off still requires all physical checklist items above. Independently isolated *member Steam gaming*, game/media pooling and private per-member media servers remain deferred until afterward. Follow [locked gates](PRODUCT.md#locked-delivery-order-functionality-before-expansion) and the [one-owner identity contract](application-design.md#personal-server-identity-and-access-contract).

## Outside public alpha

- Native Windows clients are planned after the Linux path is validated; Windows hosts are a separate longer-term independent-session and licensing problem.
- Personal music and DroppedNeedle, books, comics, recommendation engines, extensive multi-user desktops and AI features.
- A bundled NOW VPN subscription, guaranteed $7 pricing, VPN affiliate or white-label contracts, billing, and a cloud account service. **Bring-your-own VPN works first.** Referral partnerships and an optional VPN offering for the server plus customer devices remain exploratory commercial options; provider limits, licensing, performance and margins are unverified.
- Proprietary streaming protocols, a general server app store, universal GPU support or access to copyrighted media catalogs.

**Safety and truthfulness:** A VPN changes routing and network exposure; it does not guarantee anonymity or legal permission to download particular content. No content is bundled. Physical acceptance is necessary for claims about isolation, playback, performance and easy setup.
