# NOW server onboarding and Tailscale account/discovery design

**Status:** Architecture proposal only — NOT implemented or approved for release.  
**Drafted:** 2026-10-20  
**Owner:** OptiPlex NOW (not OptiPlex Studio)  
**Related:** [Current status](CURRENT-STATUS.md), [server setup](server-setup.md), [upstream-first Wolf architecture](UPSTREAM-FIRST-WOLF-INTEGRATION.md), [multi-user desktop feasibility](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md).

## Product objective

A person with a supported Linux PC should be able to make it a remotely streamable personal computer using a guided installation, then sign into OptiPlex NOW on a second device to discover that server automatically. No memorized IP addresses, terminal commands, Docker configuration, manually copied SSH settings, or remembered Moonlight host addresses should be necessary for the ordinary happy path.

**Explicitly separate three concerns:**
1. **NOW account and optional website:** identifies the person's registered servers and synchronizes *non-secret* connection metadata/preferences.
2. **Tailscale:** authenticates devices, establishes permitted private network connectivity and enforces tailnet access policy. Users control their own tailnets.
3. **Moonlight plus Wolf or Sunshine:** streams games/desktops and performs its own client pairing. Website login does **not** confer Moonlight pairing or Linux administration rights.

A NOW account should improve convenience but never be a prerequisite for local streaming or permanently prevent users from accessing their own data if Monument Risk's website is unavailable. Game video/audio/control streams must **not** pass through Monument Risk infrastructure. The Tailscale path may use Tailscale infrastructure for connectivity/relay when direct paths are unavailable; NOW does not guarantee direct peer-to-peer performance.

## Release reality and platform scope (2026-10-20)

NOW 1.14.0 is a native x86-64 Debian/Ubuntu-family **client for an existing server**. The New Server Setup screen is a placeholder. It does not provision Sunshine, Wolf, Tailscale, GPU drivers or server backups, and it does not have a NOW account service.

The first install target should be a tested subset of Ubuntu/Pop!_OS 24.04 and compatible NVIDIA encoder configurations, narrowed by empirical clean-machine testing. Other distros, GPUs and architectures are candidates, not promises. A NOW desktop client currently exists for compatible Linux; users of Windows/macOS/mobile/TV Moonlight would initially receive instructions and supported pairing information through a web portal, not an invented native NOW client.

## First-class user journeys

### A. Register a new home server (opt-in cloud path)

1. Run NOW on the intended supported Linux server. Choose **Set up this PC as a server**.
2. Read-only preflight detects distro/architecture, available GPU encode path, kernel/driver capabilities, memory/storage, Tailscale status, Docker/container runtime, audio/input capabilities, network/port conflicts and existing streaming installs. Display exactly what must change, with clear unsupported/error states.
3. User chooses **Stream my existing desktop (Sunshine)** or **Create an independent desktop (Wolf)**. The wizard configures *one primary streaming host per default port set*; do not start two conflicting streaming hosts automatically.
4. User approves required OS changes. An explicitly authorized, narrowly scoped local server manager installs/pins components, configures services, preserves existing state and has an executable rollback plan. Avoid arbitrary privileged commands from clients or web.
5. Offer **Secure remote access with Tailscale**. If already signed in, reuse existing enrollment. Otherwise launch Tailscale's official browser/device sign-in flow; the user authenticates with Tailscale, not NOW. Verify that the server is enrolled and reachable on its intended tailnet. Do not require Tailscale for LAN-only use.
6. Offer **Link to my NOW account**. On the server, obtain proof of possession through a short-lived, single-use challenge approved locally; user signs into the proposed NOW site and confirms the specific server. A server-generated keypair and signed HTTPS enrollment exchange establish the server identity. This is a proposed mechanism, not existing code.
7. Optionally register a display name, random stable server ID, Tailscale fully qualified MagicDNS name, supported capabilities and narrow, non-sensitive health/version information. Show an explicit privacy notice. There must be no inbound public listener required for cloud registration; status reporting is outbound HTTPS.
8. After a second device actually plays a verified stream, mark streaming setup complete. A running process/container alone is insufficient.

### B. Add a new client computer to the same account

1. Install NOW and click **Sign in to NOW**. Authenticate through system browser with a standard public-client flow (authorization code + PKCE), or a secure device-code flow where callbacks are unavailable; exact auth provider TBD. The website could be hosted on an appropriate Monument Risk subdomain, but no deployment is implied here.
2. NOW obtains an account-scoped server list over HTTPS and offers **My Gaming PC**, **Family Desktop**, etc. It auto-fills server identity, advertised apps, MagicDNS FQDN, and non-secret preferences. No manual IP or SSH username should be needed for first streaming.
3. If Tailscale is already installed and authorized in the matching tailnet, check live reachability. If not, guide official Tailscale installation and user sign-in, with the right tailnet or Tailscale machine-share invitation. **NOW website login alone does not enroll a machine in Tailscale**.
4. Resolve the server's full MagicDNS name, with an observed Tailscale address as an optional diagnostic fallback. Never use a hard-coded home LAN IP as the canonical server identity.
5. Ensure Moonlight is installed/selected. Offer native Moonlight pairing to Sunshine or Wolf; a PIN must be approved by an already-authorized host administrator or via a dedicated, authenticated manager operation. Do not bypass pairing or copy a shared long-lived pairing secret from the website.
6. Verify real playback, audio/input as applicable, disconnect/reconnect, and save the local client configuration securely.

