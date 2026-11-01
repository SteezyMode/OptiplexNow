# NOW UI visual identity and polish audit — 2026-11-01

**Scope:** Source and GTK-style review of current main-branch Dashboard, Games, Videos, Downloads search/transfers, Settings, navigation, onboarding, secondary Python dialogs and the shared palette. This is **not** a claim of physical visual QA on the user's laptop/projector. No host or GPU state is changed.

## Direction: utility-grade media console

The product is now used as a daily remote-control surface, so prefer **instrument clarity and quiet controls** over splash-screen polish. Keep the established graphite/olive base, slightly warm neutral text, and restrained terracotta/copper emphasis. Do not introduce branding that looks like Dell/OptiPlex commercial identity: the commercial name is still undecided.

### Style contract

| Role | Current reference | Use |
|---|---|---|
| Canvas | `#101111` | Window/background |
| Control surface | `#222724` | Quiet buttons/panels |
| Panel/metric | `#171918`–`#1e211f` | Telemetry and launch tiles |
| Primary accent | `#c47d65` | Selected tab, emphasis, focus border |
| Foreground | `#ece8e0` | Primary text |
| Secondary text | `#b8b4ac` | Section labels and help |
| Healthy | `#84d9a7` / `#b3e4cd` | Verified/qualified health readouts only |
| Destructive | `#9d3543` on hover | Shutdown and dangerous actions, not normal navigation |

Use one coherent accent family. **Do not use teal as a second generic hover color.** Distinguish navigation, CTAs, secondary settings, state displays and destructive controls by semantics, not arbitrary page colors.

### Typography and density

- Continue using Inter where installed. Keep Dashboard host name prominent, but at **28 px**, not 32 px, to reserve space for connection state on small 4:3 screens.
- Use **16 px** subpage headings, **11–12 px** ordinary control/status labels, and reduced-weight muted explanatory copy. Never make key status legibility depend on a tooltip or on color alone.
- Preserve the current primary 56-px launcher tile dimensions for PLAY STEAM / OPEN VIDEO LIBRARY. Keep action buttons content-width in Settings.
- Preserve the optional GPU readout as **secondary lowercase `cap`** and do not display instantaneous draw alongside VRAM. Preserve its invisible click target.

### Interaction rules

- Neutral controls rest on graphite/olive. Hover/focus changes the border and surface with copper-family emphasis; the hover state is not an orange page-sized block.
- Selected top-level tabs keep copper fill and dark text. On GTK, explicitly style child `label` foreground during selected/hovered states to avoid white text on a copper background.
- Shutdown remains visually distinct from Wake/Sleep/Restart, including on hover. Never use copper for destructive meaning.
- Visible keyboard focus must remain distinguishable, even without a mouse; don't remove GTK accessibility labels or hide focus only to achieve a cleaner look.
- Empty/unknown/unavailable metrics remain labeled as such without a bright error state for optional features.

## Source findings by surface

| Surface | Current strength | Remaining concern / next physical check |
|---|---|---|
| Dashboard | Functional state-first hierarchy; four metrics, GPU shortcut, qualified VPN | Check crowded host name + two status pills at 430–560 px; verify CPU/GPU label ellipsis and 2×2 power controls |
| Games | PLAY STEAM is a clear action with a single distinct CTA | Compare help/status spacing against Videos on small screen |
| Videos | Matches Games launcher tile in v1.21.11 | Confirm browser handoff status remains readable and no dead embedded-player affordances |
| Downloads | Native transfers, incremental search, sortable columns and explicit confirmations | Header VPN badge now has its own row above REFRESH / Advanced Vuetorrent to prevent overlap; verify popover and narrow result columns |
| Settings | Six equal navigation tiles in a responsive two-column FlowBox, nested tabs, opt-in Host GPU | Confirm two columns at normal width, one full-width column at 430 px, and reachable Save/Cancel |
| Onboarding / dialogs | Shared theme CSS covers the native/Python windows | Python modal palettes use the shared fallback, not every main-window selector; inspect independent visual QA before broadening styling |

## Pass 1 (this PR)

- Replace legacy teal hover states in the main app with neutral/warm copper-family emphasis.
- Fix selected-tab, launch-tile, power-button and destructive-control **GTK child-label contrast** in hover/active states.
- Add consistent focus border indication; keep keyboard navigation behavior unchanged.
- Slightly rebalance host title and subpage heading sizes. Do not touch layout breakpoints, authorization, LACT, or launch actions.
- Add source regression checks and run both CI jobs; leave screenshot/device approval separate.

## Subsequent visual QA (not authorized by this source-only pass)

1. Collect user-approved real screenshots at narrow laptop window, normal desktop, projector 4:3; mask hostnames, paths, downloads and other identifying/private data.
2. Test tab/focus/hover states at 430 px, 560 px, 720 px and 1024 px; check text truncation, scrollable forms and button labels.
3. Audit the separate Python GPU power and owner-approval windows against the core app, then standardize shared styling without changing their permission checks.
4. After the commercial name is selected, design a small brand mark/icon and replace the development codename, **without** implying Dell affiliation.

The existing `releases/latest/download/OptiPlex-Now_amd64.deb` flow remains unchanged. **Do not publish this pass merely because CI is green; approve its visual direction first.**

## Owner device review, following PR #241 trial

The first PR #241 installer was reported functional and nearly visually correct, but the Settings home looked poorly arranged: every entry was a short, left-aligned button in a vertical stack. At the 430 px minimum width, the Downloads VPN status also collided with the Advanced Vuetorrent action. Both observations are tracked as real-device regressions, not treated as minor cosmetic preferences.

The revised PR uses six equal-sized, centered Settings cards in an adaptive two-column GTK FlowBox, and separates Downloads' title/VPN row from its action row. This retains the Settings callbacks, VPN popover and VueTorrent handoff and does not change remote operations. Physical acceptance of both layouts after reinstalling the new PR artifact remains open.
