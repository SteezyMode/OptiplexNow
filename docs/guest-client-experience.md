# NOW guest client: connect to the owner's OptiPlex

**Target product:** An owner configures one existing OptiPlex server once, distributes the NOW client to trusted guests, and authorizes them to use selected gaming, media, and other services on that OptiPlex from their homes or remotely while the host is powered on.

This is **not** a requirement for guests to install their own Sunshine/Wolf server or run their own NOW Host Agent.

## Guest experience

1. Install NOW on the guest's computer.
2. Follow an owner-issued **Tailscale share invitation for the OptiPlex**, or join the owner's tailnet using their **own** Tailscale user identity. Do not request or share the owner's personal Tailscale login/password, reusable auth keys, node keys or tailnet admin access. The guest accepts the invitation using their own Tailscale identity.
3. After Tailscale is connected and access is authorized, NOW discovers the owner's OptiPlex by its verified node identity and saves the server selection locally. No IP or port entry.
4. NOW presents configured **Games**, **Jellyfin**, and other services as straightforward launch tiles. The host supplies service capabilities without exposing host admin tools. Connections remain direct over Tailscale/LAN where possible.
5. For **Games**, the guest requests Moonlight pairing, and the owner approves the device once; independent Wolf guest desktops are preferred for guests, rather than sharing the owner's unrestricted live desktop. Steam game availability depends on the actual host's Steam session, licenses and concurrent-use rules; NOW must not distribute Steam account credentials.
6. For **Jellyfin**, give each guest a Jellyfin account or another officially supported per-user authentication method. NOW should save that guest's service token locally after first authorization, with revocation/logout support. **Tailscale identity alone is not a Jellyfin login.** Do not hand out the owner's Jellyfin admin account or copy backend secrets into the client package.
7. Future launches: **Open NOW → choose Games, Jellyfin, or another approved service**. If the Tailscale session and service/pairing credentials remain valid, no account prompt is needed. On the same LAN, an optional explicit trusted-LAN fallback may be added later without undermining device authorization.

## First release: owner/server model

- The owner controls access. Each guest gets their **own Tailscale identity** and separate NOW device authorization; granting one person access does not grant their entire tailnet access.
- Use official Tailscale per-machine share invitations where applicable, rather than adding arbitrary guests as administrators or sharing the primary login. Restrict Tailscale grants to necessary host ports/services and maintain an easy revoke path.
- The **NOW Host Agent remains on the owner's OptiPlex**. The client never gets the Docker socket, SSH credentials, shell commands, root privileges, Sunshine/Wolf administrative credentials or server installer actions.
- The host can advertise a modest typed capabilities list: e.g., games available, Jellyfin available, optional owner-enabled services. **Do not** expose arbitrary URLs or proxy unrestricted host services without authorization.
- Keep onboarding separate from service credentials: secure networking (Tailscale), owner approval (NOW), Moonlight native pairing (gaming), and Jellyfin per-user authentication (media) are independent layers. Smooth UX should *orchestrate* those layers, not bypass them.
- The host must be powered on, connected to the network and running the required services. Tailscale provides connectivity across different networks but does not turn on a powered-down desktop automatically.
- Do not expose Jellyfin, Wolf, remote desktop, SSH or NOW pairing to the public internet just to make setup easier. There is no required public website or NOW account for first release.

## Next engineering priorities

1. **Guest invitation and identity compatibility:** validate official Tailscale machine sharing with two different real user identities, including shared-node IP mapping, WhoIs fields, tailnet grants and revocation. Confirm NOW discovery works with shared-in host nodes.
2. **Complete request-only pairing broker:** remote device may request, check or cancel only its own pending authorization; owner approves locally; a backend adapter may consume an approved grant once. Broker is opt-in, under a narrowly scoped separate port and no shared user-facing admin routes.
3. **Game-launch flow:** authenticated Moonlight pairing and replay-safe reconnect to a scoped Sunshine/Wolf session. Prefer isolated guest desktops and account separation when possible.
4. **Jellyfin launch:** configured by the owner, guest-specific login, locally retained credentials using appropriate OS protections and direct streaming. No master-password distribution.
5. **Simple NOW client home screen:** automatically rediscover the chosen OptiPlex, reflect host online/offline and only show configured/authorized services. Keep GTK integration modular.
6. **Disposable-host acceptance:** realistic two-device testing, cross-tailnet guest share, remote playback/input, media login, logout/revocation and service coexistence before exposing the owner's real OptiPlex.

## Explicit non-goals for this milestone

No client account backend, custom VPN implementation, silent Moonlight pairing, auto-provisioning a fresh host for each guest, new public website or a remotely accessible administrative socket.

References: [Tailscale share a machine](https://tailscale.com/docs/features/sharing), [Tailscale access-control grants](https://tailscale.com/docs/reference/syntax/grants), [Tailscale identity](https://tailscale.com/docs/concepts/tailscale-identity).
