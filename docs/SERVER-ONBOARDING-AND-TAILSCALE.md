# NOW server onboarding and Tailscale account/discovery design

**Status:** Architecture proposal only — NOT implemented or approved for release.  
**Drafted:** 2026-10-20  
**Owner:** OptiPlex NOW (not OptiPlex Studio)  
**Related:** [Current status](CURRENT-STATUS.md), [server setup](server-setup.md), [upstream-first Wolf architecture](UPSTREAM-FIRST-WOLF-INTEGRATION.md), [multi-user desktop feasibility](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md).

## Product objective

A person with a supported Linux PC should be able to make it a remotely streamable personal computer using a guided installation, then install NOW on a second device, authorize Tailscale **at most once** when needed, discover that server automatically, and stream after a safe first-time pairing approval. An optional future NOW website account is not required for this first-release user journey. No memorized IP addresses, terminal commands, Docker configuration, manually copied SSH settings, or remembered Moonlight host addresses should be necessary for the ordinary happy path.

**Explicitly separate three concerns:**
1. **NOW account and optional website:** identifies the person's registered servers and synchronizes *non-secret* connection metadata/preferences.
2. **Tailscale:** authenticates devices, establishes permitted private network connectivity and enforces tailnet access policy. Users control their own tailnets.
3. **Moonlight plus Wolf or Sunshine:** streams games/desktops and performs its own client pairing. Website login does **not** confer Moonlight pairing or Linux administration rights.

A NOW account should improve convenience but never be a prerequisite for local streaming or permanently prevent users from accessing their own data if the optional NOW account service is unavailable. Game video/audio/control streams must **not** pass through the optional NOW registry service. The Tailscale path may use Tailscale infrastructure for connectivity/relay when direct paths are unavailable; NOW does not guarantee direct peer-to-peer performance.

## Release reality and platform scope (2026-10-20)

NOW 1.14.0 is a native x86-64 Debian/Ubuntu-family **client for an existing server**. The New Server Setup screen is a placeholder. It does not provision Sunshine, Wolf, Tailscale, GPU drivers or server backups, and it does not have a NOW account service.

The first install target should be a tested subset of Ubuntu/Pop!_OS 24.04 and compatible NVIDIA encoder configurations, narrowed by empirical clean-machine testing. Other distros, GPUs and architectures are candidates, not promises. A NOW desktop client currently exists for compatible Linux; users of Windows/macOS/mobile/TV Moonlight would initially receive instructions and supported pairing information through a web portal, not an invented native NOW client.

## Default first-release decision: one sign-in, not two

**Recommendation for the first supported Linux-client release:** Use the existing official **Tailscale sign-in as the only new-account login required** for remote client setup. Do not require a separate NOW website identity, registration, or password. On a client with an authorized and working Tailscale connection, account login can be **zero steps**. If Tailscale is disconnected or the device is unapproved, direct users to the official sign-in/approval process. Local-LAN setup continues without Tailscale.

**Host discovery without a website:** NOW reads the local Tailscale peer inventory (or supported local API) and attempts bounded read-only discovery of a narrowly scoped NOW host agent at a documented, fixed tailnet-only endpoint on accessible peers. Only a server with a valid, authenticated NOW service response enters the **My computers** list; a peer appearing in `tailscale status` is *not* evidence that it runs NOW. Store a stable server public identity/fingerprint, advertised streaming backend and full MagicDNS hostname locally. Hostname/IP changes may require rediscovery, but do not require users to memorize them. Discovery must be rate-limited, respect Tailscale grants, avoid probing unrelated network segments and not assume every tailnet peer is a server.

**Control vs streaming:** The client talks to the host's restricted NOW agent using authenticated HTTPS over Tailscale for discovery, pairing requests, capabilities and status. The host uses Tailscale's LocalAPI/WhoIs to bind incoming connections to real tailnet node/user identity, plus NOW's own owner-approved per-device authorization before granting sensitive actions. No raw Wolf, Sunshine, Docker, SSH or root management interfaces should be exposed to ordinary clients. Streaming itself is **Moonlight directly to Wolf/Sunshine over Tailscale** (or LAN), not proxied through an account site or the NOW agent.

