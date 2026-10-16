# Studio — UltraBox-based instrument

**Development branch only. No changes to the running OptiPlex.**

Studio is a self-hosted browser synthesizer built on a *pinned* MIT-licensed
UltraBox commit: 0ba53c39b086231ebd92bb055cb1edb5d2630b60.
UltraBox builds on JummBox and BeepBox. Original code, license and credits
remain attributed. Its original synth engine and piano roll are not replaced.

## First version

- The complete UltraBox synthesis and piano-roll experience.
- STUDIO / STEPS & PERFORMANCE expander, with 8, 16, 24, or 32 16th-note
  steps. The grid directly edits notes on the selected UltraBox channel/bar.
  The grid extends across adjacent bars for steps longer than a single bar.
  It is intentionally conservative around complex or held notes.
- Twelve drum rows, or eight semitones starting from an adjustable base pitch.
- XY performance controller for the current instrument's filter cutoff and
  echo level. Use UltraBox's effect controls to enable these effects.
  By default changes are momentary; Keep persists one finished gesture.
- Central song library with name, manual Save, Save As, Load, revision checks
  and SQLite storage; a bearer token is required. The token stays in
  browser sessionStorage (not in the URL or repository).

NOT IMPLEMENTED YET: beat-repeat/stutter engine, tape stop DSP, microphone
sample uploader, automatic song synchronization, detailed revision history UI,
and automatic deployment. Custom sample audio is not yet stored in the database.
This is not a complete DAW or a released product.

## Local Docker test

Run inside the studio directory on a host with working GitHub/npm access.

1. Copy .env.example to .env.
2. Generate a secret using: python3 -c 'import secrets;print(secrets.token_urlsafe(48))'
3. Put it in .env as STUDIO_API_TOKEN. Do not commit .env.
4. Run: docker compose build
5. Run: docker compose up -d

A private host-only port 127.0.0.1:18765 will serve Studio.
Check: curl http://127.0.0.1:18765/api/health

After testing, a separately configured Caddy HTTPS domain can proxy to
127.0.0.1:18765, for example:

    studio.monumentrisk.com {
        reverse_proxy 127.0.0.1:18765
    }

The domain is PROPOSED, NOT CURRENTLY LIVE. Private/Tailscale access or
additional proxy authentication is strongly recommended. Don't expose
the token or the service over unencrypted public HTTP.
Make encrypted backups of the persistent Docker volume studio-data.

The Studio project is separate from OPTIPLEX NOW. The launcher can later
open its HTTPS address as a standalone browser-app window (where available),
or a normal browser window. Nothing in the audio/UI should depend on GTK.

## Upstream, tests and validation

The Dockerfile downloads the pinned original upstream source during build,
injects the StudioBridge TypeScript module, builds and hosts the generated
site, and copies the upstream LICENSE.md as UPSTREAM-LICENSE.md.
We intentionally do not vendor an unreviewed mutable upstream branch.

GitHub Actions workflow studio.yml builds and tests the Docker image.
This is not proof of audio or browser correctness. Human browser/MIDI
testing must precede a deployed stable release.

Test explicitly: piano-roll notes vs Steps toggles, all 12 drum rows,
long notes, chord edits, undo/redo and playback; 32 steps across bars;
effects activated and momentary vs Keep behavior; URL song loading,
independent client project saves and 409 conflicts, sample URL loading,
offline clients, slow MacBook and Deck screen dimensions.
