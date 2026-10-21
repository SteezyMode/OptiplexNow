# Physical client beta report: 2012 MacBook Air

**Test date:** October 21, 2026 (Japan time)  
**Test build:** OptiPlex NOW `v1.18.0` closed-beta Debian package  
**Test type:** Owner-assisted, real-device fresh Linux client connected to an **existing configured host**  
**Disposition:** **Partial pass with release-blocking defects.** Video playback and a Wolf desktop session work; Steam game streaming and hands-off onboarding do not. **Beta 1 is not accepted.**

## Test objective and environment

Determine whether a previously unconfigured Linux laptop can install NOW, connect through an existing Tailscale identity, discover and authorize an established Wolf host, install and pair Moonlight, and play games and personal video without terminal-based client onboarding. Record usability friction and actual results, not just service status.

| Dimension | Observed / reported |
| --- | --- |
| Client | 2012 11-inch MacBook Air, Intel Ivy Bridge HD Graphics 4000; 1366x768 display |
| Client OS | Linux Mint XFCE, distribution release not captured |
| NOW build | Tagged `v1.18.0` Linux amd64 `.deb`, installed and launched |
| Moonlight | Initially absent; guided per-user Flathub installation then manual selection of Moonlight **6.2.0 x86-64 AppImage** |
| Video decoder | Host `vainfo` confirms Intel `i965` VA-API with H.264 decode profiles. Flatpak log shows unsuccessful VA-API/Vulkan initialization and H.264 software fallback |
| Remote transport | Tailscale was **already installed, authenticated and connected** before this run |
| Gaming host | Owner's pre-existing Linux Wolf server, reachable through private Tailscale IP; infrastructure not reprovisioned |
| Video host | Owner's existing, configured Jellyfin service behind an HTTPS address; address omitted from this public report |
| Test operator | Owner-assisted tester; not an independent external user |
| Not captured | Exact Mint release, NOW package SHA256 verification, Moonlight Flatpak version, Wolf image digest, latency/FPS, device temperatures, exact elapsed onboarding time |

This was a **fresh NOW/Moonlight client setup**, not a clean OS installation, Tailscale first enrollment, fresh host deployment or Windows test. The live host was deliberately left intact.

## Result matrix

| Step / behavior | Outcome | Evidence / qualification |
| --- | --- | --- |
| Install `.deb` and open GUI | **Pass observed** | Client installed, tray and GTK app opened; no client terminal required for the normal initial wizard path |
| Existing Tailscale session recognized | **Pass observed** | Wizard displayed **TAILSCALE CONNECTED** |
| New Tailscale install/sign-in | **Not tested** | Already connected; create-account button remained prominent even when connected |
| Find existing server | **Pass with UX defects** | List included reachable OptiPlex host with game port indicator as well as unrelated/offline devices |
| SSH trust/authentication UI | **Prompt flow observed** | Graphical ED25519 host-key and Linux-account password dialogs displayed; wizard continued. Independent fingerprint-match confirmation, persisted key and reconnect not recorded |
| Wolf reachability | **Pass observed** | Games wizard displayed **WOLF REACHABLE** |
| Guided Moonlight installation | **Pass observed** | NOW added Flathub/installed the per-user Moonlight Flatpak; client was detected |
| Pair Flatpak Moonlight to Wolf | **Pass observed** | NOW initiated PIN pairing to chosen server; client appeared in Wolf pending list; owner explicitly authorized; Moonlight confirmed completion |
| Flatpak Steam streaming | **Fail** | Moonlight closed during stream. Collected client log shows broken VA-API/Vulkan initialization, software fallback and a lost control/session connection; no proven single root cause |
| Select and pair Moonlight 6.2.0 AppImage | **Pass with severe UX defects** | Downloaded executable AppImage, selected in NOW; paired after finding deeply obscured NOW approval window |
| AppImage Wolf XFCE Desktop stream | **Pass observed** | User confirmed streamed desktop works, establishing a usable Moonlight/Wolf video path on this legacy client |
| AppImage Steam game stream | **Fail / cause unknown** | Steam shortcut failed both via NOW and directly via AppImage. Successful XFCE streaming rules out total Moonlight/network incompatibility; Steam app/container startup not verified |
| Jellyfin service connectivity | **Pass observed** | Services wizard returned **RESPONDING** for a manually entered HTTPS video URL |
| Persist URL from wizard to settings | **Fail** | After wizard completion, Videos opened nothing; Videos URL in main Settings was empty. Manually entering and saving same URL fixed launch |
| Videos main button/tray shortcut | **Pass after manual fix** | Both had appeared inert when URL absent; saved URL enabled Jellyfin browser launch |
| Jellyfin content playback | **Pass observed** | User opened content and reported it worked well; audio was not independently measured |
| Final setup-complete screen | **Acceptable, limited review** | Tester clicked past it, reported appearance acceptable; no systematic copy/navigation review |
| App window from tray | **Fail UX** | Tray activation displayed window as fullscreen/unresizable on the client's 1366x768 XFCE desktop |
| Restart/upgrade/pairing persistence | **Not tested** | No reboot, reconnect, upgrade or previously-paired retry recorded |
| Controlled/independent host display | **Not tested in this run** | No physical host-desktop interference, simultaneous game/media/download or owner/member permission checks |
| New-host installation, downloader, VPN isolation, remote files | **Not tested** | Reference host was already provisioned; no fresh host or alpha three-pillar acceptance |