**First-time Moonlight pairing:** Network authorization is not streaming authorization. A Moonlight client must independently pair with the selected streaming host and keep its **own private certificate/credential locally**. Sunshine documents an authenticated host-side pairing API and Wolf has a restricted Unix-socket pairing interface for versions that actually support it. NOW should attempt a guided pairing handshake only after verified device identity and an explicit owner authorization on the host or an existing trusted administrator device. The final design may show one confirmation/PIN step; **do not promise truly silent pairing until the actual external Moonlight client and pinned host versions support it and adversarial tests pass**. Never upload or sync client private keys, host admin passwords, Tailscale keys or pairing secrets into a website registry.

**Reconnection:** Reuse persisted Tailscale enrollment, the saved server ID/hostname and the locally paired Moonlight certificate. The intended normal repeat experience is **open NOW → Play**, with no login. Reauthentication, device approvals, lost keys, changed network grants or a replaced host may occasionally require interaction.

**Cross-tailnet access:** A person outside the owner's tailnet still needs explicit machine-sharing invitation/acceptance (or equivalent policy) and owner-approved streaming pairing. A valid NOW login cannot silently bypass those steps. Keep client/host authorization separate from any future NOW account.

**Site policy:** A temporary development website may later offer an optional account/registry for cross-device server lists, invitations and settings. It does **not** make Tailscale sign-in disappear and should not become mandatory for LAN or same-tailnet clients. Tailscale OAuth app device provisioning is alpha and **single-tailnet only** as of its June 24, 2026 documentation; it is not an acceptable general cross-customer onboarding mechanism. Users own their tailnets, not a shared developer-controlled tailnet.

