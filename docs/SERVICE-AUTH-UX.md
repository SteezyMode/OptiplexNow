# Client/server authentication UX — provider-first, self-contained

**Status:** Design and incremental implementation; no email/SSO service exists today.  
**Scope:** Existing NOW GTK launcher and future guided NOW host installer. OptiPlex is only the developer's current reference host, **not a central account or required server**.

## User experience target

Install NOW → connect/authenticate Tailscale **once** (or reuse the current session) → choose an accessible compatible server → authorize native Moonlight pairing on first use → select Steam in the **existing NOW GUI**. Returning users should only need to open NOW.

On the **server**, initial setup should gather necessary configuration and lead users through upstream service sign-ins **inside the installer or supported system browser**, never require copying bearer tokens into a terminal, fragile SSH callback ports, or pasting passwords into scripts.

Show per-service status in the current Setup Wizard (or a compact modal in the future host wizard): **Not installed / Sign in / Waiting for confirmation / Connected / Needs attention / Optional**. Only claim Connected after checking the *actual service/session*, not after launching a browser.

## What each login authorizes

| Component | Initial authorization | Persistent state | Scope/owner |
| --- | --- | --- | --- |
| Tailscale on client/server | Official Tailscale browser sign-in; reuse existing device where possible | Tailscale daemon enrollment | Connectivity and accessible machine list **only**, not admin/API/media permissions |
| Wolf/Sunshine ↔ native Moonlight | Moonlight's native first-time PIN/certificate pairing, approved by owner in a trusted local host action | Per-client Moonlight private identity/certificate | Stream and session permission; **Wolf runs on server, Moonlight runs on client** |
| MoonlightWeb | Use MoonlightWeb's **own** configured PIN/session/certificate flow via the chosen HTTPS origin; do not send its admin password through NOW | Browser-specific MoonlightWeb session | Optional web stream; don't assume identical trust/key storage to native Moonlight |
| Jellyfin | Open the Jellyfin client/web UI; where supported use Jellyfin **Quick Connect** authorization from another already authenticated device | Jellyfin's own auth session | Per-user media access; URL can be discovered/configured, but tailnet login is not Jellyfin SSO |
| Dropped Needle | Optional upstream login in its own browser UI after configured URL | Upstream service cookies/tokens | Later, not an installer MVP blocker |
| Codex (Studio-specific) | OpenAI Codex's supported **OAuth device-code** flow for SSH/container/headless sessions, with code/link visible in the owning local UI. Default browser OAuth if on the same machine. | Codex's own protected credential store | Belongs to **OptiPlex Studio**'s development environment, not a mandatory NOW login |

**No universal fake SSO:** The user's single Tailscale login is the *onboarding anchor*, not a password that unlocks all services. When a provider exposes a supported device-code or Quick Connect flow, NOW should orchestrate that flow and check completion, not emulate or bypass it.

## Service authentication design rules

1. Provider-native authorization first: OAuth device-code/PKCE, Jellyfin Quick Connect, Moonlight native pairing or an upstream browser sign-in. No invented undocumented backend endpoints.
2. If the service runs inside a Wolf desktop/container, the code is displayed in the setup flow; user signs in from any browser/device; tokens are stored **in the correct service container/profile**, not copied to a NOW client, another session or a cloud website.
3. A server-side local controller may *request* a supported authorization process and receive **limited status only**. Never create a tailnet-facing Wolf Unix-socket proxy, generic shell, root API or Docker gateway to accomplish login.
4. For remote access, callbacks bound to a remote localhost must be handled by provider-supported device code or other validated supported flow; do **not** suggest disabling OAuth security or copying raw auth files as the default.
5. Store no Tailscale passwords, Codex OAuth refresh tokens, Jellyfin admin passwords, Wolf admin secrets, browser session cookies or pairing private keys in NOW's ordinary config.ini, portable .onp presets, logs, GitHub or email.
6. Distinguish guest/application login from OS/SSH/server administration. Basic streaming must **not** force SSH key setup.
7. A server owner can update/revoke each connected service separately; status can expire. Treat sign-in as durable when the provider's actual session remains valid, not forever.
8. Existing integrations continue working if NOW's setup dialog is not running and when optional email/web support is offline.

