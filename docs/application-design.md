# Application structure and optional services

Status: design baseline for draft 1.12.0, 2026-10-16. This document distinguishes implemented behavior from proposals.

## Scope

OptiPlex Now is a personal Linux client to launch, access and maintain services on a home server. It is not a Docker control panel and does not need an icon for every running container.

**Primary actions** stay visible and fast: Games (native Moonlight), Videos, Music, Files, Downloads, Terminal, Desktop and Web Gaming (MoonlightWeb). Service maintenance, SSH pairing, Web Gaming Admin, backup and machine diagnostics belong in Settings or dedicated setup dialogs. The app must not silently change the server just because a client connects.

**Optional applications** go inside the collapsed Additional Services section, not a ninth primary tile. Removing one server component must not break the launcher or the core streaming flow. Store per-service URLs as configuration, not compiled host/IP constants. Browsers handle their own sessions. Exported non-secret connection presets may carry clean URLs, but never tokens/passwords.

## Bruiser AI

Operational on the reference OptiPlex according to the owner. Open WebUI and SearXNG containers were observed, but the exact browser endpoint and inference backend were not inventoried.

Draft 1.12.0 includes a **Bruiser AI** browser shortcut under Additional Services, with optional `ai_url` in Settings. It opens the configured URL; it does **not** install, start, configure or update AI containers, reserve GPU memory, or manage model lifetimes. If unconfigured, it shows a settings hint instead of guessing a port. The URL is included in newly exported v2 `.onp` presets and encrypted `.onb` config snapshots; v1 presets continue to import. Older 1.11.9 clients do not recognize new v2 preset keys.

Keep inference policies separate from launcher code. On RTX 3050 6 GB, a quantized small model may run; concurrent Wolf gaming and model GPU memory allocation can interfere. Prefer on-demand model loading/unloading, not a permanently resident model by default. Any GPU coordination needs actual measurements before automation.

## Future module: Studio (not implemented)

Consider an optional browser-hosted MIDI step sequencer and synthesizer:

- Client: compact 16/32-step editor; basic synth/drum engine using Web Audio; tempo, swing, playback, pattern chaining; MIDI export.
- Server: authenticated pattern persistence and named save slots in a small database; versioned data schema and backup/restore.
- Sync: server is the source of truth across clients; expose explicit save/duplicate actions, revision counters and conflict prompts if the same pattern is edited simultaneously. Optionally add local cache and offline edits only after conflict behavior is tested.
- Playback: generate audio **on the playing client** to avoid geographical network latency. The server stores musical data, not a live audio stream.
- Hardware MIDI: optional extension dependent on browser and OS Web MIDI availability; never required for the first version.
- Security: private/Tailscale access or another authenticated endpoint, no unauthenticated public write endpoint, no GitHub-backed pattern data.
- Packaging: treat Studio as a separate service exposed under Additional Services, not part of the GTK executable. The launcher only opens it.
- Release separately with tests covering metronome timing, save/restore, schema migration, concurrent edits and fresh-client access.

No Studio server, database, authentication, pattern sync, browser UI or synthesizer has been implemented in the current release candidate.

## Boundaries and reliability

- Avoid new required client dependencies for optional services.
- Configuration remains compatible with old `config.ini` and v1 presets.
- A fresh client must restore its own private identity or pair explicitly; never bake Moonlight/SSH/MoonlightWeb credentials into public releases.
- Change production server services only with backups, explicit opt-in, tests and rollback.
- Source of truth for observed operations: [operations-handoff.md](operations-handoff.md).
