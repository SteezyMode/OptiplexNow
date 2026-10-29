## October 29 — PR backlog and alpha release-contract reconciliation

**Current release:** Official Latest remains [v1.21.9](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.21.9), working on the configured owner environment per owner report. More recent fresh-client wizard corrections (#226/#227) are in `main`, not in the published .deb. Last verified merged-main check: [CI #40873360566](https://github.com/SteezyMode/OptiplexNow/actions/runs/40873360566) passed both jobs. **Private Alpha 1 remains NOT ACCEPTED.**

**Backlog audit:** Reviewed 180 PRs (145 merged at audit, 31 previously closed-unmerged, four previously open). Closed stale, 180-commit-behind PRs [#51](https://github.com/SteezyMode/OptiplexNow/pull/51), [#57](https://github.com/SteezyMode/OptiplexNow/pull/57), [#58](https://github.com/SteezyMode/OptiplexNow/pull/58) as superseded, with issue-linked rationale; left [#194](https://github.com/SteezyMode/OptiplexNow/pull/194) open for **port/review, never direct merge**, because its Wolf input-isolation rules could help clean-host gamepad safety. Legacy closed branches #64 auto-trust and #62 remote owner broker must not be resurrected in place of the verified, opt-in certificate/phone-bound owner gate. Unmerged #225 was already closed as superseded by #226/#227. Historical entries below preserve what was known when written; they are **not** current release status unless explicitly marked.

**Single authoritative alpha definition:** `PRIVATE-ALPHA.md` now locks to one owner on owner-operated devices, with unapproved requests denied; **no invited guest/member role provisioning**. `PRODUCT.md` and the release gate now match. Owner Linux-account SFTP stays available under ordinary account permissions; narrower NOW-native download/file requests are confined to approved roots. Explicit nested safe destinations remain core, refinements to their presentation are deferred. Owner-approved QR plus separate Wolf pairing still need physical first-client testing. Future **Devices & Access**, phone recovery wizard, household roles and email remain post-alpha.

**Next physical gate:** Using a genuinely disposable Linux user profile and an owner-controlled Tailscale phone, test initial Wolf pair → new restricted key phone review → Verify Access → real Steam video/audio/controller/reconnect, without copying keys or modifying the working OptiPlex stack. After that test host-independent Jellyfin playback and VPN fail-closed downloads; the **separate disposable clean-host graphical install** is still mandatory. No live host changes, release tag or new .deb from this cleanup.

### Open-issue classification after October 29 triage (40 open; no blanket closures)

| Bucket | Issues | Decision |
| --- | --- | --- |
| **17 alpha/release acceptance and real physical tests** | #192, #191, #190, #189, #187, #171, #154, #152, #148, #145, #144, #141, #137, #98, #76, #10, #8 | Preserve until the documented end-to-end check succeeds. Some features are already code-complete; an open ticket does not authorize redesigning them. |
| **3 candidate fixes requiring narrow UI/device verification** | #146, #70, #66 | Existing GTK/tray implementations appear to address much of the historical request; verify actual Mint/Pop screen behavior before closure. |
| **20 deferred, optional or conditional hardening tasks** | #193, #188, #185, #170, #157, #155, #153, #94, #85, #68, #59, #53, #38, #37, #28, #21, #15, #14, #12, #11 | Not Private Alpha 1 requirements; revisit only after owner alpha or when a concrete blocker demands it. |
| **Closed superseded product implementation** | #186 | Native Downloads replaces mandatory embedded VueTorrent; Advanced remains optional. Closed as `not_planned` with explanatory comment, not as a completed alpha gate. |

Current cross-issue decision: the older #76 **ten-minute** either-Steam-or-Jellyfin Beta 1 target was replaced by one-owner Private Alpha 1's **approximately fifteen-minute** first authenticated game-stream target from two OS-ready supported machines. Issue #94's NOW-account/email-login model is deferred in favor of current trusted QR plus a later in-NOW Devices & Access approval screen. #194 is the only remaining open code PR and must be ported/tested against current host installer, not blindly merged. The **alpha contract** in `PRIVATE-ALPHA.md` controls when issue descriptions or older beta plans conflict.

## October 29 — First-run readiness and future owner-approval decision (merged main, physical acceptance open)

**Observed source behavior:** On a clean profile the GTK setup assistant can persist a server address and finish without proving Moonlight pairing or the restricted NOW owner credential. The old Finish header said “CONNECTION SETTINGS SAVED,” which a first-time user could mistake for full access. The Server page still asks for a Linux/SSH username, a necessary owner-alpha implementation detail but not a guest login. A separate explicit **Request Owner Approval (Phone QR)** action was merged in PR #226; PR-head and merged-main CI passed. The official v1.21.9 .deb **does not** contain that action, and no physical new-credential approval has been accepted.

**Scoped correction:** Replace the misleading Finish header with **NEXT: VERIFY DEVICE ACCESS**, explain that Wolf pairing and phone-approved restricted host access are distinct, and identify the Linux server account as an owner-alpha coordinate, not an administrative permission grant. Add regression tests proving a Tailnet authorization refusal cannot silently downgrade to ordinary SSH approval; verify the existing absence-of-listener fallback does not claim success when owner SSH is untrusted. Do not infer access from the Finish page, an existing key file or Wolf pairing. No host configuration, Steam, VPN, Tailscale, Jellyfin, downloader or actual user credential changed.

**Future decision, not Alpha 1 implementation:** Retain private phone QR; later add approval from an already-authenticated owner instance under **Settings → Devices & Access** inside NOW, plus owner-local lost/replacement-phone recovery. Both paths share the server authorization boundary. Ordinary clients and merely Wolf-paired/Tailscale-connected devices cannot approve themselves. Shared SFTP folders and household Admin/User grants require server-side isolation and remain post-alpha. See PRODUCT.md; no new hosted account service or extra app is required.

**Evidence and next action:** PR #227 and merged-main CI [40873360566](https://github.com/SteezyMode/OptiplexNow/actions/runs/40873360566) passed both jobs; still **no real new-client phone grant or game acceptance**. Next, physical fresh-user enrollment on disposable client profile: Tailnet selection, Wolf pairing, restricted key phone approval, Verify Access, live Steam/reconnect. The actual QR listener remains an opt-in host pilot. Keep **Private Alpha 1: NOT ACCEPTED** until these and disposable clean-host/video/download safety tests pass. Preserve v1.21.9 as official rollback.

## October 29 — Fresh-client onboarding entry point audit (merged #226; physical test outstanding)

**Observed source-level blocker:** The first-run GTK assistant exposes Wolf pairing but no direct owner-approval action. Newly installed users must discover a separate, buried Settings > Gaming & Streaming action to request their NOW restricted owner credential. Worse, the first-run copy still says no-SSH client enrollment has not been implemented despite the existing *opt-in* Tailscale owner-phone QR request/approval helper. This is a discoverability and misleading-status defect, **not** proof that live owner enrollment is complete.

**Scoped change:** Add an explicit **REQUEST OWNER APPROVAL (PHONE QR)** action directly after Wolf pairing in the first-run Games page. It opens the **existing** installed owner-enrollment window with the wizard's currently entered (validated) server address and SSH username; it does not prematurely save a connection or authorize a device. The owner must still have the private Tailscale listener deliberately configured, the client needs Wolf pairing, and the owner phone independently approves. Without that listener, existing host-local owner review remains the restricted fallback. Existing Games settings entry point uses the same launcher, and no authorization policy or private key is changed. Update first-run copy to distinguish Wolf pairing, NOW restricted access and host opt-in readiness.

**Tests:** Source regression checks first-run action wiring, staged host validation, absence of the false “not implemented” sentence, preservation of Finish-only config save. Disposable Xvfb GUI startup test now waits for the *first-run setup window*, not just the Dashboard. PR #226 and merged-main CI passed; **real fresh-key QR approval, real Moonlight certificate pairing and seamless first-game launch are still physically unverified**. This is preparatory work for the user's next safe, isolated clean-client test, not a public installer release. Existing v1.21.9 remains official Latest and unchanged.

## October 29 — Search returns only an initial ~25 hits while saying "searching" (PR #224)

**Actual owner observation (v1.21.8):** The old paged client appeared to find more results that were inaccessible; the post-scrolling releases displayed about 25 rows and then remained on "searching..." without more visible arrivals. A source comparison confirmed v1.21.6 → v1.21.8 did not alter search backend, but current host Search allows only 40 polls / 50 seconds. GTK also fails to replace its "searching" status when a bounded run completes while qBittorrent still reports Running. Thus the owner-observed truncation is not proven to be caused by the scrolling change; the incomplete search window and misleading completion status are confirmed code defects.

**Candidate remedy:** Extend one owner-authenticated, qBittorrent-SID-bound, offset-based search to at most 120 polls / 150 seconds, cap 1,000 results and preserve magnet-only operations, cleanup and both installed search plugins. Increase trusted client stream frame bound accordingly. GTK shows source-reported total vs received count and displays an explicit bounded-window completion message, while keeping the scroll and sort. Dashboard badge matches Downloads literally: VPN: HEALTHY / UNVERIFIED / UNKNOWN.

**Evidence classification:** PR #224 merged and its validated release v1.21.9 exists; the owner reported this version working well, but an independently fresh-client acceptance and definitive search-provider result count remain unverified; do not claim a given search will necessarily return more than 25 if qBittorrent's enabled providers return only 25. Do not reconfigure VPN, Wolf, downloads or plugin engines. Roll back client to v1.21.8 if regressions appear.

## October 29 — Alpha polish (PR #223 merged into v1.21.9; remaining physical checks pending)

The owner selected browser-first Videos. The native VIDEOS landing now has one OPEN VIDEO LIBRARY action invoking restricted host-verified Jellyfin discovery in the default browser, a VIDEO SETTINGS expander and server-settings link. The broken embedded player UI, in-app action and tray toggle are no longer offered. Existing private tray preference files remain unchanged, and the Videos tray shortcut uses the same browser path.

A shared package-owned dark GTK3 stylesheet covers otherwise unstyled controls throughout NOW desktop, Host Setup, owner approval/enrollment, video host setup and host upgrade dialogs. Existing named navigation/primary/danger styling retains precedence. The Dashboard now displays DOWNLOAD VPN state beside Server Online/Offline while Downloads retains its detailed readout. Both are host-health observations, not VPN egress or kill-switch verification. Unknown connectivity never displays as healthy. No live host or torrent service changes.

Status: PR #223 merged with CI; published v1.21.9 includes its UI. The owner reports the current application works well; separate physical Mint/Pop appearance and clean-client acceptance checks are not recorded. Owner reports Search works after backend migration, and v1.21.7 already fixes scrolling. Fresh independent client, Jellyfin playback and disposable clean-host/VPN outage acceptance remain open. Natsuyo's Ubuntu laptop is suitable for supervised installation and browser playback only, not owner-privilege enrollment.

## October 29 — Search scroll while progressive results arrive (PR #222; pending physical verification)

**User-observed defect in v1.21.6:** Search is functional and the host now returns progressive plugin results, but only the first 20 results are visible. Previous/Next pagination controls at the bottom of the viewport do not provide the expected scrolling-through-results behavior. Videos embedded playback also reportedly fails; browser playback is the existing fallback and this secondary issue is not asserted fixed by this patch.

**Focused client fix:** Remove explicit 20-row page hiding/pager; keep *all* validated accumulated results (up to 1,000) in the existing vertically expanding native GTK scroll window. Maintain sortable Name/Size/Seeders/Leechers/Published headers. Later APPEND frames keep the scroll position (except clamping to normal bounds); an explicit new sort returns to the top. Existing magnet-only action and destination authorization, qBittorrent plugins, VPN, host broker and refresh behavior are untouched.

**Evidence needed:** updated Xvfb GTK regression covers 100 initially visible results, scrolling, 25 appended results, completed stream and sorting. Re-run package, source and sanitizers CI; then check MacBook physical search. No back-end update or host restart needed for this UI-only release.

## October 29 — Videos and Downloads native button styling consistency (PR #221)

**Observed issue:** On a working v1.21.5 owner client, Videos OPEN and some native Downloads buttons rendered bright white stock GTK controls rather than NOW's existing charcoal-and-coral theme. **User physically confirmed Downloads Search works after the unified host package update**, so this issue is strictly visual and does not call for search protocol or server changes.

**Scoped implementation:** Explicit shared NOW action button classes with hover/focus/active/disabled states for Videos and Downloads toolbar/Search/results headers/pagination/queue actions/folder pickers. Keep primary coral action and muted dark secondary buttons, preserving all existing callbacks and host behavior. GTK/package smoke and regression tests must pass. Real GTK on Linux Mint/Pop should confirm visual appearance after install; no client/host service changes were made by this PR.

## October 29 — One-deb host/client ownership (development PR #220, NOT released)

**Owner-observed packaging defect:** The official v1.21.4 desktop .deb upgrades all three devices' UI but leaves the working OptiPlex's restricted SSH forced-command broker pinned to an unmanaged home-directory Python copy. Thus new Search/Transfers can be incompatible even with an up-to-date host desktop.

**New code (PR #220, source/CI stage):** The *same* NOW Debian package now includes the complete restricted owner Games/Jellyfin/Downloads broker and its exact imported dependencies under root-owned `/usr/lib/optiplex-now/owner-bridge`. Package install itself never alters the owner's forced-command SSH authorized_keys, policy, approved devices, Steam workspace, Jellyfin, qBittorrent plugins/containers or Gluetun. NOW Host Setup includes an explicit owner-confirmed **USE PACKAGED UPDATES** step for previously adopted owner-only hosts: it rewrites only recognized restricted broker paths with durable private `authorized_keys` backup and refusal/rollback on uncertain state. Once migrated, future .deb upgrades update host and client code together, not separate source copies. Clean-host enrollment and host services still require independent GUI acceptance; no claim of universal turnkey provisioning.

**Acceptance pending:** Exact-head CI, installed package imports, physical OptiPlex one-time switch, two-client verified Games/Video/Transfers/Search behavior, clean host and VPN fail-closed physical tests. Revert to backed-up authorized_keys only with owner review if needed; changing just the client .deb before the host migration does NOT upgrade the running broker.

## October 29 — Native Videos landing and per-device tray target (source-level)

**Owner-selected UX:** The Videos main tab is a native landing page, with **Watch in NOW** and **Open in Browser**, similar to Games. A collapsed **Video Settings** section selects the Videos tray shortcut target (browser, default; or NOW), saved per Linux account using the existing private tray preferences directory. The in-app path reuses the restricted owner Jellyfin endpoint discovery and NOW's optional same-origin WebKitGTK view. If WebKit is absent or the discovered endpoint cannot be embedded securely, the normal browser remains available. Navigating away stops hidden embedded playback. No Jellyfin credentials, root paths, server containers or owner keys are changed by these code commits.

**Evidence:** Source present on `main`; GTK/packaging CI and preference regression under review. **No real Jellyfin playback, subtitle, audio, full-screen, codec compatibility or keyboard/controller navigation has been physically exercised through WebKit** on the MacBook Air/Mac mini. The browser path was already working. The deployed reference host is untouched.

**Immediate next acceptance:** Keep one official Current Alpha release. Verify GitHub CI; then physically test the native Videos page and in-app video/audio on an approved client while checking WebKit availability and browser fallback. In parallel the new progressive qBittorrent Search client requires verified matching host modules and the two critical installed search plugins. Do not call either workflow accepted solely from CI.

## October 29 — Search P2 follow-up: broaden results on demand and sort by publication date

**Owner-observed problem:** Current Alpha v1.21.1 Search physically fills the page and responds within a few seconds, but typically returns ~25 partial results and can prioritize huge 2160p files. The fast-return backend intentionally stops its search job on the first nonempty results, so merely sorting the short subset cannot expose later smaller 1080p results.

**Source-level change under PR #219 (not yet host/device accepted):** Keep the fast default; allow an explicit bounded **More Results** search of enabled qBittorrent plugins, up to 100 results and twelve polls. Native Search sorts the returned batch by smaller/larger size, highest seed count, and **newest/oldest publication date**. qBittorrent supplies `pubDate` when plugins support it; this is not the date added to the user's transfer queue. Missing dates sort last, and the new parser accepts legacy six-field hosts. Exact owner authorization, bounded magnet-only data and transient search-job cleanup are unchanged. CI status is tracked on PR #219.

**Release and safety:** v1.21.1 is still the published Current Alpha; no replacement release or reference-host mutation has been made. The thorough-mode host broker and search module must be deployed after read-only checks and safe backups, then validated physically. P2 Transfers actions and broad Private Alpha 1 acceptance remain open.

## October 29 — P2 Downloads integrated source, host acceptance outstanding

**Actual reference-host evidence:** Using the installed PR #214 client on the 2012 Mint MacBook Air, the owner physically demonstrated search results, selecting a media subfolder before Add, and a torrent progressing to 90% in VueTorrent; the native Downloads queue was a static snapshot, not a proven live monitor. Separate read-only checks confirmed qBittorrent shares Gluetun's network namespace, real egress IP differs from host, routing selects `tun0`, and the firewall's OUTPUT policy is DROP with an explicit tunnel exception. This is consistent with VPN isolation, **not** a deliberate tunnel-failure/kill-switch test.

**Source integrated, not host accepted:** PR #215 merged to `main` at `93cb75523d6f0a619aaf1fb842b64523a9531c8f` after successful exact-head CI #40824298035 and final main CI #40824498189. It adds permanent Dashboard navigation, separate Transfers and Search, three-second visible Transfers polling, speed/ETA/seeders, an owner-only exact-hash management channel, a folder-confirmation adjustment and a read-only VPN status popover. **None of the new transfer actions, live refresh or VPN indicator has been physically accepted against the deployed host.** The new eight-field queue and restricted management broker require a supervised matching host-module upgrade; an upgraded .deb alone will not work reliably.

**Current release and next P2 check (updated October 29):** v1.21.0 **was published as the official GitHub Latest Current Alpha** with one prominent .deb link. It is installable but Private Alpha 1 is not accepted: the deployed reference host still lacks the matching restricted management and live queue modules. PR #218 addresses the owner's newly observed tiny Search results area and mandatory full-length 12-second wait; code and regression tests are present, but the revised client and host `download_search.py` are not yet physically exercised together. Deploy reviewed modules with backup, validate live Transfers, search, safe file actions and owner access, then accept the P2 user journey. No host Docker or VPN configuration was changed by these source commits. Owner Games/Video fresh-client and P3 acceptance gates remain open.

## October 26 — Private QR iPhone physical test and v1.20.0 closed-beta promotion

**Physical reference-host progress:** Owner OptiPlex installed the version-pinned isolated host QR pilot at revision `1116d2a0376597c08a2e4c278521a8ab70a51ffd`. Exact checkout verified, private module inventory installed, non-listening preflight passed, and the owner manually started a foreground listener bound only to host Tailscale IPv4 port 18793. This was not a systemd service or a main client package modification. It may still be running; **check its terminal and stop with Ctrl+C before changing/removing pilot files**. No observed host service restart, Wolf configuration edit or Steam interruption.

**Physical iPhone test:** Safari reached the host private approval page through Tailscale using the separately pinned phone. The page displayed the staged device code, restricted key fingerprint and signed-certificate-backed Wolf identity suffix `…6372`, with a valid countdown; the candidate check therefore succeeded. Approval returned the generic denial. Host read-only diagnostics then showed one pending request (expired by the time checked), matching source-bound certificate proof, verified existing restricted broker, and the **exact staged public SSH key already in host `authorized_keys` with restricted broker and Wolf ID suffix `6372`**. A later fresh six-digit code showed the *same* key fingerprint and Wolf ID and was also denied. Duplicate key refusal is the expected safety behavior. Distinguish this from a completed new-device approval, which has not been physically tested.

**Source change (CI, not installed on client yet):** PR #184 now checks restricted Games `status` before staging a QR request. Confirmed existing owner access yields `ALREADY AUTHORIZED` and skips a redundant QR; unresponsive or denied checks remain inconclusive and do not self-approve. CI #792 for this change passed 484 Python tests plus native/GTK build and packaging. Device-side v1.20.0 install/upgrade smoke and a genuinely new credential's successful phone GET→POST→SSH grant are still open.

**Release completed:** PR #184 was squash-merged to `main` (`0668a6a`), and **v1.20.0 Closed Beta** published with a [direct Linux `.deb`](https://github.com/SteezyMode/OptiplexNow/releases/download/v1.20.0/OptiPlex-Now_1.20.0_amd64.deb), SHA256SUMS and curated notes. The versioned publisher run #15 and final `main` CI #796 both passed. This establishes an installable prerelease, **not Private Alpha 1 acceptance**. Source-only `ALREADY AUTHORIZED` needs physical client verification, and the phone QR success path remains untested with a fresh key. Focus next on the three pillars and the Wolf authorization boundary, not generalized modularization.

## October 25 — GitHub-only QR hardening while reference host remains untouched

Development PR #184 now has complete offline HTTP integration coverage for staged public key → signed Moonlight proof → pinned phone candidate review → explicit approval → one-time consumption. Regression checks include wrong source, wrong signature, non-phone same-owner device, wrong phone and approval replay. Certificate mode now requires a matching pinned approver for candidate review as well as page and final POST; a normal QR client no longer exposes a misleading self-approval button. On fresh default Moonlight Qt files that are owner-owned and read-only to others, NOW tightens permissions from 0644 to 0600 before signing using an open checked file descriptor, without modifying its contents. Unsafe/writable files remain blocked. See tests/test_owner_qr_http_e2e.py and tests/test_moonlight_cert_identity.py.

**Physical state has not advanced while owner is away:** host phone node ID was successfully written and mode verified at 0600; host preflight found crypto, TOML, Wolf registry and existing owner config, but **no pilot enrollment module deployed and no port 18793 listener**. Real Tailscale iPhone Safari and a fresh-client enrollment are untested. The running Mac mini managed Steam stream and owner restricted SSH keys remain unchanged. Source tests do not establish clean-host setup or direct Wolf app authorization protection.

## October 25 — Mac mini identity hash physically verified

The existing Mac mini native and Flatpak Moonlight public certificates matched, and both corresponding local private keys were verified against them. Both QSettings files were secured to owner-only mode 0600. A separate read-only inspection on the running OptiPlex derived the exact Wolf client ID `11701600982361132536` directly from the matching paired certificate in the live Wolf TOML registry; it matched the previously observed active Mac mini stream identity and Wolf's paired API returned that ID. The result was `IDENTITY VERIFIED: True`. No live authorization, pairing, or streaming service was modified. Next physical gate: identify the trusted owner's phone by its Tailscale IP, verify its WhoIs owner user and stable node ID, and only then pin that phone for owner approvals. QR approval end-to-end remains untested.

## October 25 — Mac mini real Moonlight Qt profile discovery

A read-only manual inspection on the wired Linux Mac mini found BOTH native and Flatpak Moonlight Qt QSettings files. Their public certificate SHA-256 fingerprints were identical, and that certificate was confirmed present in the OptiPlex's actual Wolf registry at `/etc/wolf/cfg/config.toml` (root-owned, mode 0644, readable by optiplex; 34359 bytes). Two client config files were each mode 0644, exposing the contained Moonlight private keys to other local Unix users; they should be changed to mode 0600 before owner proof is attempted. **Private key equality and matching the live Wolf session ID have not yet been physically verified.** The host registry had 11 entries at an earlier check; the read-only DER inventory reported 10 parseable unique fingerprints on another check; do not infer number of owner-approved NOW devices from either count.

The original prototype assumed the certificate value was exactly an @ByteArray(...) wrapper; this proved incorrect on the real Mac mini, although an escaped/newline-tolerant PEM search decoded both public certificates successfully. PR #184 now extracts strict bounded PEM blocks from supported Qt QSettings variants and accepts two native/Flatpak configs as ONE device only when BOTH actual local private keys match the same X.509 certificate. Different certs, mismatched keys, malformed encodings, ambiguous config sources or insecure world-readable private-key files fail closed. This code is CI-tested, not yet verified using the Mac mini's actual private keys or deployed host listener.

Next physical gate: chmod 0600 on the two local Moonlight config files (preserve bytes and normal Moonlight pairing), locally sign a challenge with both and verify their matching public keys; cross-check the certificate-derived Wolf ID against Mac mini's actual stream (last observed 11701600982361132536); then owner phone Tailscale StableID pinning and end-to-end QR approval without changing existing working SSH authorization.

## October 25 — Signed phone QR prototype now wired (development only)

PR #184 now connects request-bound Moonlight RSA certificate signing to a host-authorized proof endpoint, independently verifies Wolf's certificate-derived client ID, and revalidates the proof inside the atomic restricted-key + owner policy commit. The Qt client private key stays local; wrong proof/key/identity cannot grant access. The owner QR is displayed only after successful proof staging.

Host production listener requires an installer-pinned owner user ID AND a trusted phone StableID (not just shared Tailscale-account membership) for phone page access/approval. The phone camera opens private Tailscale HTTP; no public website or domain is used. Client source IP need not equal LAN streaming source when strong certificate mode is enabled. Listener remains opt-in and undeployed.

Source and offline integration tests are not physical acceptance. The actual reference Wolf TOML, Moonlight Qt identity profile, host setup and phone WhoIs denial/happy path still require real-device verification. No reference-host streaming, keys, services or current Games functionality have been touched.
## October 25 — Moonlight certificate proof prototype (source-only)

The next secure cross-network binding uses an existing owner-device identity, NOT a public website or new NOW account. Upstream Wolf retains the Moonlight client public certificate in its private host config.toml; Moonlight Qt stores the corresponding private key in the client's own QSettings. Wolf derives its numeric client ID from the certificate. Relevant upstream docs: https://games-on-whales.github.io/wolf/stable/user/configuration.html and https://github.com/moonlight-stream/moonlight-qt/blob/master/app/backend/identitymanager.cpp .

**Implemented in draft PR #184 as an offline-tested, unconnected prototype:**
- server/moonlight_cert_identity.py constructs a bounded, domain-separated request challenge over the one-time request ID, six-digit code and the exact staged restricted SSH public-key fingerprint; verifies an RSA/SHA-256 detached signature using the submitted PUBLIC certificate; checks that it is in the host-owned Wolf paired-client TOML registry and that Wolf's API still considers the intended ID paired.
- src/moonlight-identity-proof.py reads one specified Moonlight Qt QSettings identity locally (read-only) and signs the challenge using the corresponding private key. The client sends only a public certificate and signature, NEVER the private key. Ambiguous or unreadable Qt profiles fail closed.
- tests/test_moonlight_cert_identity.py exercises real generated X.509/RSA keypairs, challenge tampering, wrong/removed registry certificate, unpaired ID, invalid key material, and untrusted registry permissions. No real Wolf, SSH or network state is modified.

**Still NOT done:** A verified host inventory path to the actual running Wolf TOML file; a server-bound staging/attestation endpoint with strict same-request/source access; client identity profile discovery (Moonlight Qt AppImage and non-Qt clients differ); persisting/rechecking the verified Wolf ID in the atomic owner grant; packaging dependency review; real cross-network tests. Until each is implemented and physically verified, the existing source-address guard MUST stay fail-closed, and no QR approval may claim Moonlight certificate verification. Custom app_state_folder mappings also fail closed under the prototype. No certificate proof secret should ever be written to a log or a QR code.

## October 25 — Mac mini Games physically verified; wrong Wolf identity binding (PR #184)

**Physically verified on reference equipment:** The owner Mac mini Linux client, with wired network and Wolf at 1280×720/30, installed the unreleased PR #184 build and completed restricted key enrollment using the host approval window. The initial owner approval inadvertently bound its public key to Wolf ID 10786982254245626228, although the single active Mac mini Wolf UI stream from 192.168.40.90 used client ID 11701600982361132536. Restricted SSH status accurately returned needs_wolf_ui. After a targeted, backed-up manual correction to BOTH forced-command authorized_keys and the owner-access policy, NOW launched Steam Big Picture successfully. Normal Steam exit was physically confirmed to close its Moonlight process automatically; a brief Wolf Select User screen flash remains cosmetic. This is NOT a clean-host/client or automated onboarding pass.

**Alpha P0 finding:** The host-local approval UI let a human choose any previously paired Wolf ID; the first QR implementation showed the sole Wolf UI session without tying it to the staged requester. PR #184 now saves a host-observed source IPv4 on each staged key (from SSH_CONNECTION or authenticated Tailnet HTTP), removes the arbitrary Wolf ID picker, bounds QR review to a specific pending request, and requires a single active paired Wolf UI with a matching source IP. The final approval transaction independently rechecks exact live source and requested client ID BEFORE writing SSH authorized_keys or the policy. No other owner devices, Wolf sessions, Steam homes or existing server settings are changed by code-only development.

**Security limitation:** Network source equality prevents the *observed accidental misbinding* for clients connecting from one source path but is NOT a cryptographic proof that Moonlight certificate, SSH key and Tailscale principal belong to the same machine. Staging through Tailscale while Wolf streams over a different LAN address deliberately fails closed. Certificate possession verification or equivalent authenticated multi-path association is still P0 before claiming hassle-free, general QR approval. Never guess an ID, map IPs by untrusted hostnames, or loosen the live gate. Legacy pending requests without observed source now cannot be approved.

**Next acceptance:** CI negatives; physical clean client source-matched enrollment; QR phone and wrong-owner tests; strong mixed LAN/Tailnet device binding; complete Jellyfin zero-URL and VPN-isolated Downloads journeys; separate disposable clean-host adoption/installer test. Private Alpha 1 remains owner-operated devices only; viewers, Windows host and commercial extras deferred.


## October 25 — Orphan-safe Wolf pairing prepare protocol (CI pilot)

**Why:** A reference-host MacBook Moonlight process was terminated after its phase-one pairing request hung, yet Wolf still showed **one pending request from `100.73.42.22`** five seconds afterward. Thus source-IP matching plus a positional queue index is insufficient to establish which pending request is **fresh**. Wolf's PIN API can acknowledge setting a pairing promise without registering a new client. Repeated blindly targeted approvals are unsafe. The pending queue is not a work queue that this project may clear or restart: preserve Wolf and the existing Steam lobby.

**Change (development PR #184, not deployed):** An optional `--require-fresh-wolf-pairing` host-listener flag enables `POST /v1/owner/wolf-pair/prepare` with an empty JSON object. The authenticated owner prepares **before** starting Moonlight. The host snapshots all existing pending Wolf pairing secrets in private process memory (does not expose them), tied to verified Tailscale user/node/source and bounded to **5 minutes**. Subsequent `GET /v1/owner/wolf-pair/pending` lists only a *new* same-source request whose secret was **absent** from that snapshot. The owner-submitted PIN is accepted only for that exact new request; a stale request, changed index, multiple new requests, different peer or expired/unprepared session fails closed. Successful PIN submission consumes the preparation. This still **does not prove completed pairing**; full owner enrollment requires separate verification that exactly one new Wolf paired client identity appears, followed by explicit confirmation. No clearing of pending requests, Wolf restarting, or automatic access grants. Existing host behavior is unchanged without the explicit experimental flag. CLI can issue `prepare` without administrator SSH; a native end-to-end GUI ordering still needs physical verification. The client pending/approval transport now validates the **actual client** Tailscale IP, no longer erroneously comparing it with the server IP.

**Physical follow-up:** stage reviewed PR head into a new side-by-side host pilot; do **not** overwrite running source or existing NOW 1.17.0. Before launching Moonlight, call prepare and capture the stale-request baseline. Start exactly one new isolated Moonlight identity, check filtered pending, submit the **PIN displayed by Moonlight** (or verify it equals the CLI-specified PIN), check application discovery and **one** new Wolf client ID, and only then exercise the witness. Do not perform private-key entitlement approval before identity review. No host changes required while developing or testing source.

## October 25 — Witness physical attempt: PIN submitted, Moonlight pairing incomplete

**Physical acceptance failed safely; no restricted credential authorization was attempted.** On the reference host, the separately staged witness pilot at `26e43af` was launched with both opt-in switches. The MacBook (`100.73.42.22`) successfully staged a new Ed25519 public key with HTTP 202 and produced a Wolf pairing request. POST /v1/owner/wolf-pair/approve returned `{"success":true}`, but ten subsequent `/v1/owner/enrollment/paired-candidate` checks found no new device and **no approval was granted**. A read-only Wolf inventory was still **10 unique paired client IDs, unchanged** from the earlier baseline, and isolated Moonlight `list` returned **host not paired**. The isolated Moonlight 6.2.0 CLI log stayed on phase-one HTTP `getservercert` and reported `QNetworkReply::RemoteHostClosedError` after approximately ten minutes. Wolf `GET /api/v1/pair/pending` returned **one MacBook-source request remaining**, which might be old, retried, or another pending request; no request-secret comparisons were logged. The Wolf log filter found repeated IP-to-MAC lookup warnings but no other pairing-specific error; do not assume MAC lookup caused the stall or change `WOLF_INTERNAL_MAC` without evidence. Wolf's own `endpoint_Pair` implementation resolves the pending PIN promise and erases that request, returning success **before completing the multi-stage Moonlight cryptographic pairing**. Thus endpoint success is only PIN-submission acknowledgment, not proof of a paired Wolf ID.

**Follow-up:** safely terminate only the isolated hung Moonlight pairing process (never the working client or Steam), compare pending queue before/after for staleness, and attempt a deliberately supervised pairing only after isolating the cause. Do not delete existing pairings or restart Wolf's live Steam container. Improve status wording and physical acceptance diagnostics; require Moonlight app listing + unique new host Wolf client before treating remote enrollment evidence as successful. No change to host NOW 1.17.0 or SSH `authorized_keys` was made.

## October 24 — Same-node witnessed Wolf pairing for restricted owner enrollment

**Unmerged PR #184 — CI-only change, not installed on the reference host.** A fresh `server/tailnet_pair_witness.py` maintains **in-memory, 10-minute** pairing observations keyed by the host-verified Tailscale **user ID + stable node ID + actual source IPv4**, alongside public-key enrollment request IDs submitted by that same peer. When *both* `--enable-owner-wolf-pairing` and `--enable-remote-approval` are explicitly enabled, the server snapshots Wolf's paired-client inventory **before** an owner-authorized PIN pairing transaction and records it **only after** that transaction reports success. A client can then request `POST /v1/owner/enrollment/paired-candidate` for one of its staged enrollment request IDs. The host re-reads its own Wolf paired-client inventory and returns an eligible candidate only if **exactly one** previously unpaired Wolf client appeared. It does not check or change live sessions or lobbies. The client-side enrollment UI explicitly shows that observed Wolf ID and explains the trust limitation; the owner must confirm the request code/key fingerprint/device in a separate approval dialog. The existing `POST /v1/owner/enrollment/approve` accepts a narrowly labeled `source=recent_pair` path and uses the existing restricted credential/policy commit mechanism after re-validating the witness and selected Wolf ID. Successful commit consumes the witness so it cannot be replayed; rejection/expiry/multiple-new-clients/wrong-peer never grants access. All source/backend paths are disabled by default; only plain owner pairing or staging behaves as before if just one feature is enabled.

**Security bounds:** This is a **server-observed unique new Wolf identity for manual owner review**, **not** cryptographic proof that the Tailscale node's restricted SSH key and Moonlight's certificate were produced by the same process, nor proof that a concurrent Wolf pair elsewhere could not have generated that one newly seen client. It is owner-only, not delegated multi-user or untrusted-device authorization. The witness lives only within the particular Python host listener process; restarting the service, observing multiple new client IDs or waiting ten minutes loses the candidate. Ordinary host-local manual approval remains available; no automatic key installation occurs at the moment of Wolf pairing. The successful prior physical test of client `5114970000005922575` happened **before this witness code was deployed**, so it cannot be retroactively treated as witnessed. A new isolated Moonlight pairing and public-key staging in the same running service are needed for the positive physical test. Retain running Steam and existing Wolf pairings; **do not re-pair or delete them to clear a lobby**. A negative live user/peer test and controlled host-side credential rollback remain future acceptance gates.

## October 24 — Physically verified isolated Moonlight pairing over owner Tailscale

**Reference hardware physical test passed (owner's MacBook Air, Mint XFCE; OptiPlex Pop!_OS Wolf):** Owner MacBook Tailscale source `100.73.42.22` and host `100.121.156.34` both reported pinned Tailscale user ID `3905340949246616`. A temporary, explicitly enabled `--serve --enable-owner-wolf-pairing` listener on port 18793 (300-second timeout) returned HTTP 200 for `GET /v1/owner/wolf-pair/pending`. An isolated Moonlight 6.2.0 AppImage identity in `/tmp/tmp.ST7HawXpsc` generated a pending Wolf device reported as `{"index":1,"client_ip":"100.73.42.22"}`. The owner performed explicit PIN approval using `POST /v1/owner/wolf-pair/approve` over the Tailscale address, which returned `{"success":true}`. The isolated Moonlight profile subsequently listed `Wolf UI` and `OptiPlex Studio Desktop`, and the Wolf paired-client inventory increased from **9 to 10 unique IDs**, adding `5114970000005922575`. Previously paired `12009214108445860267` remained present. This is positive physical verification of the **owner-only native Moonlight pairing path without client administrator SSH**. The temporary host listener was provisioned by an existing trusted SSH session and is **not** a persistent installed service or general no-SSH setup.

**Boundaries still unverified:** no physical wrong-owner denial, no packaging/installer host enablement test, no remote Games/Downloads key approval, no separately proven Tailscale↔Wolf client credential binding, no non-owner/guest workflow. The host's original NOW package remained `1.17.0`; pilot sources were staged separately at the fixed PR head and did not replace the live package. Wolf's existing `Steam` lobby `40e65a76-1c98-466d-88e9-5e552c5899de`, with its actively running Steam container and zero connected sessions, was preserved throughout. The currently implemented remote Games owner-review gate declines approval while any Wolf lobby exists; do not stop Steam just to clear that gate. Next work: establish a trustworthy new-client binding during owner-approved Wolf pairing or otherwise design a separate owner approval without dependence on stopping existing Steam; test negative cases before production enablement.

## October 24 — Owner-only Moonlight/Wolf pairing without administrator SSH (source-tested)

**PR #184 build #715 (full CI/unit tests, native sanitizers, package SHA256 confirmed; NOT host-tested):** Added the opt-in `server/tailnet_wolf_pair.py` fixed-route Wolf PIN adapter and `GET /v1/owner/wolf-pair/pending` + `POST /v1/owner/wolf-pair/approve` to the already pinned-owner Tailscale host listener. It accepts only the **actual WhoIs-verified pinned Tailscale owner account** and checks each Wolf pending `client_ip` equals that requester's actual Tailnet source IP. Pending enumeration reveals only the caller's entry, not other pending clients or their `pair_secret`. Approval requires an exact current pending index, matching source IP and 4–12 digit PIN; Wolf's private `pair_secret` is used strictly host-side via existing `wolf-pair-local.py` fixed Docker/UNIX-socket adapter. No client-provided Docker commands, profiles or Wolf IDs are accepted. The endpoint and host listener remain **disabled by default** unless separately started with `--serve --enable-owner-wolf-pairing` after operator review.

**Client:** `src/wolf-pair-client.py` now prefers the fixed Tailscale endpoint while preserving the known SSH path only if the optional host listener is **absent/refused** or the host address isn't a direct Tailnet IPv4. A forbidden owner identity, malformed/ambiguous Wolf pending entry, or upstream Wolf rejection never silently falls back to admin SSH. `pair_wolf` in `src/main.c` no longer requires an SSH username just to begin Moonlight pairing. Wolf's own Moonlight PIN remains required, and the existing GTK pairing UI is reused. The .deb packages the static host pairing backend but **does not install or enable the host service**.

**Release caveats:** The reference OptiPlex has **not** run this service, and no physical test proves the Wolf pending `client_ip` matches the actual Tailscale source IP on this host. If Moonlight connects to a LAN address rather than the Tailscale address, fail closed rather than authorizing another IP. Direct Moonlight pairing's narrow Tailscale path is not the same as NOW restricted owner Games/Downloads authorization; those still need the per-device forced-command credential, and the first-run wizard still has other SSH-dependent paths. Remote owner review remains manual/opt-in, not unattended cryptographic enrollment or multiuser isolation. Follow up with a controlled fresh profile plus negative tests **only when the host is free**, preserve all other Wolf pairings, SSH keys and existing Steam workspace.

## October 24 — Remote owner-confirmed Wolf UI enrollment pilot; disabled by default

**Development-only PR #184, not deployed on reference host:** The already-added opt-in Tailscale owner staging listener now also supports **separately opt-in** read-only `GET /v1/owner/enrollment/wolf-candidate` and owner-confirmed `POST /v1/owner/enrollment/approve` when the host explicitly starts it with `--enable-remote-approval`. Both actions reverify the remote source with Tailscale WhoIs against the host's local private pinned owner user ID. The host consults its own Wolf paired clients, apps, sessions and lobbies; it returns only a candidate `client_id` when **exactly one active paired Wolf UI session** and zero lobbies are present. No other Wolf app/session, inactive device or guessed nickname/IP can qualify. A separately authenticated owner in NOW's client review UI sees the observed Wolf ID, the pending request code and restricted key fingerprint, and must explicitly confirm. On confirmation, the host rechecks the same unique live stream and delegates to the already-tested `owner_enrollment.approve_request` to back up and atomically install only a constrained forced-command key/policy entry. It never pairs Wolf, starts or stops Steam, mutates Docker, or confers unrestricted admin SSH.

**Not silent auto-enrollment or cryptographic certificate-to-Tailscale binding.** The sole active Wolf UI stream is server-observed evidence for an **explicit, human owner decision**; it is not cryptographic proof the requesting Tailscale node and Wolf certificate are the same device. When another stream/lobby is active or any binding is ambiguous, remote approval is refused. Only an authenticated account matching the install-pinned owner can review/approve, but compromise of any device authenticated as the owner could grant privileged owner access. **Do not market or enable for untrusted multi-user hosting** or assume Tailscale user identity alone grants Wolf access. The original host-local approval still exists; there is no automatic Wolf pairing, no new host service installed/launched by package setup, and no reference-host live test. All remote approval endpoints are disabled unless the host explicitly opts in after review. This is an owner-only private alpha pilot, not a completed normal-user setup.

**Physical next test, only when the host is free:** preserve the working server; first run the previous `now-alpha` client-ID disconnect/reconnect check, verify the remote owner account and host listener are properly configured without exposing a privileged public service, confirm owner positive and wrong-owner/expired-code/competing-session denials, test actual restricted Games/Downloads, then surgically revoke only temporary full SSH from `now-alpha`. No existing keys, Wolf pairings or Steam workspace should be reset.

## October 24 — Tailscale-verified owner key staging prototype; remote approval still blocked

**PR #184 source and offline CI only — no host service activated:** Added `server/tailnet_owner_identity.py` and `server/tailnet_enrollment.py` to provide a *disabled-by-default* tailnet-only HTTP staging endpoint (fixed port 18793, bound to the host's actual Tailscale IPv4, no public/LAN wildcard). Before accepting a restricted device's **public** Ed25519 key, it checks the actual connection source via `tailscale whois --json`, requires that WhoIs source IP match an exact node /32 address and non-tagged user profile, and compares the numeric Tailscale user ID to a private **installer-pinned** host owner ID file (0600). It then uses the existing `owner_enrollment.stage_request` TTL/limit/state-lock implementation, and returns only staged request code/fingerprint. It cannot authorize Games, pair Wolf, install keys, call Docker, touch authorized_keys, or change any host services. Test coverage includes wrong account, tagged device, forged client fields, invalid owner file and no client credential leakage.

**Client bridge:** `src/owner-enroll-client.py` now supports `request_tailnet`; the existing owner enrollment GTK dialog first tries it and falls back to the preexisting privileged SSH alpha staging path **only on TCP connection refusal (listener absent)**. A server identity denial or malformed reply **does not silently fall back to SSH**. The client `.deb` contains the host pilot modules in its bridge directory but **does not install/enable a listener, modify any server config, or auto-pin an owner identity**. Full no-SSH auto-enrollment is NOT delivered; this only begins replacing the routine request transport. Security acceptance still requires a reviewed host service installer, safe owner identity pinning, actual verified Moonlight/Wolf device binding, remotely authorized approval or a safe same-owner auto-approval policy, restricted-key setup and physical new-device/negative tests. The existing `now-alpha` host approval remains pending, and direct Wolf Steam bypass issue #192 is unchanged.

**Current alpha safety:** Do not start the optional tailnet listener on the occupied live OptiPlex, infer the client Wolf ID from a nickname/Tailscale IP, or remove the previous pairing/SSH key before the controlled positive/negative tests and key-specific revocation. Project remains Private Alpha 1 unaccepted.

## October 24 — Missing Games credential now routes to setup, not a dead end

**Source-only client UX fix, pending complete CI/physical acceptance:** After moving the duplicate owner approval out of the normal wizard, `NOW → Games` was still guarded by the per-device restricted key and otherwise stopped at `THIS DEVICE NEEDS OWNER GAMES APPROVAL`. The GTK Games launch now opens the existing Streaming Setup dialog when the restricted key is missing, revealing its `ADVANCED: REQUEST RESTRICTED OWNER ACCESS` action and explaining the distinction between Wolf pairing and managed owner Steam. This does **not** approve a device, grant full SSH, launch unmanaged direct Steam, call Docker, silently create new sessions, or change read-only status/Stop behavior; tests assert these constraints.

**Product blocker remains:** That enrollment UI still stages its restricted public key over *pre-existing owner-admin SSH* and still needs host-console confirmation. Draft PR #62 verifies pinned Tailscale account identity and records remote approval but **does not actually pair Wolf or install a working restricted Games credential**. It cannot simply be merged as the solution. The next authentication implementation needs a narrow host-side enrollment/approval service that binds the verified owner, a device credential and Wolf identity and authorizes the required broker without ever granting the client an administrative shell. Existing reference host still occupied during last physical-test pause; no host commands or restarts initiated.

## October 24 — Owner access no longer presented as mandatory normal Games pairing

**Source-only UX adjustment in PR #184 (pending exact-head CI and physical test):** The routine setup wizard now presents Moonlight/Wolf pairing without the previous `REQUEST OWNER DEVICE APPROVAL` action or SSH-dependent `ADVANCED PAIRING HELP` button, because the controlled `now-alpha` test physically demonstrated that Wolf pairing can launch Steam **even while NOW-managed Games status returns DENIED**. The wizard now states this distinction explicitly; it also tells developers that its existing automated Wolf pairing helper **still uses preauthorized administrator SSH** and that Tailscale-first no-SSH client enrollment is not implemented. This change is **not** a security repair and does not authorize additional users. Existing `Settings → Gaming & Streaming → Streaming Setup` retains the same owner enrollment callback under `ADVANCED: REQUEST RESTRICTED OWNER ACCESS` so current private alpha testing of protected managed Games/Downloads remains possible. No host state, Wolf pairing, SSH keys, Jellyfin or qBittorrent modified.

**New commercial/power decisions:** Paid software must not add a recurring NOW subscription to access one's own games/media/server. Download-VPN subscription is optional with supported bring-your-own VPN; loss of the vendor website/VPN cannot revoke ordinary self-hosted access. Later guided Wake-on-LAN, sleep and shutdown remain explicitly **post-alpha**, tracked in issue #193 and `docs/PRODUCT.md`; existing advanced wake relay/power tools are not a normal user setup guarantee.

## October 24 — Tailscale-first client enrollment and separate private-download VPN agreed

**Explicit product direction, not implemented functionality:** Prefer Tailscale as default private access, discovery and trusted owner-identity infrastructure. Headscale is only a later opt-in compatibility target. After one trusted local host ownership setup, subsequent authenticated owner clients should enroll remotely **without walking to the host**, opening SSH, knowing SSH usernames or receiving ordinary shell rights. Draft #62 and issue #63 contain partial remote-owner infrastructure, but are unmerged/unverified for actual Wolf pairing. Wolf pairing alone currently allows Steam from newly paired `now-alpha`, even though NOW-managed Games denied access (issue #192); align authorization claims and avoid forcing redundant approvals. SSH for the owner remains in Advanced Settings; standard client enrollment must not depend on administrator SSH.

**Torrent VPN is a separate optional service and possible later revenue line**, not a replacement for Tailscale or a requirement for streaming. Use Gluetun-isolated bring-your-own commercial VPN for qBittorrent egress only, with kill switch, actual IP/no-leak tests, and no collateral networking changes to Jellyfin, Wolf, desktop or Tailscale. Do not tunnel the entire host as a shortcut. A normal egress VPN does not automatically provide Tailscale-like peer mesh, host discovery, or device authentication; double VPNs may conflict. Potential future affiliate/white-label offer **only** with appropriate contractual support; it is not an alpha gate, and privacy claims must never promise anonymity or legal “plausible deniability.” Product rationale documented in `docs/PRODUCT.md`.

**Physical safety:** OptiPlex is occupied for an important meeting. No live Docker, Gluetun, Tailscale, Wolf or service changes as part of this decision. Existing qBittorrent-through-Gluetun evidence in issue #8 is not proof of an all-supported-host rollout.

## October 24 — Wolf-paired `now-alpha` launches Steam despite denied NOW owner Games

**Physically reported security/product finding:** The freshly paired, separate `now-alpha` Linux Mint MacBook profile returned **DENIED** on NOW's restricted `CHECK OWNER GAMES ACCESS`, then successfully **launched Steam via Moonlight/Wolf and browsed games** without NOW owner-device approval. This confirms Wolf's published Steam application is reachable through existing Wolf pairing alone; NOW's restricted Games credential guards the NOW-managed broker path, **not direct Moonlight application selection**. Do not claim owner Games approval is a gate for all Wolf streaming; it isn't. The distinction matters for future multi-user access, but does not itself show that a user can reach unrestricted host files.

**Decision pending, do not feature creep:** For single-owner alpha, either explicitly rely on Wolf pairing as the authorization boundary for Games and reserve NOW owner approval for restricted privileged operations (including Downloads), or implement actual combined Wolf/NOW authorization later. Avoid making the owner approve twice merely to browse games. Track at [issue #192](https://github.com/SteezyMode/OptiplexNow/issues/192). Nine Wolf paired client IDs are not nine NOW owner approvals; client naming tracked in #191.

**Current physical state:** No owner request approved. One active Wolf client ID `12009214108445860267` appeared during a stream believed to be `now-alpha`; final disconnect/reconnect identification remains outstanding. Another person currently needs the OptiPlex for an important meeting. **Do not perform live host commands, pairing changes, Steam launches, restarts, broker mutations, or client-side stream tests until host is free.** Continue only afterward with identity confirmation and scope decision, then restricted Games/Downloads approval tests and narrow revocation of the temporary fresh-profile ordinary SSH key while retaining existing trusted users.

## October 24 — Host testing paused; clarify Wolf pairing versus NOW owner approval

The fresh `now-alpha` Linux Mint MacBook profile completed a separate Wolf pairing and returned **DENIED** from NOW's restricted `CHECK OWNER GAMES ACCESS` before any host owner approval. To identify its Wolf identity, the owner launched an actual active Wolf UI stream, then the host read-only `GET /api/v1/sessions` query returned **one active numeric client ID** (recorded in the ongoing test conversation; compare its exact value before approval). Disconnect/reconnect identity comparison was **not done**, and host approval remains **pending**. The host was occupied by another user, so all physical host actions are **paused**; do not test, refresh, restart, change config, or approve until it is free.

The host-local approval dialog reported **nine Wolf paired clients**. That is the Wolf pairing inventory, **not** nine concurrently streaming devices or nine NOW owner-authorized device grants; one physical machine can accumulate multiple Wolf certificates from separate Linux profiles, reinstalls, and prior tests. Causes of specific entries remain unverified; do not delete or unpair them. Friendly owner-confirmed device labels tracked in issue #191. Host UI currently displays anonymous long Wolf IDs.

**Architectural clarification / release blocker:** Moonlight/Wolf pairing is already a network streaming authorization boundary controlled by Wolf, while NOW's separate restricted per-device SSH owner credential protects the **NOW-managed Games command path and authorized Downloads operations**. Source `owner_access.py` explicitly does not control Wolf pairing or generic Moonlight launches. A freshly Wolf-paired `now-alpha` client could launch Wolf UI despite NOW's restricted Games check returning DENIED. This is **not evidence that a Wolf-paired device is barred from manually starting a Wolf-published Steam app**. Do not advertise the NOW approval as blanket streaming security until physically verifying whether direct Moonlight app selection bypasses it and resolving how a unified simple approval should work. Preserve the existing denial test and pending approval; keep scope owner-only, no general role/multi-user expansion.

**Next physical test when host free:** confirm the active Wolf client ID disappears when `now-alpha` stream disconnects and returns when it reconnects; generate fresh six-digit request if needed; compare request code, verified Wolf ID, and existing approvals before host-only confirmation. Then test positive restricted Games and Downloads and safely revoke only temporary `now-alpha` **ordinary unrestricted SSH key**, preserving trusted client/admin keys. No host changes or approvals performed during pause.

## October 24 — Fresh `now-alpha` Wolf pairing verified; pre-approval owner Games denied

The owner reports the temporary separate `now-alpha` Linux Mint profile on the old MacBook successfully paired its own Moonlight AppImage identity with Wolf. The app's `CHECK OWNER GAMES ACCESS` returned **denied**, before any restricted owner-device approval. This physically verifies the important negative path for this newly paired profile: Wolf/Moonlight pairing and accidentally authorized ordinary SSH are **not sufficient for restricted NOW owner Games entitlement**. It does **not** yet prove positive approval, restricted SSH authorization, correct newly paired Wolf client identity binding, Downloads authorization, or revocation.

Next: from `now-alpha`, submit `REQUEST OWNER DEVICE APPROVAL`, compare its six-digit code in the OptiPlex host-local approvals window, and independently identify/select the **newly paired** Wolf client ID (not existing `macbook` or `test` identities) before explicit owner confirmation. The pending request expires after 10 minutes and must be refreshed manually. If that identity cannot be distinguished from the host inventory, **do not guess or approve**. After approved, verify restricted Games and Downloads; then explicitly revoke the temporary ordinary SSH key (only) and verify restricted access still works.

## October 24 — Fresh client revealed obsolete manual service URL wizard page

On the `now-alpha` Linux Mint account, owner saw a setup wizard page requiring `Videos URL`, `Music URL`, and `Downloads URL` after Moonlight AppImage detection, and flagged that this contradicted the intended zero-manual-URL onboarding. Source review confirmed **not all automatic discovery exists**: `src/media_flow.c` already checks a fixed token from the authenticated `media-discover.py` helper and opens Jellyfin at the known trusted host port if verified, `src/downloads_flow.c` already uses restricted per-device owner authorization to discover Downloads WebUI, and Music remains an **optional manually configured link**. These runtime paths are authorization dependent and not yet demonstrated on the fresh client; never claim broad zeroconf/autodiscovery.

PR #184 removes the entire obsolete wizard service URL page and its wizard-only asynchronous service probe UI, retains optional video/music/download URL settings under `Settings → Connections & Server → Advanced Settings`, and preserves existing overrides during normal setup (with explicitly imported safe preset values saved). No hardcoded host address, insecure port guess, service restart, broker policy change or credential mutation was added. The package `service_probe` / `wizard_services` modules remain for compatibility/testing and are not part of the wizard UI. Code-only pending exact-head CI and physical GUI retest. Already installed #667 still shows the old step until updated.

**Current walkthrough:** leave those three entries blank and Finish on the installed build; proceed with Moonlight pairing and owner device approval. Do not copy the original Linux profile's Moonlight pairing material. Lack of general secure client bootstrap without ordinary admin SSH remains an alpha blocker.

## October 24 — Routine wizard admin SSH step removed; owner SSH retained under Advanced Settings

Owner clarified that SSH remains essential for **their own administrator workstation**, but it should not be a routine step in client onboarding. While testing the separate fresh Linux account `alphs-now`, they pressed Authorize SSH Key and granted ordinary owner-account SSH before realizing this distinction. That account's key **remains granted on the host** until explicitly revoked; existing trusted `macbook` account credentials must remain unchanged.

PR #184 now removes the wizard's standalone SECURE ACCESS page with ordinary and relay SSH authorization actions, puts both existing actions under `Settings → Connections & Server → Advanced Settings` with explicit **OWNER ADMIN ONLY** labels, and clarifies the owner-admin SSH dialog. The underlying `pair()` and admin workflows still exist. Wizard keeps Tailscale, server selection, independent Moonlight pairing, owner-restricted device-approval request, service checks and finish. Existing and imported wake relay preset fields survive wizard save even without relay controls in the regular flow. This is source-only until exact-head CI and fresh GUI installation pass.

**Unresolved real blocker:** Wolf PIN automation and current owner-approval request transport still require preapproved ordinary SSH. Removing an unsafe prominent wizard action is not itself a secure client bootstrap design; fresh untrusted clients cannot yet enroll without a new narrow transport. For this **controlled owner-only pilot**, the already authorized temporary `alphs-now` account can be used to test explicit restricted approval, then its ordinary SSH authorization must be surgically revoked without modifying any other keys or Wolf grants. Client Moonlight AppImage is preferred for the old MacBook; installing or selecting an executable in the fresh profile does not transfer pairing/configuration.

## October 24 — Fresh-account onboarding exposed server discovery and owner-SSH bootstrap gap

On a fresh Linux Mint profile (`alphs-now`) using the system-wide NOW #658 install, the owner had to manually enter the Tailscale server IP and the host SSH username in the setup wizard and reached the Moonlight installation page. The wizard does have `FIND SERVER ON TAILSCALE`, but current implementation enumerates peers, cannot authoritatively select the intended NOW host, and still requires manual SSH username. Owner explicitly flagged this as unacceptable turnkey onboarding friction. Moonlight installed status, fresh Wolf pairing and fresh restricted owner enrollment **have not yet been reported**; do not claim them.

**Security/design blocker:** The wizard's `AUTHORIZE SSH KEY` stage installs the fresh Linux profile's *ordinary unrestricted public key* into the chosen server OS account (with its password), whereas the new owner enrollment client requires this same preexisting ordinary SSH credential to submit an isolated restricted public-key request. This is legitimate only as a controlled **owner-admin test**; it cannot be represented as a least-privilege invitation or secure member onboarding. Avoid copying the existing `macbook` user's SSH credentials, automatic SSH approval, or granting broad owner shell access to members. Defer full member system, but before calling an owner-device enrollment flow turnkey, design a bootstrap that does not require normal clients to first hold unrestricted SSH credentials. For current physical walkthrough: install Moonlight inside the fresh profile through the per-user Flathub flow; do not authorize full SSH silently.

## October 24 — Host owner approvals list does not auto-refresh (minor)

The owner observed that the `NOW Owner Device Approvals (Host)` request list and countdown are **snapshot-based**: pending requests and their remaining-time labels update only after clicking `REFRESH HOST DEVICES`. The staged request and its matching six-digit code did show on manual refresh, and the security-sensitive approval was intentionally not performed on the already-enrolled MacBook account. Defer optional timer/live-refresh UI polish; it is not an authorization correctness failure. Pending request TTL is checked server-side on approval. Next physical gate: use a separate Linux profile/Moonlight credential to test actual denied-before-approval, approved-after-explicit-host-confirmation behavior; never repurpose an existing approved Wolf identity or owner key.

## October 24 — Owner device request pipeline physically verified (no approval)

The owner submitted an enrollment request through the Linux Mint MacBook's NOW client GUI and received a six-digit request code. On the reference OptiPlex, the owner opened the separate host-local `NOW Owner Device Approvals (Host)` GUI, clicked Refresh, selected the pending request in the drop-down, and confirmed that **the six-digit code matches the requesting client**. This is physical proof of the existing, preapproved ordinary-SSH public-key staging request and the host pending-inventory path, NOT device approval, independent Wolf identity binding or credential installation. The enrolled `macbook` Linux account was used for the request: do **not** approve it again or bind its public key to a different Wolf ID. Let the pending request expire (10-minute TTL) or handle it with a future explicit cancel path; it does not itself grant access.

Next acceptance needs an independently paired, **not-yet-enrolled** Moonlight identity on a fresh client profile/device, with the owner verifying that identity in the host approval GUI before any host SSH/policy mutation. Verify negative cases, clean grant and restricted client access after approval. The host UI requires selecting the pending-request dropdown rather than automatically selecting a lone entry; minor UX polish deferred until acceptance.

## October 24 — Host owner approval window physically opened (read-only)

The owner opened the previously staged `NOW Owner Device Approvals (Host)` GTK application on the reference OptiPlex and confirmed it displays **zero pending requests**. This physically validates the window's open/initial read-only inventory path only; the user did not explicitly report the Wolf client list, so that part is not considered verified. The earlier host CLI `pending` returned `{"requests":[],"success":true}`. No device was granted or denied and no SSH keyfile was changed as part of this window test. Next: use the already approved MacBook account to **stage only** a new public-key request via its GUI and verify that the host window sees the code/fingerprint. Do not approve the already enrolled MacBook key; use a fresh independently paired client identity to test real approval, revocation, and denial later.

## October 24 — PR #184 build #658 Dashboard startup physically accepted on Mint client

The owner installed and tested exact CI artifact `optiplex-now-pr-184-658` and reported **"yup all works"** immediately after the specified full-tray-quit / fresh launch test: Dashboard is now the initial visible page, and Downloads remains functional when selected normally. This closes the previously observed unwanted Downloads startup page regression **for this already enrolled MacBook account**. The fix explicitly selects the resolved Dashboard/Software child after GTK stack pages become visible; exact-head build/test and native sanitizer CI passed at commit `d665c224198f0bf300f67e9b419123d4bd89862b`. It does not prove startup loading of Downloads itself, which remains deferred for beta.

The owner also observed that the `REQUEST OWNER DEVICE APPROVAL` GUI window opens in Settings on build #655. On the existing reference OptiPlex, the host-only owner-enrollment helper was separately staged with verified archive checksum, and its read-only `pending` action responded `{"requests":[],"success":true}`, while the existing owner broker and policy remained intact. **Next physical gate:** open the host-local `NOW Owner Device Approvals (Host)` GTK window and read the paired Wolf inventory before initiating a truly fresh client enrollment. A window opening is not approval-flow acceptance; no new grant or key should be claimed as tested.

## October 24 — #655 saved Dashboard still presents Downloads (physical report; source fix pending test)

The owner installed PR #184 build #655 and verified that the new Games → Request Owner Device Approval window opens from Settings. The same client **still appeared to open on the stale Downloads page** rather than Dashboard, despite the beta change that disallows Downloads as a saved startup preference. Code review found a second GTK startup-order bug: the Downloads child is explicitly `gtk_widget_show_all()` during main stack construction, while the Dashboard child is not yet shown; later code skipped any explicit stack selection when Dashboard was the desired startup page. Therefore GTK could leave Downloads as the first visible child. This explanation is source-supported but not yet isolated by physical instrumentation; a still-running tray instance would also retain its current tab rather than start a new process.

Source patch explicitly shows supported startup stack children and selects the resolved startup page, **including Dashboard**, before showing the main window. No changes to saved host, credentials, Games, downloader, containers or media. Regression test guards initialization order. Exact-head CI and a physical **full quit including tray → fresh launch** are required before claiming a fix. Host enrollment helper installation was physically verified separately via read-only `{"requests":[],"success":true}`.

## October 24 — Owner-device graphical request/approval pilot (PR #184, source-only)

The fresh Linux-profile incident demonstrated a missing owner-device enrollment step after Wolf pairing and ordinary SSH. PR #184 now contains an **owner-only, explicit approval pilot**: the Games dialog and setup wizard open a GTK client request window, generate a separate 0600 Ed25519 restricted key locally, and stage **only its public key** through the existing approved owner SSH connection. The staged request expires after 10 minutes and has an owner-visible six-digit verification code/fingerprint. A separate host-local GTK owner approval window displays pending requests and currently Wolf-paired identities; the owner must independently verify which Wolf identity is that client, match its request code, check an explicit confirmation and approve. The host backend preserves prior keys/policy, writes private backups, and appends only a forced-command `restrict` credential pointing to the **already installed reviewed broker**. Client can verify approval via the restricted Games status request.

This is **not** a new listener, auto-approval, member-access service or host installer; no client-claimed identity, Tailscale address, machine name or Moonlight pairing alone grants the owner workspace. It requires both NOW package on the owner-controlled host and an already adopted, working owner policy/forced Games broker. Requiring pre-existing ordinary owner SSH confines it to the trusted-owner pilot, not untrusted members. Revocation, unexpected external authorized_keys edits, partial failure recovery, source audit, exact-head CI and physical fresh-profile approval/denial remain acceptance gates. **No changes were made to live host services or keyfiles by these source commits.**

## October 24 — Beta startup decision: Dashboard fallback; defer Downloads initial-load issue

Reference MacBook physical test of PR #184 build #623: package checksum verified and installed, but NOW displayed the saved Downloads startup page **without loading its embedded content until the Downloads navigation tab was clicked**. Neither the earlier one-time connection retry (#620) nor the GTK mapped-window startup deferral (#623) received a physical first-open pass. User accepted deferring this noncritical startup-specific issue for beta because selecting Downloads via the main tab or tray works.

**Decision:** Beta may start on Dashboard (or Software by explicit user choice), but **not Downloads**. An old saved `start_page=downloads` is interpreted as Dashboard in memory, without deleting settings; the Settings startup selector no longer offers Downloads. Keep the normal Downloads tab/tray path. Remove the unproven initial Downloads window-map callback and its test; retain ordinary on-demand discovery and fail-closed authorization. Record the known issue for later, and do not claim that startup WebKit rendering was fixed.

No reference-host change. CI and installed-client tests for this new source revision are pending; previously observed #623 second-click behavior is the baseline.

## October 24 — PR #184 #620 startup Downloads tab needs second click (physically observed)

The owner reported that build #620 **opened with Downloads visibly selected but did not actually initialize it until the Downloads navigation tab was clicked again**. Selecting `Keep Existing Setup` in the wizard on an earlier run was not a true connection operation. On source review, `src/main.c` selected a saved Downloads startup page and called `now_downloads_open()` before the main GTK window was shown, whereas the navigation-tab handler performed the load after the window was mapped. This ordering is a plausible GTK/WebKit lifecycle cause; it is not yet proven by instrumentation.

In the PR, defer the initial Downloads load to a single idle callback queued on the window's first `map` signal, preserving the configured startup page and `--start-in-tray` path. Manual Downloads selection continues to call the existing loader directly; no new host/service changes. Regression test checks lazy initialization after mapping. **Source-only until exact-head CI and a cold-start physical pass without an extra tab click.** If mapping deferral does not fix the observed symptom, collect detailed first-open errors rather than masking it by overriding the selected startup page.

## October 24 — #616 initial Downloads recovery regression (physical report; fix source-only)

The owner clarified the #616 test: the Downloads page **hung or did not complete automatic discovery on first opening**, then worked after visiting Settings and clicking "Keep Existing Setup." The current wizard's `w_keep` only closes the dialog; it does not authorize or reconnect anything. The source's Downloads tab/open path can retry the already approved, read-only SSH queue request, so the exact recovery trigger was not isolated. **Do not classify #616 as a clean first-open acceptance pass.**

A source-only follow-up adds **one** delayed read-only Downloads discovery retry after the initial authenticated request fails; no automatic retries are added to managed Steam or state-changing qBittorrent operations. It retains explicit failure state after the bounded retry, rejects missing credentials without attempting SSH, and does not change host services. Requires fresh launch/first-open physical retest and CI on exact head; no claim of guaranteed recovery under prolonged outages.

## October 24 — PR #184 test package #616 MacBook physical smoke pass (reported)

The owner installed and tested unreleased test build `optiplex-now-pr-184-616` on the existing Linux Mint MacBook and reported **"works all good"** following the requested Games, Videos, Downloads, Files, tray and Settings smoke checks. This is a user-reported no-regression pass on the **already enrolled** normal `macbook` Linux account, not instrumented acceptance for every pillar or proof that an unapproved new account can enroll through the GUI. PR #184 exact-head build-and-test plus native sanitizer jobs passed for commit `268cd182ac0bbc15d9d296cc28c3f41a2ac7c0e4`. Its new diagnostics work in code; the observed manual enrollment was on the earlier PR #608 client and cannot establish that #616 automates it. **Next:** finish owner-approved, no-terminal restricted-device enrollment for a genuinely fresh client and verify its denial/revocation behavior before merging the PR.

## October 23 — Fresh Linux-profile owner enrollment failure (physically reproduced; diagnostic fix source-only)

A second Linux account on the same Mint MacBook had valid saved host/user settings, working ordinary owner SSH and a Moonlight profile already paired to the reference Wolf server. PR #184 build #608 nonetheless displayed a perpetual-looking Downloads discovery state and refused managed Games because `~/.local/share/optiplex-now/games-client/id_ed25519` was absent. The Setup Wizard's `AUTHORIZE SSH KEY` step provisions the **different, ordinary** `~/.ssh/id_ed25519` and does not enroll the restricted owner credential. The reference owner identified the correct Wolf client by observing it disconnect, then manually granted that client an owner-policy entry and restricted forced-command SSH public key; **Downloads subsequently worked**. No Wolf, qBittorrent, VPN or other service was restarted. This establishes one owner-profile failure/recovery on the reference system, not supported graphical enrollment.

Source fix in this PR: Downloads now checks for a missing local restricted key before any SSH request and gives a specific enrollment message; unsuccessful queue requests no longer leave the discovery label appearing active; the wizard distinguishes ordinary SSH/Moonlight pairing from separate owner-device approval and does not label that flow fully ready. Python and source-contract tests cover the new failure message and fail-closed no-key check. **Graphical owner-approved restricted-key enrollment, binding to the verified Wolf client ID, revocation and clean-client acceptance remain unimplemented alpha blockers.** Do not call this incident an auto-enrollment fix.

## October 23 — Read-only Adopt Existing / Set Up New host plan (source-only)

Added `server/host_adoption.py`, a deterministic, fail-closed recommendation layer over the existing local Docker service inventory. It recommends inspection of one running/stopped Wolf/Jellyfin/qBittorrent/Gluetun candidate, blocks ambiguous/inaccessible inventories, refuses to infer that a missing Docker container means no native installation, and explicitly blocks unsafe downloader/Gluetun topologies. It never copies service names, paths, container IDs, credentials or Docker environment into its output and **never authorizes adoption or installation**. The local GTK Host Setup review now prints these recommendations after the hardware, install-plan and service-census steps; packaging and mock/installed-package tests cover the new read-only tool. This is progress towards understanding what to preserve on a real host, NOT a working adoption installer. No reference service was touched; fresh-host/client, privileged approval, configuration backup, media mount mapping, viewer denial, and actual VPN fail-closed tests remain open.

## October 23 — Downloads page uses full available window (source-only, awaiting MacBook retest)

The owner pointed out that the two temporary top-of-page buttons (“VUE TORRENT” and “QUEUE SNAPSHOT”) waste precious space on the 2012 MacBook Air. Removed the toolbar and suppressed the informational status label while an authorized WebKitGTK VueTorrent view is active; the authenticated read-only queue is still rendered automatically if an embedded view cannot be opened. This changes only GTK layout and does **not** touch VueTorrent, qBittorrent, server processes or VPN. CI runs independently from physical acceptance; latest client build must be visually checked before claiming release acceptance.

**Next critical path:** host-side safe install/adopt (Wolf, Jellyfin, Gluetun/qBittorrent/VueTorrent with reviewed search plugins), authenticated owner/viewer access isolation and VPN fail-closed testing. Existing reference host is not an installation test; do not replace it in the name of alpha readiness.

## October 23 — MacBook automatic Downloads discovery ACCEPTED on reference devices

After the authenticated host-side `download_queue.py` update (WebUI port 8085; five torrents), the owner cleared the manually configured client **Downloads override** and reopened NOW Downloads. **VueTorrent successfully appeared automatically**, with no manually supplied address. This closes the *reference-device URL discovery test* only. Other physical successes: embedded VueTorrent login/search, tabs retaining the existing WebView, and tray Downloads navigation. Host module rollback backup: `/home/optiplex/.local/share/optiplex-now/backups/download-queue-20261023-171108-510144.py`.

The PR remains draft while release-facing access-control/failure and settings acceptance remain; the broader private alpha is NOT accepted. Specifically, an authorized client detecting an admin WebUI does not prove viewer/member denial at the service endpoint. Clean host provisioning, approved search-plugin packaging, VPN kill-switch test, protected media-root file browsing, and login persistence also remain open. No login secrets have been stored in the repository.

## October 23 17:11 JST — Downloader endpoint discovery host deployment verified

The reference OptiPlex owner ran a backed-up atomic update of the **existing host-side** `server/download_queue.py` module. The deployed code was compared to Git blob `d55d7a2c2e8943b25ec0696f6f5342eefdc35495` from commit `d6a62ef973195c1168dc63c9684bda5aeae8d382`. The host-local `inspect_queue()` health check succeeded and returned **`webui_port: 8085` and five torrents**. Host backup: `/home/optiplex/.local/share/optiplex-now/backups/download-queue-20261023-171108-510144.py`. No Docker, Gluetun, qBittorrent, Jellyfin or Wolf container changes were required. This verifies the host endpoint metadata, **not yet the full MacBook automatic discovery UX**. Owner's next test: clear client Settings > Downloads override, save and reopen Downloads; ensure embedded VueTorrent opens without manual URL. Viewer authorization, VPN kill switch, storage mapping, installer and login UX remain outstanding.

## October 23 — MacBook acceptance: Downloads persistence and tray routing

The owner **physically confirmed** on the MacBook that the latest Downloads client retains VueTorrent when switching NOW tabs and that choosing Downloads from the system-tray menu opens the existing in-app Downloads page. The embedded VueTorrent interface, login and torrent search were also previously verified on this machine. CI build #573 passed; the tested client is a branch artifact, not a published alpha release. The owner has not yet tested automatic WebUI endpoint discovery after deploying the updated restricted host-side queue descriptor, so manually entered Downloads URL remains the verified configuration on this reference system. Full viewer denial, VPN tunnel-failure isolation, server provisioning/search-plugin installation, permitted-root file management and clean-device onboarding are NOT accepted. Do not represent this page as shipped private alpha.

## October 23 — VueTorrent real-device acceptance and navigation fixes (PR #184)

The owner physically verified VueTorrent's login and torrent **search** using existing plugins inside NOW's MacBook GTK embedded Downloads view. This validates the existing adopted qBittorrent/VueTorrent/search environment, **not** automatic provisioning on a new server.

The owner also observed two client UX regressions: (1) reopening Downloads after visiting other NOW tabs reloaded VueTorrent and repeated the authenticated queue check; (2) choosing Downloads from the system-tray menu did not bring the app/window forward. Source fix now retains the existing WebKitGTK view, login state and JS search state when host/SSH user/Downloads override are unchanged, and rechecks/rebuilds only when a different host/config is selected or the prior attempt failed. The tray dispatcher restores the GTK app before invoking the standard Downloads navigation (same page as the top navigation button). Regression tests cover both paths. **Latest package CI and physical client acceptance still required.** This reuse cache is a client UX optimization, not server-side role authorization or revocation protection.

For alpha, owner-approved qBittorrent search engine plugins must be adopted or reproducibly provisioned during server setup (#187). Third-party search engines are Python programs; source inspection, pinned hashes, explicit owner authorization and preservation of existing engine configurations are mandatory. No new plugin was installed or fetched on the reference machine; no live Docker, qBittorrent, Gluetun or credential changes.

## October 23 — Download WebUI auto-discovery (PR #184, awaiting host deployment)

**Physical client observation:** the owner tested the embedded VueTorrent WebUI on the MacBook and reached the qBittorrent login screen after manually entering a Downloads URL. The user subsequently recovered access to their qBittorrent account. NO credentials, passwords, auth cookies, or personal account details have been recorded in this repository.

**Source changes:** `server/download_queue.py` now includes only the verified qBittorrent `webui_port` in its existing owner-authenticated bounded queue result. The Linux `download-queue-client.py --with-port` helper verifies the port (0 = older host) and emits a compact sanitized metadata line plus the same safe queue snapshot. The GTK Downloads module parses that port, combines it with the already paired host address, applies its local-host/private-origin policy, and opens the optional embedded WebView. A manually configured same-host URL remains fallback for older host versions. **Normal flow requires no Downloads URL entry.** The downloader's independent login is intentionally unchanged: no password injection, caching, login bypass, or single-sign-on is implemented.

**Validation:** CI/physical verification of the newest discovery patch and host deployment are separate gates. The reference host still needs an owner-controlled, backed-up update of `download_queue.py`; until then, only the pre-existing manual URL path works. The linked owner SSH preflight checks the device but cannot substitute for server-side owner/viewer controls over the qBittorrent WebUI.

## October 23 — Embedded VueTorrent pilot (PR #184; NOT physically verified)

The Linux client now has an optional, self-contained GTK3 WebKitGTK 4.1 renderer in `src/downloads_webview.c/.h`. It loads only when the user enters Downloads; systems without a WebKit runtime retain the already physically verified authenticated read-only queue. The Debian client merely **recommends** `libwebkit2gtk-4.1-0`, not a required dependency. The configured `Downloads URL` (`cfg[7]`) must use the same host as the connected NOW server (`cfg[0]`), HTTPS for domain names or private LAN/Tailscale IP HTTP, and must not contain userinfo or query parameters. There is no hardcoded reference IP or port. Unexpected top-level navigation, pop-up windows and browser-initiated file downloads are denied. The embedded WebUI uses qBittorrent's **own login**; no NOW credential, Docker socket, qBittorrent cookie, or bypass token is forwarded. Before constructing the WebView, the client must successfully complete the existing restricted owner-SSH `downloads_queue` request. This is a **client-side preflight only**, not yet a host-enforced permission boundary for raw qBittorrent WebUI access; future admin/viewer isolation and audited bridge remain open in #186.

**Not yet acceptance:** no real-device WebKitGTK rendering, VueTorrent content, login, form submission, streaming resource behavior, WebView RAM footprint, 640x500 usability, host-side qBittorrent authentication testing, or cross-platform webview have been verified. Existing VPN/qBittorrent and Jellyfin containers must remain untouched; this change is confined to the client and source-only tests. PR #184 stays draft pending physical GUI test. Private Alpha 1 is still NOT ACCEPTED per `docs/PRIVATE-ALPHA.md`.

# Current implementation and verification

Updated October 23, 2026 (JST). **Source code, published releases, CI and physical acceptance are different evidence levels.** This is the current status page, not a chronological PR log.

## October 23 — P2 authenticated qBittorrent queue physically verified (PR #184)

**Reference OptiPlex owner-only workflow passed.** On the Linux Mint MacBook, the paired restricted SSH credential sent `{"version":1,"action":"downloads_queue"}` to the reference host. The broker returned `success:true`, `service:qbittorrent`, `truncated:false`, and five sanitized queue entries containing only name, progress percentage and state. Four entries reported `missingFiles`; one reported `stalledUP`. No torrent was changed or automatically repaired. Live module install had backed up the prior broker at `~/.local/share/optiplex-now/backups/downloads-queue-20261023-143444-226917/`. Gluetun/qBittorrent were not restarted and no VPN settings changed. This validates only owner read-only queue retrieval, not viewer isolation, GUI presentation, queue mutation, path authorization or VPN kill-switch behavior.

## October 23 — P2 downloader authenticated status physically verified (PR #184)

**Existing reference host only, not alpha acceptance.** The owner's Linux Mint MacBook sent exactly `{"version":1,"action":"downloads_status"}` via its enrolled, forced-command SSH device credential to `optiplex@100.121.156.34`. The response was `success:true`, `version:1`, one `qbittorrent` record, `gateway_bound:true`, `gateway_healthy:true`, with `vpn_egress_verified:false` and `killswitch_verified:false`. This confirmed the new independent inventory module and authorization path on the existing host. The host modules were manually staged with an earlier backup at `~/.local/share/optiplex-now/backups/downloads-status-20261023-142321-251828/`; no containers or services restarted. A first SSH command accidentally used the MacBook login `test` and was denied; the corrected `optiplex` login succeeded immediately. Separately, operator-run public IP inspection observed distinct host and Gluetun exit addresses, but the module does not perform this inspection and does not claim tunnel kill-switch verification. Queue listing, queue actions, file permissions, VPN tunnel interruption and clean-host setup remain open.

## October 23 — Jellyfin zero-URL discovery on existing host (PR #183)

**Physically exercised, source PR and manual host rollout; not yet a tagged client release or full Video acceptance.** The owner verified the existing Jellyfin instance at host loopback `127.0.0.1:8096` and via approved Tailscale address `100.121.156.34:8096`, both identifying the server as `OptiPlex`. After backing up the restricted Games broker and installing read-only `media_endpoint.py` plus its narrow `media` action, the owner tested the PR #183 MacBook build: authenticated discovery returned `available`, and clicking Videos reached Jellyfin without entering an address. No Jellyfin/Caddy/Wolf/Docker/Tailscale services or libraries were modified. Host rollback backup: `~/.local/share/optiplex-now/backups/jellyfin-discovery-20261023-135345/`.

**Still open:** Real playback audio through the newly discovered route, negative unauthorized-device/incorrect-host and outage behavior, supported clean-host adoption/provisioning, viewer roles and CSS appearance differences between direct Tailnet and custom reverse-proxy addresses. The subsequent `media_flow.c/.h` modularization has not been physically retested. PR #183 is not merged or released as of this observation. The Videos fallback to a preconfigured address is preserved for existing installations.

## October 23 — NOW-managed Steam Games live acceptance (PR #182)

**Physically exercised on the existing reference OptiPlex and Linux Mint MacBook; not a clean-host or full private-alpha acceptance.** The owner installed PR #182 test package `1.18.0+pr182.496` on the MacBook and the narrowly authenticated host Games broker on the existing OptiPlex. Direct Wolf Steam advertisement was backed up then removed; the persistent owner Steam directory, Wolf configuration, legacy links and independent physical desktop were preserved. The owner clicked NOW **Games** and observed automatic Moonlight launch, Steam Big Picture, usable mouse/keyboard, playable Resident Evil 2 Remake, Steam exit and subsequent Moonlight closure. A second managed Steam launch also succeeded without restarting Wolf. The game-to-Steam exit once took approximately one minute; the Wolf UI appears briefly during transitions and a Steam window initially appeared minimized/behind other windows. Those are recorded UX/performance observations, not game-streaming failures.

**Lease lifecycle physically verified:** Initial closed Moonlight left one registered Wolf UI session and a joined owner Steam lease with no lobby and no Steam writer. An authenticated guarded Stop recovered one test. The revised non-mutating `reconcile` accepted only an authorized owner's residual Wolf UI session with zero lobbies and no Steam writers, archived the lease, and returned `wolf_ui_connected`. After a subsequent natural Steam exit, a fresh restricted `status` returned `wolf_ui_connected`, evidencing **automatic cleanup** and readiness for another start. Host module rollback backup: `~/.local/share/optiplex-now/backups/owner-launch-pre-reconcile-20261023-131943.py`. Do not generalize to multiple owners or unrestricted direct Wolf access.

**Still open:** Fresh unassisted owner-device enrollment, second device and writer-conflict tests, audio/controller independently verified, supported clean-host GUI setup/adoption, safe recovery across reboots/outages, Videos discovery, downloader VPN isolation and server-enforced viewer roles. PR #182 tests passing is distinct from those physical release gates. Latest PR head tested in CI: `4af7e3c`; physical client package was built from an earlier PR revision, with the subsequently tested host reconciliation update deployed separately. v1.18.0 remains the published prerelease until a new tagged build is actually published.

## Release status

- **Published closed-beta prerelease:** [v1.18.0](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.18.0), October 21, 2026. Download the versioned `OptiPlex-Now_1.18.0_amd64.deb` and verify the release `SHA256SUMS`. This package includes the existing-host client plus a **guarded experimental clean-host Wolf pilot**, not the full three-pillar installer. [Release process](RELEASE-PROCESS.md).
- **Physical client acceptance and follow-up:** [October 21 MacBook test report](QA-MACBOOK-2026-10-21.md) on Linux Mint XFCE v1.18.0 observed Tailscale/server discovery, Moonlight pairing, Wolf XFCE and Jellyfin playback **after manual URL Settings correction** (audio not separately measured). Steam initially failed. On **October 22**, direct Moonlight Steam launch succeeded on the MacBook **after backing up its fresh Wolf Steam directory and manually symlinking it to the existing owner Steam state** (details in [#152](https://github.com/SteezyMode/OptiplexNow/issues/152) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154)). This verifies a working streamed Steam application, **not** a complete game/input/performance acceptance or zero-terminal first-run setup. Pairing and persistence defects remain; **Beta 1 not accepted.**
- **Source and release distinction:** [PR #142](https://github.com/SteezyMode/OptiplexNow/pull/142) removed Music Server Profiles from the onboarding wizard on `main` after v1.18.0 was tagged. [PR #143](https://github.com/SteezyMode/OptiplexNow/pull/143) proposes collapsed optional wake controls. Neither should be represented as included in the tested v1.18.0 install. CI and existing host pilot checks do not prove a clean host deployment or an actual Steam game stream.

## October 23 physical owner Steam acceptance (source-only pilot)

**Physically exercised, not released:** After safely backing up the Wolf
configuration, owner Steam workspace and uncertain launch lease, the owner
cleared a stale lobby with a Wolf-only restart. A new host-local pilot run
using verified legacy NVIDIA `video/x-raw` caps passed CreateLobby and
JoinLobby on the actual OptiPlex. The MacBook transitioned from Wolf UI to
Steam and ran **Resident Evil 2 Remake with working gameplay**, while the
OptiPlex physical desktop remained independently usable. The named Steam
workspace was backed up and verified before launch. See [issue
#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

**Physically verified managed lifecycle on reference host:** After the user
exited RE2R and disconnected Moonlight, Wolf reported zero lobbies/sessions.
With no Steam writer active, merged PR #175's `reconcile` archived the old
v1 lease without Wolf restart. A new v2 Create+Join opened Steam and stored
a private PIN; the operator's guarded StopLobby returned
`{lease_archived:true,status:"idle",success:true}` and returned the MacBook
to Wolf UI. Another preflight passed and a further v2 Create+Join reopened
Steam **without restarting Wolf or manually touching leases**. This proves
the host-local **Create → Join → Play RE2R → Stop → Relaunch** path while the
physical OptiPlex desktop remains usable. Steam audio was not separately
verified.

**Not a completed NOW Games workflow:** The shipped NOW Games button still
runs direct `moonlight stream HOST Steam`. A separate restricted Games SSH
transport has since passed real device-bound status and rejection checks on
the MacBook, but the GTK button does not invoke it. As of the subsequent
read-only October 23 physical check, the reference host had **no active
owner lease**, no detected Steam processes or Steam containers, one Wolf UI
session and zero lobbies. These are point-in-time observations, not a
license to create another Steam session. Automated first-run enrollment,
multi-device handoff, client-side Games orchestration and a clean-host
installation remain unaccepted. **Private Alpha 1 remains unaccepted.**

## October 22 owner Steam source-only development (unreleased)

Following the physical MacBook/Mac mini tests, merged PRs #162, #163 and #164
added **read-only Wolf profile inventory**, **developer-only owner/device
policy**, and an **offline named Steam lobby request planner**. PR #165
added a guarded **host-local Create/Join transaction** with a durable
fail-closed launch lease and simulated failure-path tests. These files are
source-level preparation, not installed operational host services. Normal
client Games still launches the legacy direct Moonlight Steam app, Wolf's
direct-app permissions are not restricted by NOW's policy, and fresh-owner
client P0 remains **unaccepted**. The host-local source work subsequently
passed real Create+Join and a full lifecycle check on October 23, above. See [engineering trail](ENGINEERING-TRAIL.md) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## October 22 Wolf protocol fixture (PR #166, source-only)

The repository now has a bounded allowlisted Wolf socket adapter,
a fixed host-side Docker bridge, and a disposable AF_UNIX HTTP daemon
fixture covering create/join transport and persisted lease behavior.
This is **not an actual Wolf image integration test**, has not been deployed
on the reference host, and does not change the Games shortcut, authenticate
a remote client, or prevent direct Wolf bypass. The fresh-client owner Steam
acceptance gate remains open (#154). See [engineering trail](ENGINEERING-TRAIL.md).

## Real Wolf read-only API compatibility (PR #167)

**Verified actual upstream Wolf daemon, read-only:** GitHub Actions run
`39757247197` started Wolf in a disposable, network-isolated Ubuntu 24.04
container with empty temporary Wolf state and no GPU/input devices or Docker
management socket. The actual daemon's five API GETs returned success:
`apps=2`, `profiles=1`, `clients=0`, `sessions=0`, `lobbies=0`.
This is **not** physical GPU streaming, native lobby Create/Join, an authorized
owner broker, or accepted fresh-client Games. Earlier probe failures were
caused by test assertion, scratch cleanup and restrictive image-volume
validation; all fixes are recorded in [engineering trail](ENGINEERING-TRAIL.md).
The exact image digest is recorded by the workflow, and no owner-host data or
running services were involved. See [real Wolf validation](REAL-WOLF-VALIDATION.md).

## Wolf lobby protocol verification (PR #168, disposable state only)

[Actual Wolf run 39761010450](https://github.com/SteezyMode/OptiplexNow/actions/runs/39761010450)
confirmed the pinned daemon's Create/Join schema and **accepted one real
disposable process-lobby Create POST** via NOW's HTTP adapter. No Join was
attempted and no Steam account, Moonlight session or GPU was used. The source
Steam planner was tightened to reject incomplete tagged Docker runners; older
mock fixtures omitted required fields. **The owner's Games shortcut and host
remain unchanged. Fresh-client P0 still fails acceptance.** See
[validation levels](REAL-WOLF-VALIDATION.md) and
[engineering trail](ENGINEERING-TRAIL.md).

## October 22 host-local owner launch pilot (source only)

The repository now includes a read-only host operator entry point at
`server/owner_steam_pilot.py inspect`, using actual Wolf inventory and the
existing named-profile lobby planner. Enrollment requires explicit host owner
and device consent; a later live Create+Join is guarded by additional host
operator flags and the existing durable lease. This **is not remote device
authentication, a deployed host service or a NOW Games-button change**. The
MacBook's active Wolf UI session, paired identity and complete `user` Steam
runner were observed physically, but native owner Steam Create+Join and
fresh-owner one-click access remain **unaccepted**. See
[the guarded host pilot](HOST-OWNER-PILOT.md) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## October 23 Wolf Steam video producer caps guard (PR #174, source only)

Physical CreateLobby returned a GStreamer pipeline syntax error followed by a
20-second setup timeout. Code inspection found NOW passed an empty
`video_producer_buffer_caps`; upstream Wolf uses that string in the video
producer. This is a strong candidate, **not a verified root-cause fix**.
Source PR #174 requires explicit host-verified software or NVIDIA-zero-copy
caps and refuses a create attempt otherwise, without writing a lease.
The previous failed lobby and uncertain lease were subsequently reconciled
in supervised recovery. GitHub tests were fixture/protocol evidence on merge;
the corrected caps subsequently passed real Steam + RE2R and relaunch tests.
See [host pilot](HOST-OWNER-PILOT.md) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## Games button integration boundary

`server/owner_games_request.py` is the narrow `status/start/stop` host
policy handler; `server/owner_games_ssh.py` accepts those operations over
an owner-approved, forced-command SSH key bound to an existing Wolf device.
That restricted path has now passed a real MacBook `status` request and
negative shell and remote-forwarding tests. The application is **not**
connected to the installed NOW Games button, and a generic client has no
zero-terminal Games-key enrollment. Source/CI tests do not replace full
live Start/Stop through the new transport or a physical GUI acceptance.

## October 23 physical restricted SSH and Steam alias audit

**Physically tested on the existing reference OptiPlex, not released:** The
MacBook generated its own independent Ed25519 Games key. The owner verified
the existing Wolf device grant and installed an OpenSSH
`restrict,command=...` entry binding the key to that device. With the
host-only Games policy still **disabled for Start/Stop**, the MacBook's
restricted-key `status` request returned `wolf_ui_connected`. A request
to run ordinary remote `id` failed with a denied JSON response and SSH
exit 1; reverse SSH port forwarding was refused with exit 255. These
checks verify this credential's narrow behavior, **not** all key-revocation,
multi-tenant isolation or production onboarding cases.

The host preflight reported `enabled:false`,
`legacy_links_reviewed:false`, caps `video/x-raw`, no active Steam
lease, and no matching Steam processes or containers. A top-level,
nonrecursive inventory completed across **8** Wolf per-device folders:
**5** `Steam` paths are symlinks to the same existing
`profile-data/user/WolfSteam` workspace; **3** use separate directories.
The earlier recursive scan was incomplete at 500 directories, but the
top-level per-device inventory completed. No files or links were edited.

The real Wolf apps inventory still exposes **Wolf UI, OptiPlex Studio
Desktop and direct Steam** to Moonlight. The named `user` profile also
includes Steam. Consequently, direct Steam can bypass NOW's single-owner
Games lease and potentially write the shared Steam workspace. Keep the
five symlinks and owner profile untouched; **do not enable remote
Start/Stop or delete direct Steam until the GTK managed Games flow and
controlled bypass-removal/rollback plan are ready**. The currently installed
NOW Games button still targets direct Steam. Full details in
[owner Games SSH](OWNER-GAMES-SSH.md) and [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## Capability status

| Capability | In current source | Real-world acceptance |
| --- | --- | --- |
| GTK3 client, saved settings, Games/Videos entry points, tray, diagnostics | Implemented for preconfigured hosts | v1.18.0 Mint client test passed Videos launch and playback after a manual URL fix; wizard URL persistence failed (#147); tray resize failed (#146) |
| Tailscale graphical setup, discovery and SSH trust/enrollment | Implemented GUI and helpers | v1.18.0 real client recognized existing Tailscale, discovered Wolf host, presented native SSH fingerprint and password dialogs; new login, verification outcome, reconnect and negative paths not accepted |
| Wolf/Moonlight connection and pairing | Pairing bridge implemented | Genuine Flatpak/AppImage pairs observed; Wolf XFCE AppImage stream passed; Steam AppImage streaming passed October 22 **only after manual Wolf server-state symlink repair** (#152, #154); buried approval window, manual refresh and missing completion feedback (#144, #145) |
| Moonlight and encrypted backup GUI | Flatpak guided install and AppImage selection implemented | Fresh client Flatpak install observed; legacy Intel Flatpak codec warnings; AppImage XFCE streamed; backup and upgrade preservation not tested |
| Owner-configured media, downloads and files | Videos/Music/Downloads URLs, SFTP and Gluetun status; no managed media install | Jellyfin content playback on existing host physically passed from Mint client with manually saved URL; audio not separately measured; downloads, files, VPN leak and managed Jellyfin **not** tested; no-URL service onboarding is #148 |
| Optional music service | Music link and existing-host profile export for a DroppedNeedle/slskd/qBittorrent/Gluetun configuration | Experimental for general users, no bundled DroppedNeedle installation, recommendations or Spotify-like catalog |
| Server Setup review | Separate GTK window; real read-only preflight and plan shipped in PR build | Real hardware observation useful, but **not** an installation certificate |
| Clean NOW-managed Wolf installation | Developer/alpha implementation in `server/host_install.py` and GUI, AMD/Intel/NVIDIA; immutable image, root recheck, dedicated state | **No confirmed clean physical host install** |
| NVIDIA userspace driver volume | `host_nvidia.py`: version-specific build with official installer SHA256 check; no host-driver replacement | Physical encode and driver-update migration/rollback **unverified** |
| Separate game sessions preserving host display | Wolf named-profile Steam Create/Join/Stop source pilot; installed NOW Games button not wired | **Physically verified on reference OptiPlex:** MacBook played RE2R while host desktop stayed free, followed by managed v2 Stop/relaunch. **Not accepted on fresh client or clean host through NOW GUI.** |
| Restricted owner Games credential | Forced-command per-device SSH status/start/stop code on `main`, manually installed on reference host | Physical MacBook `status` succeeded; shell and reverse forwarding denied. Start/Stop **disabled**, wrong-key/revocation and GTK Games handoff **not** physically accepted; 5 shared legacy Steam aliases and direct Steam bypass remain. |
| Windows clients and hosts | Explicit roadmap: Windows client first, independent-session Windows host later | Neither is implemented; Windows host adds licensing/technical feasibility gates |
| Owner-mediated automatic device access by email | Future design only | Not implemented |
| Turnkey install, dependency setup, repair, upgrades, uninstall | No complete end-to-end implementation | Not alpha-accepted |

A running Docker container is **not** an active session, verified hardware encoder or successfully paired streaming client. Unknown service status remains unknown.

## Technical boundaries

- The [public-alpha product contract](PUBLIC-ALPHA.md) requires **all three** physically validated workflows: independent games, Jellyfin video and VPN-isolated remote download administration. The experience must keep the physical host desktop usable and ordinary services outside the download VPN. The role model is **owner/admin** (downloads, file management and settings) versus **member/viewer** (authorized playback and optionally approved gaming), enforced server-side. **None of that full stack or access boundary is accepted today.**
- Published v1.18.0 includes an **experimental, guarded clean-host Wolf-only installer** requiring a clean Ubuntu/Pop!_OS 24.04 amd64 host, an OS administrator prompt, Docker/Compose already present and manually verified immutable image inputs. It has **no clean physical host acceptance** and does not install Docker, Jellyfin, media services or VPN downloads. The main existing-host client does not automatically provision any service.
- Install code refuses preexisting NOW-managed workspaces/projects and Wolf port conflicts. It does not adopt or delete user containers. The live reference host is **not** an installation test target.
- NVIDIA's manual driver-volume first-install path exists, but automatic regeneration and safe migration after a driver update do not. The installer is not byte-for-byte reproducible because base image/apt dependencies are not fully pinned. [Host installer contract](HOST-INSTALLER.md).
- The client remains modularizing incrementally. `src/main.c` is still a substantial GTK controller; native tests and sanitizers do not cover every UI path or field condition.
- The source also retains separate experimental host staging, transaction and local-authorization modules. Their tests do **not** establish that these prototypes are deployed or connected to the operational installer.

## Immediate acceptance gates

**Next implementation:** integrate the restricted Games client with GTK without blocking the UI: verify the dedicated credential, start `Wolf UI` through Moonlight, wait for a matching authenticated `wolf_ui_connected` status, issue at most one managed Start, and provide meaningful busy, failure, reconnect and guarded Stop behavior. No implicit fallback to direct Steam on a denied/uncertain managed launch. Validate through NOW, then plan a reversible, backed-up removal of only **direct** Steam from Moonlight's app list while preserving the named owner profile and existing symlinks. Keep host Games write controls disabled until bypass/isolation and race issues are reviewed. After this, address first-run pairing and settings persistence, test a second household device, and separately validate a clean host (#154).** Use the [Host installer acceptance checklist](HOST-INSTALLER.md#physical-host-acceptance-before-alpha-sign-off) for a **clean server plus a second client**. Record OS, GPU/driver, Docker/Compose, Wolf digest, package build, observed video/audio/input and recovery behavior.

Continue [Beta 1 client acceptance](BETA-ACCEPTANCE.md) against an owner-approved existing host. The [MacBook report](QA-MACBOOK-2026-10-21.md) is a partial device pass and a set of blocking defects; restart/upgrade/reconnection, new Tailscale sign-in and full gaming remain open. The two acceptance tracks must not be conflated.

**Do not announce a validated alpha or commercial readiness based on source and CI alone.** Fix physical-test defects before adding more server frameworks, simulated lifecycle features or general-purpose dashboards.

## Tracked decisions and references

- [Product direction and phased roadmap](PRODUCT.md) defines scope; [Architecture](application-design.md) defines privilege/data boundaries.
- [#76](https://github.com/SteezyMode/OptiplexNow/issues/76): existing-host client acceptance.
- [#98](https://github.com/SteezyMode/OptiplexNow/issues/98): reproducible NOW Host install, operational readiness and recovery.
- [#94](https://github.com/SteezyMode/OptiplexNow/issues/94): future existing-account device authorization.
- [#85](https://github.com/SteezyMode/OptiplexNow/issues/85): long-range Wolf/desktop feasibility.

For individual module changes, consult [merged GitHub PRs](https://github.com/SteezyMode/OptiplexNow/pulls?q=is%3Apr+is%3Amerged) instead of maintaining another chronological PR catalogue here.
