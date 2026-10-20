# NOW Linux client — v1.1 priority correction (2026-10-20)

**Approved through product-owner direction:** The working Web Gaming URL is not an installer priority. The previous [immutable v1.0 release contract](https://github.com/SteezyMode/OptiplexNow/blob/4b682acb0ae31fdd0fcb72b0d30d6921fc27644b/docs/CLIENT-INSTALLER-MVP.md) remains preserved for audit; this focused amendment supersedes its Web Gaming portability priority.

## Single product / installer direction

**OptiPlex NOW is one product with two eventual installation roles:** Client (connect to an existing host) and Server (provision/maintain a host). Today the functioning GTK launcher is the Linux client. Do not force server-side Docker/Wolf install onto a client; the guided Linux server-role installer is a separate subsequent track within the **same NOW product**. OptiPlex Studio stays independent.

## Locked client release work, in order

1. Preserve stable Linux NOW 1.14.0 behavior, current GUI/tray, server status, existing Tailscale/Moonlight installs and configuration; finish review of client auth state #51 and Snap reuse #52.
2. **Fresh-client dependency setup:** .deb installed, detect missing Tailscale/Moonlight; clear, user-consented in-application dependency installation and real status/errors. No unnecessary terminal; reuse native/Snap/AppImage/Flatpak Moonlight. **Current work: draft PR #57.**
3. **Tailscale browser login:** integrate official provider authorization only if not already connected, and confirm actual daemon state; complete fresh-client polkit/browser acceptance. Existing speculative #56 was withdrawn because it was stacked on out-of-scope Web Gaming work.
4. **Server choice and native Moonlight/Wolf pairing:** find permitted tailnet server, support manual/LAN, save identity, user-visible pairing PIN process, native Moonlight once, no mandatory SSH/host administration credentials. Existing GTK UI, same streaming shortcut.
5. **End-to-end release gate:** clean Mint/Ubuntu/Pop!_OS x86-64 and real client, wired/wireless, local/remote Tailscale, Steam/desktop Wolf session, audio/gamepad/reconnect, upgrade and failure paths. CI + manual evidence, **then** user-approved release.
6. **Windows NOW client next** (native Moonlight and Tailscale, Jellyfin browser). The subsequent server installer stays one product, with its own planned work.

## Explicit defer / do not touch

- The known working `https://games.monumentrisk.com` Web Gaming endpoints stay in the existing NOW client for this beta. No Web Gaming URL generalization, portable Web Gaming preset work, MoonlightWeb fork, embedded browser, alternate domain, web gateway deployment or server-side changes in the Linux client release.
- Web Gaming portability draft #55 and its downstream experimental auth draft #56 are closed/unmerged and are **not** release blockers. The genuinely useful authentication ideas may be ported to a clean client-only branch later.
- Do not spend client release time building multi-user invite accounts, email PIN infrastructure, Windows server support, new tile dashboards or a parallel product.
- No silent merges, release tags or modifications to the reference machine.

**Progress is measured by completion of the fresh-client install → Tailscale sign-in → server choice → native Moonlight pair → working/reconnect stream path.** Features that do not reduce friction on that path are not release blockers.
