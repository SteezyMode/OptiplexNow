# NOW client installer MVP — Tailscale-first onboarding

**Status:** Development roadmap; not a shipped claim. **Tracking:** [Issue #48](https://github.com/SteezyMode/OptiplexNow/issues/48).  
**Scope:** Make the existing working Linux NOW client easy to set up against **any compatible already-running user/server machine**, without redesigning the GTK/tray GUI or modifying a production host. A guided *new server installer* remains a separate essential product track.

## North-star client experience

1. Install NOW on a fresh supported Linux computer.
2. In the **existing NOW Setup Wizard**, detect/install Tailscale if absent; if already enrolled and connected, **skip login**. Otherwise guide **one official Tailscale sign-in**, never request the user's account password inside NOW.
3. Use the authorized Tailscale peer inventory to populate existing server selection; identify a compatible NOW host **only after a narrow, authenticated host capability check** when such an agent has been developed and tested. Retain the existing legacy device picker until then, clearly labelled as a device list.
4. Select the desired server and remember its identity/hostname. Server endpoints and supported service actions should be **host-specific**, not hardcoded to the reference OptiPlex or silently assigned to arbitrary tailnet peers.
5. Offer **Steam over Moonlight/Wolf** as the first essential flow. Reuse an existing native/Snap/AppImage/Flatpak Moonlight installation; guide the initial native Moonlight pairing **once** where not yet paired, then preserve its local certificate.
6. Launch Steam in Wolf's **virtual/independent session**, not by stealing the server's visible desktop. Relaunch NOW and stream again without signing in, typing an IP, setting up SSH or repairing anything.
7. Existing service links (e.g. **Jellyfin**, then optionally Dropped Needle) can use the selected host's configured service location. Those services may need their **own initial login**; Tailscale network identity alone is **not** a Jellyfin account or native Moonlight certificate. Save/reuse service credentials only using service-supported client storage, not a bundled server admin password.

**One primary Tailscale sign-in** is the connectivity/discovery *UX anchor*, **not** blanket authorization to every daemon on a remote computer. Enforce each service's native first-time authorization rather than silently bypassing security. Tailscale itself cannot guarantee a host is configured, powered on, reachable, or running any given service. Manual IP and LAN-only fallback remain available.

## Current code baseline (verified against main, 2026-10-20)

| What already works or exists | Source | Installer improvement |
| --- | --- | --- |
| Native amd64 Debian package, GTK/tray and system integration | `package.py`, `src/main.c` | Preserve package/upgrades, do not reinvent install |
| Existing Settings → Setup Wizard | `src/main.c` | Improve this wizard; **no new dashboard or GUI replacement** |
| Tailscale device list | `src/find-servers.py` | Keep as legacy picker, add connected-state awareness and refresh |
| Tailscale setup button | `setup_tailscale()` | Currently executes `sudo tailscale up` when installed; must avoid redundant sign-in |
| Moonlight detection | `moonlight_mode()` | Already handles executable on PATH, AppImage, Flatpak; accommodate Snap under desktop PATH |
| Moonlight installer action | `install_moonlight()` | Already offers user-triggered Flatpak installation; verify result, no forced format change |
| Moonlight pairing and Steam launch | `pair_wolf()`, `launch_wolf_app("Steam")` | Already present and established; preserve behavior, improve first-run status/error handling |
| Configured web/media shortcuts, SSH/SFTP, remote status | `src/main.c` | Keep as-is; **do not require SSH setup for basic games** |
| New server provisioning | GUI placeholder | Separate guided-server-installation track, not a prerequisite here |

## Delivery milestones (separate reviewable PRs)

### P0 — Setup readiness contract and regression tests
- Detect **new installation** and **already configured client** states without overwriting stored host, preferred Moonlight or pairing.
- Add deterministic tests for dependency detection, GUI compatibility and saved configuration. Preserve current executable, settings path, tray controls and existing actions.
- Keep CI isolated from the developer's real server.

### P1 — Reuse or install Tailscale/Moonlight
- One read-only local dependency/state probe:
  - Tailscale missing / installed but disconnected / authorized and connected / unavailable.
  - Moonlight missing / native including Snap / AppImage / Flatpak, with actual executable usability checked.
- Detect Snap even if launching from desktop does not inherit `/snap/bin` in PATH.
- Show compact readiness and **user-confirmed** install/login actions inside current Setup Wizard. Use official installation processes; never silently install dependencies.
- New `.deb` must **not** require Tailscale or Moonlight package installation to work for offline/LAN and non-gaming actions.

### P2 — One Tailscale login, server discovery and saved selection
- When already connected, never run `tailscale up` just to display the login page again.
- When not connected, open the official Tailscale login and then refresh peer selection.
- Existing picker uses authorized peers, with explicit compatibility status. Future server capability information can be served by a narrowly scoped read-only NOW presence endpoint, independently reviewed and tested; not required for the first legacy-picker demo.
- Save stable server selection; handle a missing/offline/revoked host with clear, recoverable feedback. Manual hostname/LAN mode stays.
- Do not require SSH credentials, privileged approvals, or host management on the main gaming path.

### P3 — Native first-time pairing, Steam and reconnect
- Select existing usable Moonlight backend rather than reinstalling or switching packaging.
- Run Moonlight native pairing once when needed, keep per-device Moonlight credential local, and never promise that Tailscale login automatically pairs a different protocol.
- Click existing **Steam** NOW shortcut → Wolf virtual session streams from chosen host. Verify audio, gamepad, usable FPS and that host display stays unaffected.
- After application/network restart or switching between home/remote, the same saved host and pairing state continue working.

### P4 — Service shortcuts without provisioning
- **Jellyfin first:** use existing Videos action; optionally populate URL from a compatible server's explicit advertisement/config, otherwise accept manual URL. Jellyfin authenticates users using its own existing mechanism. Never copy admin credentials.
- **Dropped Needle later:** same principle with existing configurable Music action. No media server install, library scan, Docker orchestration or account-manager implementation in client MVP.

### P5 — Acceptance and release
- Disposable clean Mint/Ubuntu/Pop!_OS amd64 install: `.deb` → existing wizard → optional Tailscale login → choose an already prepared Wolf server → pair Moonlight once → Steam → quit/relaunch → Steam again.
- Upgrade an already configured client (including Snap Moonlight) without changing installed package format, saved host, pairing or GUI shortcuts.
- Test LAN and genuine outside-LAN connectivity, video/audio/input, Linux tray environments, online/offline, login failure, unsupported packages and permission-denied states.
- CI confirms package/build/regressions; **manual real-client streaming is required** to claim end-to-end success. Only publish via the existing immutable tag-release workflow after approval.

## Out of scope for this installer milestone

- Fresh server provisioning; Wolf/GPU/container installation; driver surgery; Jellyfin/Dropped Needle deployment; always-on pairing broker; guest/tenant account management; new tile dashboards; central NOW account; native Windows port; changes to running developer host.
- Avoid conflating **Tailscale sign-in** (network/device identity), **native Moonlight pairing** (streaming authorization), **Jellyfin sign-in** (media account), and **SSH keys** (optional privileged management).
- Draft experiments #44–#47 can be evaluated independently and **must not become mandatory** for the existing client installation MVP.

## Definition of done

A new Linux user can install NOW, sign into Tailscale once if needed, select an existing permitted compatible server through the current GUI, complete Moonlight pairing once, and thereafter open the existing NOW tray and launch Steam in an independent remote Wolf session at home or away. Media shortcuts are host-configurable but do not block game onboarding. No server changes or SSH administration necessary for the ordinary client-only path.
