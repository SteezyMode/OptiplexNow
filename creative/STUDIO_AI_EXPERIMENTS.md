# Studio AI experiments — design notes (2026-10-16)

**Status: proposed, NOT installed or integrated.** Core Studio v1 app selection remains frozen in `STUDIO_V1_LOCK.md`. Bruiser AI stays a separately operated optional service; neither Studio nor OptiPlex Now should require it.

## Goal

Give Bruiser an opt-in, project-aware assistant role across the Studio suite (especially native Godot), and enable optional Suno-like local audio generation without breaking gaming/video encoding or overloading the RTX 3050 LP 6 GB, power-capped to 55 W.

## Existing Bruiser architecture

Prior testing used Ollama/Open WebUI and Qwen3.5 9B IQ4_XS / 8K context. Verify actual current backend and Open WebUI version on the OptiPlex before connecting anything. Open WebUI >=0.6.31 supports native Streamable HTTP MCP; stdio MCP servers typically require an MCPO proxy or carefully configured bridge. Tool-call capability and accuracy depend strongly on the LLM; Qwen 9B must pass tests before enabling editing tools.

## Godot integration: priority 1

- Investigate https://github.com/YasiruRF/godot-mcp : reads/scripts/files, headless validation, optional live-editor bridge; states tested against Godot **4.7.2**, installed in our pinned Wolf Studio image. Alternative https://github.com/NPGameDev/godot-mcp-toolkit with editor dock.
- Start **read-only**: list approved projects, read scenes and GDScript files, gather Godot log/errors, search version-matched API docs.
- Phase 2: **propose patch** and show diff, require explicit confirmation, create git commit/backup first; validate via headless Godot in isolated workspace before accepting.
- Phase 3: optionally connect live-editor bridge on **localhost only**. Some bridges bind unauthenticated 127.0.0.1 WebSockets; never publish this through Caddy or Tailscale Serve. Any local code may reach localhost in same network namespace; inspect threat model and prefer bridge with authentication or process isolation.
- Do not grant generic shell access, unrestricted project directory access, Docker socket, game libraries, full home, or the ability to modify Wolf/Caddy/network settings.
- Pilot one disposable Godot project with full restoration test; backup and verify project folder access in the Studio container first.

## Knowledge pack

- Retrieval from pinned **Godot 4.7**, **Krita 5.3**, **Blockbench**, **Piskel**, **Onionskyn**, **UltraBox Studio Synth**, **openDAW**, **AudioMass**, and **CozyClay** docs. Pin docs/version and cite snippets in answers.
- Good at explaining workflows, existing project structure, errors, transforming asset names/metadata, scripting and audio prompts. Poorly supported as a universal GUI automation controller; each app requires real documented hooks and a tested permission surface.
- Krita Python plugin API and Blockbench JavaScript plugin API might offer bridges later but are **not validated**. Browser apps only get explicit import/export workflows until a secure API is actually built. Serving a browser app from server does not put its in-browser project data on the server.

## Local music generation: priority 2 / opt-in GPU worker

**Preferred candidate:** https://github.com/ace-step/ACE-Step-1.5 (MIT; verify model weight restrictions). Source docs:
- https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/GPU_COMPATIBILITY.md
- https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/API.md
- https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/ace_step_musicians_guide.md

Features reported upstream: text-to-music with vocals/lyrics, instrumentals, remix, reference audio, repaint specific region, extended layering and extraction in non-turbo variants. API has queue/task IDs, async polling, and WAV/MP3/FLAC output. Do not call every advanced feature available in low-memory turbo mode without testing.

Memory: documented low-VRAM modes using INT8/CPU and DiT offloading. RTX 3050 LP has nominal 6GB VRAM but only 55 W cap and is also Wolf/NVENC server GPU. Do not extrapolate RTX3090 benchmark speed to this machine. At <=6GB docs recommend DiT-only model (LM disabled); Bruiser can generate **text prompts and lyric structures** separately rather than loading ACE's own LM. Disable GPU generation while interactive streaming is active; serialize queue max 1, with idle unload, timeouts, resource and storage quotas. Protect local API with auth; do not expose raw Gradio/API externally. Budget ~10GB+ for core model downloads plus generation artifacts; storage files on StudioProjects and backups.

Alternatives / rationale:
- https://github.com/facebookresearch/audiocraft MusicGen-small: accessible short instrumentals; less Suno-like. Larger MusicGen models recommend 16GB VRAM.
- https://github.com/HeartMuLa/heartlib HeartMuLa: normal pipeline ~10–12GB VRAM; 8GB lazy-loading is documented, not a comfortable 6GB target.
- https://github.com/ASLP-lab/DiffRhythm: reports >=8GB VRAM for base model.
- https://github.com/multimodal-art-projection/YuE: much larger footprint / slow on current hardware.
- Cloud-backed API option only if user explicitly wants recurring cost and privacy tradeoff.

## Intended workflow

1. User prompts Studio Music AI (e.g. '90s-style survival horror save-room theme, low strings, 72 BPM, instrumental, 30s').
2. Bruiser (or a thin deterministic app endpoint) formats captions / lyrics / duration.
3. A **single optional** ACE-Step job is enqueued when server has GPU capacity.
4. Job emits one or more real audio files, metadata, model version, settings and seed to `/home/optiplex/StudioProjects/Exports/`.
5. Studio provides playback, download and import into AudioMass / openDAW. A WAV is **not** automatically editable MIDI or synth notes: instrument separation and note transcription are separate tasks with imperfect fidelity.
6. Exports remain independent of Bruiser so the Studio suite operates normally if AI is offline.

## Acceptance tests (before calling it integrated)

- Browser/SSH/game streaming all stay functional when AI is stopped or crashes.
- Image retains editable Godot/Krita after a session disconnect; project save/load roundtrip with correct file ownership and backup restore.
- Bruiser can correctly inspect and diagnose a sample Godot project using local docs and read-only tools.
- One reversible code/scene edit passes Godot headless validation, review and rollback.
- ACE-Step starts **on demand**, outputs a valid audio file, records generation time/peak VRAM/RAM/GPU power, saves to persistent location, stops/unloads fully, does not crash Wolf or stall NVENC during gaming.
- No unprotected public endpoints, no raw full server access, no unauthorized file edits.

**No user-facing app changes or production configuration changes are made by this design document.**
