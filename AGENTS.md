# Development agent instructions

This repository contains a self-hosted entertainment application under the internal codename **OptiPlex NOW**. The commercial name is undecided. Do not imply Dell affiliation. These instructions apply to code, tests, documentation, PRs, and releases.

## Mission and authority

**Ship a self-service version of the ACTIVE, owner-validated Private Alpha 1; formal acceptance is still open.** The owner declared private alpha active on November 3, 2026, after verifying v1.21.16 on the household reference setup. That is **phase entry**, not end-to-end clean-host or security sign-off. Keep v1.21.16 as the known-good functional baseline. The current, authoritative exit contract remains [docs/PRIVATE-ALPHA.md](docs/PRIVATE-ALPHA.md): (1) independent games, (2) personal Jellyfin video, and (3) VPN-isolated qBittorrent downloads plus protected admin file management. These must work together on supported hardware. A thin launcher with three external URLs does not meet the gate.

Read, in this order, before proposing work:
1. `docs/PRIVATE-ALPHA.md` for the active release acceptance contract.
2. `docs/CURRENT-STATUS.md` for what was actually implemented, CI-tested, physically tested, or released.
3. `docs/PRODUCT.md` for product direction and later opportunities.
4. `docs/application-design.md` for architecture and privilege boundaries.
5. The relevant source, tests, open issue, and upstream interface. Read `docs/ENGINEERING-TRAIL.md` only for relevant past decisions and incidents.

`docs/PUBLIC-ALPHA.md` is the longer-horizon public release contract. `docs/BETA-ACCEPTANCE.md` tracks an older, narrower existing-host client beta. Do not mistake either for the current Private Alpha 1 acceptance gate. When sources conflict, identify the conflict instead of silently broadening scope.

## Work selection: finish workflows, not fragments

**Duplicate-work preflight (required before creating a new feature or fix PR):**
1. Verify current `main` and the official published .deb separately; read the current acceptance contract and last merged/main CI evidence.
2. Search the existing implementation **and** relevant open, merged, and closed-unmerged PRs and their issue comments for the same user-facing behavior. Old passing CI on a diverged branch is not acceptance.
3. Identify what is *missing in current source* versus what is *implemented but physically unverified*. Do not reintroduce superseded Web Gaming, VueTorrent-webview, broad SSH-pairing or auto-trust designs just because their PR titles match a request.
4. Prefer updating the existing owning issue and targeted tests over inventing a parallel module, new framework, issue or PR. Link replacement PRs and record why an old branch is closed or selectively salvaged. Do not close a real hardware/security acceptance gate on mock evidence.
5. Owner-only **Private Alpha 1** excludes member/viewer account implementation, though unapproved host-service requests must be denied. The product roadmap may include post-alpha roles without adding them to the release gate.

- Pursue one ship-readiness critical path at a time: **reproducible Host/Client installation and backend account provisioning; fresh device/Game authorization; automatic Jellyfin setup/discovery; VPN/Downloads fail-closed and root security; recovery and independent disposable clean-host acceptance**. Reuse working Games/Video/Downloads implementation instead of reopening features. Security/regression fixes may interrupt in proportion to proven risk.
- Every issue/PR must name the end-user outcome, the relevant private-alpha acceptance check, the observed deficiency, and how completion will be demonstrated.
- Do not build optional music/books/comics, separate member Steam instances, pooled game installs, Windows hosts, custom VPN sales, billing, novelty widgets, or in-stream overlays for Private Alpha 1.
- New infrastructure, protocols, frameworks, services, or documents require an explicit blocking need. Prefer completing an already-started implementation.
- Do not create another state machine, adapter, fixture, or manager merely because one would be architecturally interesting. Demonstrate why existing components cannot meet the requirement.
- Preserve known-good functionality. No broad rewrite, unexplained rename, or mass deletion as an ordinary refactor.
- No automated GitHub issue/PR proliferation. Consolidate duplicate issues and close only with real acceptance evidence.
- **Feature freeze:** Downloads UX, streaming and the optional Music integration are functional on the reference household; avoid redesigning them without a demonstrated defect, security blocker or explicit new product decision. Treat SubHub/subtitle translation as independent, never as a Private Alpha 1 release gate.