External reference docs: [Tailscale node identity/WhoIs](https://tailscale.com/docs/concepts/tailscale-identity), [Tailscale machine sharing](https://tailscale.com/docs/features/sharing), [Tailscale OAuth provisioning limitations](https://tailscale.com/docs/features/oauth-apps/device-provisioning), [Sunshine pairing API](https://docs.lizardbyte.dev/projects/sunshine/master/md_docs_2api.html), [Wolf pairing API](https://games-on-whales.github.io/wolf/stable/dev/api.html).

## First-class user journeys

### A. Register a new home server (opt-in cloud path)

1. Run NOW on the intended supported Linux server. Choose **Set up this PC as a server**.
   **First-release path:** local install and Tailscale setup do **not** require creating a NOW cloud account; the optional steps 6-7 below are a separate future extension.
2. Read-only preflight detects distro/architecture, available GPU encode path, kernel/driver capabilities, memory/storage, Tailscale status, Docker/container runtime, audio/input capabilities, network/port conflicts and existing streaming installs. Display exactly what must change, with clear unsupported/error states.
3. User chooses **Stream my existing desktop (Sunshine)** or **Create an independent desktop (Wolf)**. The wizard configures *one primary streaming host per default port set*; do not start two conflicting streaming hosts automatically.
4. User approves required OS changes. An explicitly authorized, narrowly scoped local server manager installs/pins components, configures services, preserves existing state and has an executable rollback plan. Avoid arbitrary privileged commands from clients or web.
5. Offer **Secure remote access with Tailscale**. If already signed in, reuse existing enrollment. Otherwise launch Tailscale's official browser/device sign-in flow; the user authenticates with Tailscale, not NOW. Verify that the server is enrolled and reachable on its intended tailnet. Do not require Tailscale for LAN-only use.
6. Offer **Link to my NOW account**. On the server, obtain proof of possession through a short-lived, single-use challenge approved locally; user signs into the proposed NOW site and confirms the specific server. A server-generated keypair and signed HTTPS enrollment exchange establish the server identity. This is a proposed mechanism, not existing code.
7. Optionally register a display name, random stable server ID, Tailscale fully qualified MagicDNS name, supported capabilities and narrow, non-sensitive health/version information. Show an explicit privacy notice. There must be no inbound public listener required for cloud registration; status reporting is outbound HTTPS.
8. After a second device actually plays a verified stream, mark streaming setup complete. A running process/container alone is insufficient.

### B. Add a new client computer (first-release Tailscale-first path)

1. Install NOW on a compatible Linux client. If Tailscale is already installed and authorized, reuse its existing device session and skip account sign-in.
2. Otherwise use NOW's **Connect securely** action to launch the **official Tailscale sign-in flow** once. The client machine receives a device identity from Tailscale. The user does not enter any host IP, tailnet name, SSH user or Moonlight PIN into NOW account settings. If device approval is enabled, an authorized tailnet administrator still has to approve the device.
3. NOW enumerates only reachable/authorized Tailscale peers and detects NOW hosts through a narrowly scoped, authenticated read-only service check. Use the full MagicDNS hostname and stable host identity; don't mistake a generic Tailscale peer for a compatible host.
4. Display **My computers** with approved server names and streaming backend. The user selects a host (or auto-selects their only approved host).
5. Start Moonlight pairing on this client. Route the pairing request to the host manager for **explicit owner authorization**. Prefer a one-click owner approval instead of manual copy/paste; verify actual support in the installed Moonlight/Wolf/Sunshine versions before hiding the PIN.
6. Verify picture, audio/input and reconnection. Save only local client identity and non-secret server preferences; subsequent use should be **open NOW → Play**.

**First-setup interaction budget:** one Tailscale sign-in **if needed**, plus a device approval and/or a host pairing confirmation **when security requires it**. Those confirmations are not additional account logins. Account reuse or LAN-only operation may have no login at all. The app must not promise unattended access to a server the owner has not authorized.

**Future optional website path:** A NOW account could synchronize a list of approved server identities across newly installed clients, but it must not replace official Tailscale enrollment, host authorization, or native Moonlight pairing. It should not be the default in the single-sign-in release.

### C. Share a server with another person

A recipient does not need a NOW website account in the first-release path. Their Tailscale identity is still **not** automatically a member of the owner's Tailscale network. Treat granting access as a distinct owner approval:
- NOW host owner explicitly authorizes the recipient's device for streaming; an optional future account/registry layer may supplement but not replace this approval.
- Tailnet owner uses Tailscale's supported **share a machine** invitation (or an intentionally configured same-tailnet invitation/policy) so the recipient can reach only authorized resources. The recipient accepts and signs in using their own Tailscale identity.
- Wolf/Sunshine pairing is approved separately. For Wolf, per-person desktop/session authorization and isolation require additional validation at the native Moonlight/host boundary; NOW UI filtering alone is not security.
- Show revoke access in the UI and clearly distinguish NOW device authorization, Tailscale network permission, Moonlight paired-device revocation and any later website-account revocation.

A household multi-user product is a later security milestone, not something guaranteed by creating two Wolf containers.

### D. Offline/no-account path

**Connect to an existing server** must remain available for LAN-only use or privacy-conscious users. It can discover a host on reachable networks or accept a hostname manually. Pair through Moonlight and preserve local settings. NOW's core local and LAN streaming must continue when the optional account service is offline.

## Architecture and trust boundaries

| Component | Responsibility | Secrets it must not receive |
| --- | --- | --- |
| NOW Linux client | Local setup UX, authenticated server list, connectivity checks, launch Moonlight | Other devices' Tailscale keys, other devices' Moonlight private keys |
| NOW server manager (proposed) | Least-privilege allowlisted installation, profile, service health, rollback, pairing authorization | Arbitrary commands from cloud/browser clients |
| NOW registry (optional cloud) | Account sign-in, approved server associations, minimal non-secret metadata, one-time registration/device linking | Tailscale auth keys, SSH keys/passwords, Moonlight pairing private keys, Steam credentials, root/Docker/Wolf control sockets |
| Tailscale (upstream) | Per-device network enrollment, MagicDNS, private connectivity, policy, optional sharing | NOW's game-session/application authorization responsibilities |
| Wolf or Sunshine (upstream) | Stream protocol, pairing, encoder/app sessions | NOW cloud authentication tokens |
| Moonlight (upstream) | Decode stream, input and per-device host pairing | NOW backend administration privilege |

Maintain separate identifiers for NOW account, server, physical client device, Tailscale node, native Moonlight client certificate, Wolf profile/desktop and ephemeral stream session. Account-to-server association must not be confused with device/network authorization.

A compromised NOW web account must **not** automatically yield a shell, a usable Tailscale tunnel, streaming access or host-control privileges. Use standard hardened login (prefer passkeys/established authentication provider with MFA), device-scoped revocable application sessions, session expiry, rate limiting, CSRF protection, short-lived one-time enrollment challenges, user-visible device revocation, and audited registration changes. Avoid inventing bespoke password or cryptography systems. Do not put secrets in URLs, query strings, source code, GitHub, browser local storage or diagnostics.

The website may display 'recently seen' using a signed, outbound server heartbeat, but must never claim a client can actually connect until that **client** verifies its own Tailscale reachability and stream pairing. Do not expose Wolf's management Unix socket, Docker socket, server root/API, Tailscale local API, SSH admin or similar privileged interfaces publicly. NOW's privileged server manager needs explicit action allowlists and local authorization even when its caller has a valid NOW account.

## Tailscale decisions and caveats

- **Default:** each customer keeps their own tailnet. NOW does not enroll all customers into a shared developer-operated tailnet.
- **Authentication:** initial login to Tailscale is a separate official user action on server and each client, unless the device is already enrolled. A NOW account cannot silently skip that step.
- **Discovery:** prefer fully qualified MagicDNS name and a stable NOW server ID, not remembered Tailscale IPs. Device name changes and DNS issues should be handled gracefully. Tailscale generally assigns stable 100.x addresses across changes in physical networks, but network authorization is still required.
- **Sharing:** Tailscale machine sharing is the candidate for invited external users. Share does not itself grant NOW or Moonlight application authorization. Accepting a share and owner policy are explicit.
- **Provisioning:** don't build the public cross-customer flow on Tailscale's OAuth-app device provisioning: **as documented June 2026 it is alpha and limited to one tailnet**, unsuitable for a single NOW app serving unrelated customer tailnets. Classic Tailscale auth keys are credential material and should not be stored in NOW's cloud registry.
- **Failure modes:** handle tailscaled stopped, signed-out device, missing share, ACL denial, unresolvable MagicDNS, expired/unauthorized machine, firewalls/relayed connections and separate Moonlight pairing failure with targeted explanations. Do not describe an account/hostname lookup as proof of network connectivity.
- **Privacy:** opting into registry sync exposes limited server existence/name/last-seen data to the website; require consent and offer account/server deregistration without erasing local game or desktop data.

References: [Tailscale quickstart](https://tailscale.com/kb/1017/install/), [Machine names/MagicDNS](https://tailscale.com/docs/concepts/machine-names), [Share your machines](https://tailscale.com/kb/1084/sharing), [Auth keys](https://tailscale.com/docs/features/access-control/auth-keys), [Device provisioning with OAuth apps — alpha/single-tailnet](https://tailscale.com/docs/features/oauth-apps/device-provisioning).

## Temporary infrastructure and UI copy standards

Any available website/domain used during development is **temporary hosting infrastructure only**. It is **not** the product identity, company identity, identity-provider design, or brand. Do not embed a temporary domain, owner company, or assumed future brand in UI strings, package names, protocols, docs or screenshots. The address must be configurable, with production migration and a no-account mode supported.

A development login screen should be strictly utilitarian. Suggested labels: **Sign in**, **Email**, **Continue**, **My servers**, **Add server**, **Connect**, **Sign out**. Display necessary privacy/security disclosures in a factual style. Avoid promotional taglines, AI-written marketing paragraphs, stock imagery, invented testimonials, brand grandstanding or a sales landing page. Sign-in should focus on selecting and authorizing the user's device, not selling the product.

## Engineering roadmap (documentation only)

**Phase 0 — Inventory and proof, read-only:** map the current NOW UI/actions, host prerequisites and reference Wolf setup; implement testable read-only compatibility detection, with privacy-safe structured results. No service changes. Avoid using the production OptiPlex as a clean installation test.

**Phase 1 — One supported local install:** test on a clean supported Linux+GPU host. First get a reliable Sunshine *or* Wolf installation working under a local, allowlisted manager, preserve existing installations, support rollback and run a real LAN Moonlight smoke test. The first validated backend is an engineering choice, not an unsupported universal promise.

**Phase 2 — Tailscale guided connectivity:** official user sign-in, reuse existing enrollment, hostname discovery, authorized reachability tests, Moonlight PIN workflow and remote reconnect verification. Existing-server migration must remain non-destructive.

**Phase 3 — Automatic client discovery and host pairing:** signed/authorized host identity, narrow tailnet-only discovery and host status, verified Tailscale device identity, owner-approved Moonlight pairing, local credential persistence, and a real client-stream test. No NOW website login required.

**Phase 3b — Optional account/registry proof (later):** separate hosted sign-in, server challenge/linking, metadata sync and account recovery; never require this for the Tailscale-first or LAN-only journey. Server management stays private; website downtime does not block known local clients.

**Phase 4 — Other backend, maintenance/recovery and outside testing:** validate Wolf/Sunshine interoperability decisions, safe version pins, observability, backup/restore, broken-network UX and external-network playback. Then invite limited real users to measure time-to-first-stream and support requests.

**Phase 5 — Authorized multi-user Wolf desktops:** only after the separate security and persistence gates in the multi-user feasibility document are met.

### First acceptance checklist

- Fresh supported Linux machine completes preflight with useful actionable errors.
- Re-running an interrupted setup is idempotent; installed unrelated services and data remain untouched.
- One streaming host works with Moonlight; an actual picture/input test succeeds.
- A new client signs into Tailscale if necessary, automatically discovers its authorized NOW server without typing an IP, and does not need a separate NOW website account.
- Tailscale enrollment (if needed) is user-authorized through Tailscale; denied access remains denied even with a valid NOW website session.
- Moonlight pairing is device-specific and owner-approved; revocation can be tested.
- Client reconnect works from a genuinely separate outside-LAN network.
- Deleting a NOW cloud account or losing website connectivity does not erase local game files, persistent desktops or remove the owner's Tailscale credentials.
- No public control sockets, administrative endpoints or site-held VPN/SSH/Moonlight secrets.
- All instructions indicate **proposed vs shipped** behavior accurately.

## Open decisions before implementation

1. Choose a tested first backend (Sunshine existing-host desktop versus Wolf independent virtual desktop) based on lowest-risk clean install testing; avoid shipping both as mandatory.
2. Choose a security-reviewed hosted identity provider and exact sign-in mechanism for the optional website; no auth stack exists yet.
3. Define the minimum server registry fields and the authenticated server possession/enrollment protocol, including account recovery and revocation.
4. Define whether Linux clients can hand off Moonlight pairing PINs through documented supported interfaces; never promise pairing automation without proof.
5. Define server-side account sync/management boundaries and privacy retention rules.
6. Test client/platform support and ensure non-Linux/TV Moonlight clients have an honest manual guide until dedicated integration exists.

**Change-control rule:** This document does not authorize deploying a new account site, starting services, updating Wolf/Sunshine, changing Tailscale membership, touching the reference server, merging code or publishing NOW. It is a decision draft for implementation planning.
