# OptiPlex NOW Beta 1 — Locked Execution Order

**Decision:** Finish the existing GUI and dashboard backlog first. **First-run Tailscale/SSH/Moonlight onboarding is the final major engineering stage**, followed only by release verification. Do not reprioritize because a new feature is appealing; explicitly discuss and approve any amendment before changing this order.

## Invariant order (one stage at a time)

1. **Tray and Settings stability.** Confirm merged PR #74 on a real XFCE client: `|` descriptions visible, desktop rename persists, no Settings-save crash, config retained. Fix any regression uncovered.
2. **Host dashboard.** Verify merged PR #75 on-device: accurate host CPU/GPU utilization and temperatures, RAM, VRAM, disk, Tailscale; compact window, graceful unavailable metrics. Fix inaccuracies before advancing.
3. **Small GUI completion.** Replace numeric tray ordering with familiar XFCE-style item list plus Up/Down arrows; readable light/dark controls; retain separate enabled/featured settings; test save/reorder/restart.
4. **Operational diagnostics.** Add AirVPN/Gluetun status and active Wolf session overview with explicitly confirmed, safe end-session action. Preserve existing host services. Validate real-state and failure handling.
5. **First-run connectivity and walkthrough — LAST major implementation stage.** Meet Issue #76: fresh Linux laptop; a pre-approved user signs in to Tailscale, connects to the right server, accesses Jellyfin and pairs/launches Wolf Steam/Desktop. Guided GUI, no terminal/config editing, persistent pairing, required security approvals clear. Real timed <=10-minute independently completed test.
6. **Release gate only.** Clean installation, upgrade preservation, reboot test, UI smoke tests, CI, correct version and checksum, GitHub release assets and short instructions.

## Beta scope discipline
- No redesign, aesthetics polish, new apps, multiple Wolf desktops, new server architecture, or unrelated features before completion.
- Bugs blocking an active stage are in scope; document deferred enhancements separately.
- Do not claim success from passing CI alone. Verify on real client and host.
- User explicitly wants reminders/challenges if conversation strays from these stages.
