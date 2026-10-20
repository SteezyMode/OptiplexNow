# OptiPlex NOW Linux Client MVP — locked release contract v1.0

**Frozen scope:** 2026-10-20. **Owner/tracking:** [#48](https://github.com/SteezyMode/OptiplexNow/issues/48). **Review branch:** [#49](https://github.com/SteezyMode/OptiplexNow/pull/49).  
**Definition:** An ordinary user can install NOW on a clean supported Debian/Ubuntu-family x86-64 Linux machine, join an authorized Tailscale network once, choose **their own already prepared Wolf host**, pair native Moonlight once, and thereafter click the **existing NOW Steam or Desktop action** to open an independent virtual session without controlling the host display. Reopening NOW or switching networks must not repeat setup unnecessarily.

**Change control:** This is the **sole controlling Linux client MVP plan**. Phase order, non-goals, and release criteria are fixed for v1.0. New features, architecture or priorities require an **explicit user-approved v1.1 amendment** in a separate PR/issue. Bug fixes required to satisfy a gate are not scope creep. A draft PR, successful CI, or an already working developer installation cannot be represented as shippable client acceptance.

## Required sequential gates

| Gate | Required work | Objective pass condition | PR/issue |
| --- | --- | --- | --- |
| **G0 — stabilize** | Audit *existing* draft stack; correct CI-visible and untested errors; preserve saved config, tray controls, encrypted backups and native client | Existing installed client upgrades with no regression. CI and tests green. Working reference server unchanged | #49, #51, #52, #55, #56 |
| **G1 — install/readiness** | Existing .deb installs GUI on fresh supported Linux; detect Tailscale state and native/Snap/AppImage/Flatpak Moonlight; user-confirmed installer for missing dependencies; show real failures, not assumed success | Fresh client reaches setup without copy/paste commands; existing dependencies are reused, not reinstalled | #48 |
| **G2 — Tailscale auth & server choice** | Skip login if enrolled; official browser authorization when necessary with secure local privilege handling and confirmed completion; pick authorized peer or manual/LAN hostname; remember server; don't identify all tailnet peers as NOW hosts | One official login at most, selected compatible server persists; offline/disconnected/denied recoverable | #51/#56; #48 |
| **G3 — native Wolf/Moonlight pairing** | Steam/desktop path does **not** require SSH user/key or host admin access; detect already-paired state or launch Moonlight native pairing with clear owner PIN action, then verify real session and reconnect | First-time stream succeeds; subsequent NOW Steam clicks reconnect; host physical screen unaffected; no Wolf installed on client | #48 |
| **G4 — optional service links** | Existing Videos/Jellyfin browser URL and optional Web Gaming configured **per server**; no personal server/domain defaults; retain old configurations or explicitly flag migration; don't require media auth for gaming | User selects own host/service addresses, sees clear unavailable/not-authenticated state, normal Jellyfin/browser login preserved | #55/#53; #50 |
| **G5 — clean client acceptance** | Disposable clean Linux Mint/Ubuntu/Pop!_OS x86-64 install plus one physical second client for video/audio/gamepad; inside and outside LAN; uninstall/reinstall, update and failure/recovery tests | All end-to-end checks recorded with exact OS, version, date, results; no production-server changes during test | #48 |
| **G6 — ship** | Review exact diff and dependencies, all scoped PRs to main in sequence, stable signed/reproducible artifact review (if available), immutable tag release workflow and documented known limitations | Publish **only** after G0–G5 passing and user approval; can roll back to 1.14.0 and restore existing settings | #48 |

**PR dependency/order:** #49 (this plan) → #51 (client auth state) → #52 (Moonlight Snap lookup) → #55 (Web Gaming URL) → #56 (experimental browser sign-in **only after proper multiline JSON/event/polkit tests**). Rebase and test each against main before merge. None automatically merged. Experimental server discovery/approval proposals #44–#47 are NOT client release dependencies.

**Known review blockers at freeze:**
- #56's first parser consumes `tailscale up --json` one line at a time; upstream emits **pretty-printed multi-line JSON objects**. Must fix, add realistic fixture tests, and validate on clean client. A CLI result is **not** a verified successful login until status is observed.
- #55 removes an implicitly hardcoded legacy Web Gaming URL. Avoid silently breaking current reference-machine shortcut; document a one-time configuration/migration path and test updates. No new installs should default to the developer's domain.
- Current Setup Wizard combines basic streaming with optional SSH administration and forces SSH username validation. Remove that prerequisite on the **gaming path**, without breaking existing optional SSH/SFTP and power actions.
- Some workflows only run when a draft targets `main`; stacked draft PR CI successes against `main` validate the **combined head** and do not by themselves prove independent PRs can be cherry-picked.
- UI labels, launcher status and stream/pairing claims must be derived from actual state, not just launching a subprocess.
- Release and settings/preset compatibility must be verified with real old `config.ini` and `.onp` samples.

## User journey to test

1. Download and install the versioned official `.deb` on a clean supported computer; launch existing GTK NOW UI.
2. Detect/reuse or offer explicit install of missing Tailscale and Moonlight, with errors/retry.
3. Authenticate with Tailscale's **upstream** login only if not already connected; do not store Tailscale account passwords/tokens in NOW.
4. Choose any allowed, prepared Wolf server (not automatically the developer's OptiPlex). Reuse saved connection on repeat launches. LAN/manual choice remains.
5. Pair native Moonlight *once*; ask owner to approve PIN via the real Wolf mechanism. Native Moonlight stores its certificate locally, NOT in ordinary client presets.
6. Click existing NOW **Steam**, then **Desktop**. Both connect to **independent Wolf virtual sessions**. Verify controls, sound, video and unaffected physical server desktop.
7. Optionally open configured Jellyfin URL and use its supported existing login/Quick Connect. Optional Web Gaming URL is configured by user, not invented from a tailnet login; browser/web stream requires a compatible server-side gateway.
8. Quit/reopen NOW; reconnect on home network, then over a separate network; handle down/offline/revoked host gracefully.

## Outside the fixed Linux MVP

- **New server installer** remains essential, but is a separately gated project; no Wolf/Docker/driver/GPU surgery on a running host in this client track.
- **Windows NOW client** is the immediate next product track after G6. Windows should use native Moonlight as primary, Tailscale for peer connectivity, browser Jellyfin and optional MoonlightWeb. Wolf remains on compatible Linux servers. Do not require Windows server hosting.
- **No MoonlightWeb fork/WebView** in v1; optional app-like window experimental later only after measuring gamepad, video/audio, fullscreen, pointer lock, certificate/TLS and latency. No public domain required for a private tailnet HTTP(S) service.
- **No universal NOW account, central hosted portal, guest management, mandatory SSH, owner email PIN infrastructure, Codex/OAuth emulation, Jellyfin/Dropped Needle server provisioning**. Future server-owner email OTP is a separately gated feature; native Tailscale, Moonlight, Jellyfin and Studio/Codex credential boundaries remain.
- No redesign of the current native tray/GTK client, no blanket package-format change, no storing secrets in GitHub, app config, presets or emails.

## Release decision

**PASS** only if independent source/CI checks, installed-package smoke test, fresh-device end-to-end stream, persistent reconnection, service URL isolation, packaging/upgrades and manual failure recovery **all** pass. Otherwise **NO SHIP**, with a specific failed gate and next corrective PR.

*Plan versions are additive: v1.0 remains fixed; if scope changes are approved, a new v1.1 plan links to this commit rather than rewriting the history of v1.0.*