## Reproduction sequence and findings

### 1. Tailscale, server choice and SSH

NOW identified the already-connected Tailscale account and discovered the intended host with an available Wolf port. The discovery view also exposed unrelated and offline Tailscale devices, and the user had to enter the host Linux SSH username manually. On the Server page, **Music Server Profiles (This PC)** distracted from the two real intents: find an existing server or set up a new one. That button was subsequently removed on `main` by [PR #142](https://github.com/SteezyMode/OptiplexNow/pull/142); it is **still present in the tested v1.18.0 binary**. [Issue #141](https://github.com/SteezyMode/OptiplexNow/issues/141) tracks the broader redesign.

The Secure Access page successfully showed native trust/password UI, but prominently displayed three wake-relay fields and a separate relay authorization control. Proposed fix: collapsed **Wake Options (Optional)** section, leaving SSH authorization primary ([PR #143](https://github.com/SteezyMode/OptiplexNow/pull/143), pending when this report was written). Do not bypass SSH host-key validation or infer administrative access from Tailscale membership.

### 2. Moonlight install and Wolf pairing

The intended host was already chosen in NOW, yet the standalone Moonlight GUI endlessly attempted local discovery. Local broadcasts are not a reliable Tailscale remote-discovery mechanism. NOW's **Connect to Game Host / Pair Wolf** path correctly passed the chosen address to Moonlight's command-line pairing operation, avoiding manual IP entry.

Functional pairing was possible with both Flatpak and AppImage, but **Moonlight's foreground PIN window obscured NOW's separate Wolf authorization dialog**. The user had to find NOW through the app tray, manually **Refresh Clients**, select the correct pending device, approve it and return to Moonlight to acknowledge successful pairing. The AppImage retry produced especially obstructive focus behavior and an apparent freeze until the authorization window was located. It was an **inaccessible window**, not a confirmed application deadlock.

After success, the wizard still showed **Moonlight [installed] / Wolf Reachable** and buttons suggesting pairing was unfinished. Main Games calls the action **Pair Wolf**, not the wizard's **Connect to Game Host**. Expected: one NOW-managed pairing flow with visible state, protected explicit authorization, bounded auto-refresh every few seconds with manual refresh retained, verified completion, then **Launch Games** or **Continue Setup**.

References: [#144 pairing focus and auto-refresh](https://github.com/SteezyMode/OptiplexNow/issues/144), [#145 paired-state/completion](https://github.com/SteezyMode/OptiplexNow/issues/145).

### 3. Decoder and gaming

Host-side `vainfo` succeeded with `Intel i965 driver for Intel(R) Ivybridge Mobile - 2.4.1`, reporting H.264 decode support. By contrast the Moonlight Flatpak log showed **No suitable Vulkan devices found**, **Failed to initialize VAAPI**, inability to initialize V4L2 M2M decoder and fallback to FFmpeg software H.264 decoding. The same log also showed a successful launch/stream handshake followed by control-connection errors. Therefore **it does not establish a decoder-only explanation** for the Flatpak session ending.

The older **6.2.0 AppImage** was executable and detected by NOW. Wolf **XFCE Desktop streamed successfully**. Steam failed to open or stream from both NOW and a direct Moonlight attempt. A check for `steam` in the streamed XFCE shell returned no path, but that **does not prove Steam is absent from Wolf's separate Steam application/container**. Exact failing component is still unknown. Diagnose configured Wolf app launch/container logs through normal host administration and test the existing deployment **read-only first**. Do not change the working reference host, reinstall Steam, or prescribe a newer GPU as the fix without evidence.

No verified game FPS, playable input, game audio, thermal profile or simultaneous independent physical-host desktop use was recorded. Gaming acceptance is **open**.

### 4. Video and wizard persistence

The tester entered the owner-provided Jellyfin HTTPS URL on the Services wizard page; **CHECK SERVICES** reported **RESPONDING**. After finishing/closing setup, **Videos** opened nothing from both launcher and tray. Main Settings showed an **empty Videos URL**. The tester added the same URL in Settings; Videos opened Jellyfin and actual Jellyfin content played successfully (audio not independently measured). This is concrete evidence that the wizard's validated field was not persisted in the normal configuration in this test, not a Jellyfin or browser outage. [Issue #147](https://github.com/SteezyMode/OptiplexNow/issues/147).

**Broader product issue:** even after persistence is fixed, requiring the owner to know and type a Jellyfin URL is unsuitable for an ordinary consumer. Many target hosts will have **no Jellyfin installation at all**. For public alpha, NOW should offer graphical **Set Up My Video Library** for a clean compatible host, or **Use Existing Jellyfin** with safe owner-confirmed detection. Once enrolled, approved client devices should receive the authorized video endpoint through trusted server metadata or connection setup, with no required public domain, reverse proxy or URL typing. Keep manual URL input as an advanced option. Preserve existing stacks and real Jellyfin authentication; never invent or leak owner URLs/credentials. [Issue #148](https://github.com/SteezyMode/OptiplexNow/issues/148). **Neither managed installation nor automatic discovery ships in v1.18.0.**

### 5. Window and completion behavior

On XFCE, clicking the tray icon restored NOW as a large non-resizable/fullscreen window ([#146](https://github.com/SteezyMode/OptiplexNow/issues/146)). Separately, final setup completion was reported as acceptable but clicked through, not scrutinized. Reopening the wizard should present saved progress and allow returning to incomplete Video/Game setup without repeated authorization or hidden actions.

## Defect triage and proposed next work

| Priority | Finding | Tracking | Exit condition |
| --- | --- | --- | --- |
| **P0: gaming acceptance blocker** | Steam stream fails although Wolf XFCE streams | [#76](https://github.com/SteezyMode/OptiplexNow/issues/76), [#145](https://github.com/SteezyMode/OptiplexNow/issues/145) | Real Steam session with verified video, game input and audio; logs identify/fix failure |
| **P1: critical setup UX** | NOW authorization dialog buried by Moonlight PIN, manual client refresh, duplicate confirmation | [#144](https://github.com/SteezyMode/OptiplexNow/issues/144) | One visible, bounded, recoverable pairing flow; owner chooses and approves right client |
| **P1: functionality** | Videos wizard field not saved despite successful health check | [#147](https://github.com/SteezyMode/OptiplexNow/issues/147) | Save survives Finish, wizard reopen, app restart and upgrade |
| **P1: completion clarity** | No verified game-paired success state or launch CTA | [#145](https://github.com/SteezyMode/OptiplexNow/issues/145) | Verify actual pairing and show appropriate Play/Continue action |
| **P2: window usability** | Tray restores full-size unresizable window | [#146](https://github.com/SteezyMode/OptiplexNow/issues/146) | Restore normal resizable previous geometry on XFCE |
| **P2: onboarding clarity** | Manual SSH user, unrelated peers, extra music and wake controls | [#141](https://github.com/SteezyMode/OptiplexNow/issues/141), [PR #142](https://github.com/SteezyMode/OptiplexNow/pull/142), [PR #143](https://github.com/SteezyMode/OptiplexNow/pull/143) | Find Existing / Set Up New are primary; optional controls hidden; trusted metadata improves enrollment |
| **Public-alpha milestone** | User must install Jellyfin separately and enter URL manually | [#148](https://github.com/SteezyMode/OptiplexNow/issues/148), [#137](https://github.com/SteezyMode/OptiplexNow/issues/137) | Guided safe Jellyfin install or existing-server adoption, client Video setup without URL typing |

P0/P1/P2 reflect product triage for this test, **not** GitHub project label state. CI and merges may occur independently. Bugs in already installed `v1.18.0` do not disappear when a change is merged to `main`; fixes require a later packaged build and physical regression.

## Follow-up acceptance protocol

1. **Client regression after fixes:** Install a later tagged package on the same 1366x768 Mint client while preserving configuration and paired identity. Verify settings persisted, window resizes, pairing status and existing device reconnect without a second PIN.
2. **Streaming diagnosis:** Collect non-destructive Wolf Steam app logs and current app definition; test direct Steam streaming through AppImage and NOW. Record visible frames, real game input, audio, duration, and host physical-desktop independence. Revisit Flatpak `i965` compatibility separately. Do not claim a specific Moonlight build is universally supported based on a single legacy GPU.
3. **Video regression:** Test clean Video field save from wizard, application restart and package upgrade. Test first-time Jellyfin sign-in and actual playback on a second approved device.
4. **Independent tester:** Complete the whole wizard without explanations or a terminal; record every dialog/focus transition, time, manual intervention, failed/canceled flow and return path. Do not claim a 15-minute first-stream result without measuring it.
5. **Public-alpha host work (separate track):** On a **new** disposable compatible host, test managed Wolf, managed/existing Jellyfin and VPN-isolated downloader plus owner/member permissions. Never run a destructive fresh-host installer on the existing reference OptiPlex.

## Decision

The current v1.18.0 client demonstrated **real Jellyfin playback** and **Wolf XFCE remote desktop streaming** after substantial owner assistance. Server discovery, graphical pairing and a guided Moonlight installation were usable in parts but not frictionless. **Steam game-stream acceptance remains failed, video URL saving remains broken, and clean-host/video provisioning remain unimplemented.** This evidence supports focused remediation, **not** a finished beta or the three-pillar public alpha.

See [Beta acceptance](BETA-ACCEPTANCE.md), [Current status](CURRENT-STATUS.md), [Public alpha](PUBLIC-ALPHA.md), and the original [client acceptance issue #76](https://github.com/SteezyMode/OptiplexNow/issues/76).