On later sign-ins, NOW should restore its server list and preferences automatically. Tailscale and Moonlight local device credentials persist under their own security models; the registry must not copy them between devices.

### C. Share a server with another person

A second NOW account is **not** automatically a member of the owner's Tailscale network. Treat granting access as a distinct owner approval:
- NOW owner authorizes the other person in the NOW account/registry layer.
- Tailnet owner uses Tailscale's supported **share a machine** invitation (or an intentionally configured same-tailnet invitation/policy) so the recipient can reach only authorized resources. The recipient accepts and signs in using their own Tailscale identity.
- Wolf/Sunshine pairing is approved separately. For Wolf, per-person desktop/session authorization and isolation require additional validation at the native Moonlight/host boundary; NOW UI filtering alone is not security.
- Show revoke access in the UI and clearly distinguish NOW account revocation, Tailscale network permission and Moonlight paired-device revocation.

A household multi-user product is a later security milestone, not something guaranteed by creating two Wolf containers.

### D. Offline/no-account path

**Connect to an existing server** must remain available for LAN-only use or privacy-conscious users. It can discover a host on reachable networks or accept a hostname manually. Pair through Moonlight and preserve local settings. NOW's core local and LAN streaming must continue when Monument Risk is offline.

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

- **Default:** each customer keeps their own tailnet. NOW does not enroll all customers into a shared Monument Risk tailnet.
- **Authentication:** initial login to Tailscale is a separate official user action on server and each client, unless the device is already enrolled. A NOW account cannot silently skip that step.
- **Discovery:** prefer fully qualified MagicDNS name and a stable NOW server ID, not remembered Tailscale IPs. Device name changes and DNS issues should be handled gracefully. Tailscale generally assigns stable 100.x addresses across changes in physical networks, but network authorization is still required.
- **Sharing:** Tailscale machine sharing is the candidate for invited external users. Share does not itself grant NOW or Moonlight application authorization. Accepting a share and owner policy are explicit.
- **Provisioning:** don't build the public cross-customer flow on Tailscale's OAuth-app device provisioning: **as documented June 2026 it is alpha and limited to one tailnet**, unsuitable for a single NOW app serving unrelated customer tailnets. Classic Tailscale auth keys are credential material and should not be stored in NOW's cloud registry.
- **Failure modes:** handle tailscaled stopped, signed-out device, missing share, ACL denial, unresolvable MagicDNS, expired/unauthorized machine, firewalls/relayed connections and separate Moonlight pairing failure with targeted explanations. Do not describe an account/hostname lookup as proof of network connectivity.
- **Privacy:** opting into registry sync exposes limited server existence/name/last-seen data to the website; require consent and offer account/server deregistration without erasing local game or desktop data.

References: [Tailscale quickstart](https://tailscale.com/kb/1017/install/), [Machine names/MagicDNS](https://tailscale.com/docs/concepts/machine-names), [Share your machines](https://tailscale.com/kb/1084/sharing), [Auth keys](https://tailscale.com/docs/features/access-control/auth-keys), [Device provisioning with OAuth apps — alpha/single-tailnet](https://tailscale.com/docs/features/oauth-apps/device-provisioning).

## Engineering roadmap (documentation only)

**Phase 0 — Inventory and proof, read-only:** map the current NOW UI/actions, host prerequisites and reference Wolf setup; implement testable read-only compatibility detection, with privacy-safe structured results. No service changes. Avoid using the production OptiPlex as a clean installation test.

**Phase 1 — One supported local install:** test on a clean supported Linux+GPU host. First get a reliable Sunshine *or* Wolf installation working under a local, allowlisted manager, preserve existing installations, support rollback and run a real LAN Moonlight smoke test. The first validated backend is an engineering choice, not an unsupported universal promise.

**Phase 2 — Tailscale guided connectivity:** official user sign-in, reuse existing enrollment, hostname discovery, authorized reachability tests, Moonlight PIN workflow and remote reconnect verification. Existing-server migration must remain non-destructive.

**Phase 3 — Optional account/registry proof:** server challenge/linking, secure web login, sign in from a second NOW client, server list sync, automatic hostname resolution and a full client-stream test. Server management stays private; website downtime does not block known local clients.

**Phase 4 — Other backend, maintenance/recovery and outside testing:** validate Wolf/Sunshine interoperability decisions, safe version pins, observability, backup/restore, broken-network UX and external-network playback. Then invite limited real users to measure time-to-first-stream and support requests.

**Phase 5 — Authorized multi-user Wolf desktops:** only after the separate security and persistence gates in the multi-user feasibility document are met.

### First acceptance checklist

- Fresh supported Linux machine completes preflight with useful actionable errors.
- Re-running an interrupted setup is idempotent; installed unrelated services and data remain untouched.
- One streaming host works with Moonlight; an actual picture/input test succeeds.
- A new client signs into NOW and sees its registered server without typing an IP.
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
