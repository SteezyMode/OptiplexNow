# OptiPlex NOW roadmap

**Updated:** 2026-10-20. **Planning document, not a feature inventory or release promise.** See [CURRENT-STATUS](CURRENT-STATUS.md) for released, verified work. Do not mark a milestone complete based only on unit tests.

## 0 — Protect the existing client
Preserve existing NOW 1.14-era streaming, shortcuts, presets, remote access and maintenance behavior. Establish baseline tests and a documented compatibility matrix. Correct outdated docs without equating reference-host capabilities with shipped installer behavior.

## 1 — Guided Wolf server MVP (highest priority)
- Choose client, server or both.
- Read-only hardware/encoder/OS/network/storage and existing-service discovery.
- Preview and explicitly approve a supported Wolf installation without replacing existing configured services.
- Install/configure one working game/desktop profile on a **fresh supported test machine**.
- Pair a native Moonlight client and demonstrate an actual live stream.
- Validate repeat setup, diagnostics, upgrade limits and recovery/uninstall behavior.

**Acceptance:** Another user can reproduce a working stream on a supported clean Linux machine following NOW prompts, without manual bespoke server engineering. Failed/partial installs leave recoverable state.

## 2 — Maintenance and adoption
Read-only detection/adoption of existing Wolf instances, status explanations, safe update planning, backup/restore testing, minimal privileged management interface, and redacted diagnostic export. Test live behavior and protect pairing/user mounts.

## 3 — Independently optional integrations
**Moonlight Web:** supported browser access and maintenance; reuse existing working installations.
**Jellyfin:** media service detection/opt-in setup, safe storage/permissions, health and native UI handoff.
**DroppedNeedle:** opt-in music workflow detection/setup and independent lifecycle.
Order reflects priority, not mandatory dependencies; none should hold back MVP streaming. Existing NOW 1.x shortcuts and MoonlightWeb maintenance remain separate from future provisioning claims.

## 4 — Multi-user desktop feasibility
Evaluate distinct persistent user identities, device authorization, home/data isolation and multiple concurrent Wolf desktops in a disposable environment. Do not claim secure multi-tenancy before isolation and recovery acceptance.

## 5 — External beta and commercial validation
Document supported hardware, collect clean-install completion rate, manual intervention, support time, stream reliability, recoverability and willingness to pay. Resolve NOW application licensing, upstream component attribution and trademarks before commercial distribution.

## Explicit non-goals
General-purpose app store, broad arbitrary distro compatibility at launch, mandatory media modules, cloud control plane, replacing upstream streaming servers with forks, and merging Studio into NOW.

Track implementation through issues/PRs and checklists; update [CURRENT-STATUS](CURRENT-STATUS.md) only after evidence, and retain negative test results.
