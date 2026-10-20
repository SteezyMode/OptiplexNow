# OptiPlex NOW — repository guidance for coding agents

Read [README.md](README.md), [docs/CURRENT-STATUS.md](docs/CURRENT-STATUS.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/ROADMAP.md](docs/ROADMAP.md) before substantive changes. Read [docs/adr/001-single-package-modular-provisioning.md](docs/adr/001-single-package-modular-provisioning.md) for the accepted future direction.

## Truth and scope
- Existing shipped behavior is established by source, tests, tagged artifacts and documented hands-on verification—not by proposals. Check versions independently. The current NOW 1.x client expects an already configured server; the fresh-server wizard is not implemented.
- NOW manages personal Linux streaming/server access. Studio is a separate local-first creative project application. Do not add Studio project/Codex internals to NOW.
- The planned NOW 2.x direction is **one native Debian package** with client/server/both workflows and independently selectable, externally installed service adapters. Wolf game/desktop streaming is the initial server provisioning target; Moonlight Web, Jellyfin and DroppedNeedle are optional integrations. An advanced optional Downloads & Music category covers qBittorrent/VueTorrent, slskd, and Gluetun where selected. ListenBrainz/Last.fm are optional DroppedNeedle account connections, not servers NOW installs. None are Wolf MVP prerequisites.
- Existing client features and configured services must remain functional during the transition. Preserve user profiles and backward compatibility unless a reviewed migration explicitly changes them.
- Do not present proposed integrations, server provisioning, security, multi-user isolation or rollback as shipped.

## Engineering discipline
- Audit imports, callers, package manifests, tests, configuration and real installed behavior before removing or changing anything. Do not add infrastructure or features just because a plan mentions them.
- Prefer upstream-supported APIs, packages and settings; record compatibility assumptions. Never fork upstream solely to change branding.
- Service adapters must support read-only discovery first; never claim ownership of an existing installation by default.
- All privileged/provisioning changes require clear preview, user confirmation, narrow privileges, idempotent execution, actionable errors, and defined recovery/rollback limits. Never auto-open public ports, replace working containers, reset pairing, or delete user data.
- Separate client UI from server-side privileged execution. Do not expose Docker/Wolf sockets to web clients or untrusted containers; keep secrets out of Git, logs and diagnostics.
- Changes to NOW must not modify running Wolf, Caddy, Jellyfin, DroppedNeedle, qBittorrent, VueTorrent, slskd, Gluetun, Moonlight Web, Tailscale, unrelated containers, or the reference host without explicit task-specific authorization.
- Work on isolated branches, make focused changes, run relevant unit/build/package/GTK tests and report what was actually verified versus still untested. No release tags or deployment without explicit request.
- Keep README, CURRENT-STATUS and roadmap aligned when milestones change. Record significant new decisions in ADRs; do not retroactively rewrite historical records.

## Out of scope by default
Generic homelab app store, arbitrary container dashboard, speculative white-label forks, automatic remote-server takeover, and Studio's creative agent functionality.