## Email PINs and owner notifications (optional server milestone)

Email PIN is a viable **optional owner email verification and out-of-band device approval** feature. During a future server install, ask for a destination email and send a verification challenge through an explicitly configured SMTP or transactional provider. Verify that address before using it for new-device alerts and optional approval.

- Create a **random, single-use, short-lived** PIN tied to a server-specific pending action. Give a narrow validity period (e.g. five minutes), rate-limit sends and verification attempts, and never log the plaintext code or store it as a recoverable secret.
- Email notifications must not independently grant Wolf admin, system login, or Steam/Codex/Jellyfin account access. Pair email confirmation with real device identity, local owner trust and the specific requested operation.
- Delivery and recovery must work sensibly when the SMTP provider fails, the server is offline, or the user has no email account; a trusted local owner confirmation remains possible. Don't hardcode a developer SMTP account or route all customer approvals through a central service.
- For the first client install **email is not mandatory**; adding mail delivery, abuse protection and account recovery prematurely would expand the MVP significantly.

## Platform/streaming decision

**Wolf on supported servers remains the primary choice for independent virtual desktops and not taking over the physical host screen.** A client NEVER needs Wolf installed. Linux NOW uses detected native Moonlight (Snap/native/AppImage/Flatpak); a later Windows NOW client can use native Moonlight Windows builds with its own platform launcher.

MoonlightWeb (linckosz/moonlight-web) is an **optional server-side browser gateway** to Wolf/Sunshine. Good for browsers/limited Windows beta, but it has its *own* account/PIN/certificate, browser input and WebRTC stack. It is not just native Moonlight without an installer. Keep it as a supported fallback, not the exclusive client until independent browser latency, audio, input, security and multi-user acceptance tests match the native path.

## Engineering phases

- **A0, in draft PR:** read-only client Tailscale state; don't run `sudo tailscale up` on already-connected clients. Tests inject subprocess outcomes, no real tailnet side effects.
- **A1, next:** replace remaining terminal-oriented Tailscale sign-in with a verified provider browser-link/user-action flow; status/pending/error in the *current* wizard. Reuse existing Moonlight installs and pairing.
- **A2:** native Moonlight pairing assistance, verified server-specific authorization, no host admin socket exposed to clients; preserve reconnect.
- **A3:** service capability links and Jellyfin Quick Connect/normal provider auth through the existing Videos action. Don't install Jellyfin.
- **A4:** host installer’s owner email verification/optional approval notifications with an opt-in outbound mail transport; Codex device-code experience handled in separate Studio work.
- **A5:** Windows launcher with native Moonlight as preferred; optional MoonlightWeb fallback, including its own login/session handling.

## Acceptance

From an unconfigured client, setup identifies already-connected Tailscale correctly, never unnecessarily asks to sign in, recognizes existing Moonlight, selects any compatible host, pairs once, then reconnects through NOW's **existing** Steam button. All authentication states have explicit failures, manual fallbacks and reauthorization paths; no one is asked to use a terminal purely because the launcher did not expose the upstream sign-in mechanism.

References: [Tailscale sign-in](https://tailscale.com/docs/reference/tailscale-cli/up), [Wolf native pairing and API](https://games-on-whales.github.io/wolf/stable/dev/api.html), [Moonlight official clients](https://github.com/moonlight-stream/moonlight-qt/releases), [MoonlightWeb](https://github.com/linckosz/moonlight-web), [Jellyfin Quick Connect](https://jellyfin.org/docs/general/server/quick-connect/), [Codex device authorization](https://learn.chatgpt.com/docs/auth).
