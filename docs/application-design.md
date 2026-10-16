# Application structure and optional services

Status: design baseline for draft 1.12.0, 2026-10-16. This document distinguishes implemented behavior from proposals.

## Scope

OptiPlex Now is a personal Linux client to launch, access and maintain services on a home server. It is not a Docker control panel and does not need an icon for every running container.

**Primary actions** stay visible and fast: Games (native Moonlight), Videos, Music, Files, Downloads, Terminal, Desktop and Web Gaming (MoonlightWeb). Service maintenance, SSH pairing, Web Gaming Admin, backup and machine diagnostics belong in Settings or dedicated setup dialogs. The app must not silently change the server just because a client connects.

**Optional applications** go inside the collapsed Additional Services section, not a ninth primary tile. Removing one server component must not break the launcher or the core streaming flow. Store per-service URLs as configuration, not compiled host/IP constants. Browsers handle their own sessions. Exported non-secret connection presets may carry clean URLs, but never tokens/passwords.

## Tray and dashboard rules

- Every optional **Additional Services** entry must have its own Settings → Tray Menu Shortcuts checkbox. Turning one on adds its direct shortcut; turning it off removes that entry without affecting other options.
- The existing eight main actions keep their established tray selection behavior. The draft 1.12.0 adds a ninth **Bruiser AI** checkbox, off by default; existing `tray_buttons=255` remains valid.
- New optional services such as Studio must implement the same opt-in tray behavior before being added. No optional service should be automatically pinned to the tray just because it is installed server-side.
- Proposed later dashboard cleanup, **not implemented**: preserve one-click routes to native Moonlight and Web Gaming as a paired Play/Games group; keep Videos, Music, Files and Desktop prominent. Move lower-frequency Downloads into configurable Additional Services; keep Terminal, pairing, power actions and recovery under Manage Server. Let a user pin favorite optional services to the main dashboard rather than growing a fixed set of tiles.
- Don't remove existing direct actions in a patch release without a migration and live usability tests, particularly on 1024×768 projector output.

## Studio references and microphone sampling

Possible implementation references (not audited or integrated): [VAST G1-J8](https://github.com/status201/vast-websynth) offers a synth, melodic/drum sequencers, microphone-to-sampler recording, stutter and tape stop; [mloop](https://github.com/gdamdam/mloop) offers mic/line-in loop recording, pads, step sequencing, reverse and tape degradation; BeepBox/JummBox are mature examples of low-friction pattern composition but lack the same direct recorded-sample workflow.

Pick-up-and-play goal: preset or demo song plays immediately; 16-step hardware-style flow; record a sound from local mic in one deliberate action, trim and assign it to a pad/step, add retrigger/stutter and tape delay/stop. Avoid opening a DAW-sized panel on launch. Sample playback and Web Audio synthesis run locally in the client browser; server persistence must separately sync patterns **and the referenced audio samples**, with authentication, versioning and backup. Browser mic permission requires a secure origin (e.g., HTTPS with trusted certificate, or localhost), not an insecure remote LAN URL.

## Bruiser AI

Operational on the reference OptiPlex according to the owner. The previously configured Bruiser architecture was **Open WebUI on host port 3000**, **Ollama system service on port 11434** (Open WebUI Docker link: `http://host.docker.internal:11434`), and **SearXNG in Docker on port 8080** (Open WebUI container lookup: `http://searxng:8080`). The client only needs Open WebUI. The October 16 Docker snapshot confirmed Open WebUI and SearXNG running; it did **not** re-verify Docker port publication, Ollama, user admin rights or the selected active model. Historical configuration used quantized Qwen3.5 9B with mixed GPU/CPU offload; do not assume it is the present loaded model.

Draft 1.12.0 includes a **Bruiser AI** browser shortcut under Additional Services and a **Bruiser AI Admin** button in Settings. Both derive the default Open WebUI base URL from the selected client server host as `http://SERVER:3000`; Settings `ai_url` explicitly overrides that address. Admin opens `/admin/settings` on the *same origin* and requires the current Open WebUI administrator account. Neither action bypasses login or exposes admin APIs. The URL is included in newly exported v2 `.onp` presets if overridden, and in encrypted `.onb` config snapshots; v1 presets continue to import. Older 1.11.9 clients do not recognize new v2 preset keys.

The launcher does **not** install, start, configure or update AI containers, reserve GPU memory, or manage model lifetimes. The default port must be verified on the user's current server; if the site is bound only to loopback or a different port, configure a reachable Tailscale/private URL. Do not expose unauthenticated Ollama or SearXNG endpoints to the public Internet.

Keep inference policies separate from launcher code. On RTX 3050 6 GB, a quantized small model may run; concurrent Wolf gaming and model GPU memory allocation can interfere. Prefer on-demand model loading/unloading, not a permanently resident model by default. Any GPU coordination needs actual measurements before automation.

## Candidate source and visual customization

**VAST G1-J8** ([source](https://github.com/status201/vast-websynth)): Strongest synth-first match. TypeScript + Vite/Web Audio, modular UI code. `src/styles/theme.css` centralizes palette variables; `src/styles/layout.css` and `src/ui/styles/*.module.css` control the layout and panels. **Forking and editing the presentation is feasible.** There is no guarantee an unmodified version supports every desired page/step size or a unified theme preference switch. Its native storage and exports do not automatically synchronize samples across the user's devices. GitHub marks the project MIT; verify exact upstream attribution/license terms (and third-party dependencies) before distributing a modified build.

**mloop** ([source](https://github.com/gdamdam/mloop)): React/Vite/Web Audio focused on sampling and looping. Native 8/16/32/64-step sequencing, mic recording, effects, local IndexedDB sessions. UI and CSS are editable, but remixing it into a synth-first instrument would be a larger rewrite than styling VAST. Licensed AGPL-3.0-or-later; a modified hosted service needs license/source-availability compliance and cannot reuse the original branding without permission.

**BeepBox / BassoonTracker:** easier to host or skin to varying degrees, but their core interaction models are more constrained for the requested DS-10-style subtractive synth, microphone sampler, and live FX.

**Visual direction after owner feedback:** trim the dramatic sunset aesthetic. Use neutral graphite surfaces, high-contrast light text, a **single** muted coral highlight for armed/active states, light rules rather than nested outlined boxes, no heavy gradients, woodgrain, chrome, glows or background texture. Period cues should come from restrained typography and hardware-function labeling. Do not base the final Studio UI on the generated mockup; treat it as exploratory. CSS styling is straightforward; reorganizing VAST's UI still requires code changes, accessibility and responsive testing.

## Future module: Studio (not implemented)

Consider an optional browser-hosted MIDI step sequencer and synthesizer:

- Client: **synth-first** 16-step default with user-selectable **8, 16, 24 or 32 steps per track**, controlled as one to four active 8-step pages; additional pages can be enabled/disabled without discarding their pattern content. Provide per-lane lengths for polyrhythms; 8–32 step range is a Studio product requirement, not a claim about an existing fork. Two playable subtractive/chiptune synths, one drum instrument and a simple optional microphone sampler, swing, pattern chaining, MIDI export.
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
