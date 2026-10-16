# OptiPlex Studio v1 — application-selection lock (2026-10-16)

This file **freezes product scope**, not the installed state. OptiPlex Now is separate: **do not modify its production client, Wolf configuration, streaming drivers, Jellyfin or remote-launch paths as part of Studio deployments**. Do not merge this feature branch into Now's stable branch.

## Approved applications

| Role | App | Technology and status | Upgrade policy |
| --- | --- | --- | --- |
| Dashboard | OptiPlex Studio Hub | Localhost 18768, installed | Manual verified changes |
| Music sketch/synth | UltraBox-based Studio Synth | Separate Studio Compose stack, 18765; its SQLite song API uses a secret bearer token, **installed and persistent** | Pin upstream source SHA, preserve named volume |
| Multi-track recording/edit | AudioMass | Static browser editor, 18766, installed | Pin upstream source SHA |
| Full music production | openDAW | Browser, **NOT INSTALLED** | Research/build/pin version then test project round-trip |
| Pixel sprites | Piskel | Browser, 18767, installed | Pin upstream source SHA |
| Vector / Flash-style animation | Onionskyn | Browser, 18771, **CI-built; deployment pending**, very young 2026 beta | Pin SHA; user export/import round-trip required before relying on it |
| Painting and frame-by-frame raster animation | Krita | Native Linux **NOT INSTALLED** | Pin known-good desktop release; test latency/pen support |
| 3D modeling and texture/game assets | Blockbench | Browser, 18770, installed | Pin upstream source SHA |
| Storyboards, scene blocking/camera previs | CozyClay | Static browser, 18769/app/, installed, AI/motion sidecars deliberately disabled | Pin upstream source SHA; treat as experimental tool |
| 2D/3D game development | Godot | Native Linux **NOT INSTALLED** | Pin stable release; keep project files/backups on shared server storage |

## Deliberately excluded from v1

- **Celstomp**: strong raster frame-by-frame timeline and pressure brushes, but primarily duplicates Krita's role and doesn't provide Onionskyn's vector symbols, tweens or Flash-like project workflow.
- **Wick Editor**: historical Flash-style tool with older upstream code/build dependencies (last main commit 2021). Does not justify a second vector animation editor.
- **OpenToonz/Tahoma2D/Blender**: potentially valuable later, but outside v1; only add when a concrete use case survives a separate test.
- **Bruiser AI**: separate service, NOT a component of Studio or Now.
- **Server administration**: independent of these creative apps; Now's core remains gaming/media launching only.

## Persistence is the highest-priority gap

Only the Synth currently has a server-side project save API. Serving a browser app from OptiPlex does **not** mean files are saved on the server. Each browser editor needs file export/import testing and eventually a common authenticated project folder/API. Native Godot/Krita work must live on durable OptiPlex storage with snapshots/backups, not inside ephemeral Wolf containers. Avoid in-browser autosave as the single source of truth.

## Remote design

- Browser apps execute drawing and rendering on **the client machine**, not on the OptiPlex. They are well suited to low-latency mouse/vector work at the mall.
- Godot and Krita are native editors. Wolf runs **isolated disposable app containers**; installing Krita only on the host does not make it appear inside Wolf. Inspect existing config, then use a **separate dedicated Studio container or carefully selected remote method**, with persistent bind-mounted project storage. No changes to the working gaming profile.
- Remote pen/mouse strokes streamed via Moonlight incur network + capture/encode/decode latency. Test under actual mall network conditions before promising that full Krita drawing is comfortable. For serious pen work, local editor + later sync may outperform streaming.
- HTTPS/domain records and per-app Caddy routes must be configured and verified. The separate Studio DNS may be missing.

## Reliability / freeze policy

1. No `latest` tags, unpinned upstream source, Watchtower or unattended feature upgrades for Studio/Now.
2. Run build/test/HTTP smoke checks before any deployment. Record deployed git commit and image IDs.
3. Restart failed containers; add health checks and alerting. Keep resource budgets, so creating art can't starve the gaming encoder.
4. Schedule verified backups of project data and a restore test before depending on central storage.
5. Preserve Caddyfile and database backups before route/schema changes. Never overwrite the existing Studio named volume.
6. Dedicated Studio repository is **planned, not yet created**; keep this branch separate until extraction.
7. Don't claim the suite is production-locked until persistence, stable native editor isolation, and remote browser access are verified.

## Pinned browser-app upstream source versions

- AudioMass `21f5ee1362a47be6f0dbe6e4969a15e43d21b044`
- Piskel `bef52beb312e771bf0cbb915d873e8d638842d7a`
- CozyClay `1738d7f8ed8fe4c4ffdc9c6d97bc25792512f763`
- Blockbench `7c92e27d237e365110030d73e92c5d1605f0d311`
- Onionskyn `df36837a6bd48763fa1806ce4d24040821470d3c`
- Studio Synth UltraBox `0ba53c39b086231ebd92bb055cb1edb5d2630b60`

**Freeze condition:** New applications must replace an existing role or address a documented missing workflow. No feature creep while hardening the foundation.