## Code and design boundaries

- Follow existing module boundaries; move code out of `src/main.c` incrementally when directly changing that area. Avoid increasing global UI state or creating generic abstractions without reuse. **Modularity is a ship-readiness quality criterion:** extract cohesive views/host service modules with explicit ownership and small APIs, protect async/cancellation lifetimes, and add behavior-preserving regression tests. Use [#185](https://github.com/SteezyMode/OptiplexNow/issues/185) to track scoped code hardening. No big-bang rewrite, mandatory architectural framework, or arbitrary line-count goal; prioritize actual setup, recovery, security and shipping risks.
- Prefer stable upstream interfaces for Wolf/Moonlight, Jellyfin, qBittorrent, Gluetun, Tailscale and Docker. Do not rebuild their media, streaming, VPN, or torrent engines.
- Keep privileged host operations in a narrow, authenticated host-side boundary. Never give an ordinary NOW client unrestricted Docker, Wolf management socket, host filesystem, or VPN administrative access.
- Treat Tailscale connectivity, Moonlight pairing, host ownership, service login and gaming authorization as distinct checks. Server-side permissions matter even when a UI button is hidden.
- An approved owner device must resume the **same persistent owner Steam workspace**. Do not use a per-client symlink as the consumer solution; prevent conflicting writers and ambiguous create/retry operations.
- Downloader traffic alone uses the commercial VPN, and must stop on loss of the tunnel. Gaming, Jellyfin, and host networking remain independent. Verify actual egress and failure behavior, not just a green container badge.
- Member/viewer credentials must not permit qBittorrent administration, unrestricted SFTP, protected file operations, host service changes, or owner's Steam state.

## Safety and truthful evidence

- Treat the active reference OptiPlex as production-like personal infrastructure. Never overwrite, migrate, uninstall, restart or reconfigure live services, drivers, Steam homes, Jellyfin libraries, downloads, or VPN settings without the owner's explicit approval and a tested rollback plan.
- Do not automatically retry a state-changing operation after an unknown response. Inspect state and protect durable owner data.
- Never commit credentials, auth cookies, device private keys, Steam state, private URLs/tokens, downloaded content, or raw sensitive Wolf responses.
- Classify results explicitly: **planned / code present / mock tested / real upstream compatibility tested / physically exercised / release-accepted**. Do not claim a GUI action worked because a command was invoked, a Docker container is running, or CI passed.
- Test the actual end-to-end flow with real gameplay, media playback, VPN exit and kill switch, and denied unauthorized requests before accepting a feature.
- Run focused tests and relevant regression, sanitizer, packaging and CI checks. Report failures and unperformed physical tests without euphemism.

## PR and handoff format

Each change must include: problem and supporting evidence; user-visible alpha outcome; exact modules modified; non-goals; test commands and results; data/security boundaries; rollback plan; physical checks still needed; and **one concrete next action**. Use the single canonical PR template.

Update `docs/CURRENT-STATUS.md` only when supported status changes. Add a concise, dated `docs/ENGINEERING-TRAIL.md` entry for consequential decisions/incidents; do not duplicate complete PR descriptions. Do not create parallel roadmaps or bloated handoff documents.

A milestone stays open until its complete, independently observable acceptance checks pass. A passing workflow is not approval to ship.

## Interaction with the product owner

- Default to a recommendation and the smallest executable next step, not a menu of ten speculative features.
- Explain technical blockers in plain English and identify which upstream component owns them.
- Require explicit authorization before live-host mutation or material scope change.
- Do not ask for permission for ordinary reversible, scoped code changes inside an approved task.
- If stopped, state exactly what was done, what was not done, and what must happen next.

**Operating rule: optimize for a working, safe, understandable alpha, not commit counts, infrastructure depth, or the appearance of progress.**
