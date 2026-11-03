# Bilingual Jellyfin subtitles — isolated SubDuet pilot

**Status:** Optional post-Private-Alpha-1 experiment. Not installed on reference host, not in the published .deb, and not accepted via real Jellyfin playback.

## Purpose

Enable English and Japanese subtitles together for a multilingual household, while leaving Jellyfin as the player and keeping the original movie untouched. Use [SubDuet](https://github.com/NLINEA/SubDuet) (MIT, beta) as an upstream generator of ordinary `Movie.mul.srt` sidecars. Jellyfin supports ordinary external subtitles. No custom browser player, expanded host admin role or new streaming protocol is needed.

The initial pilot deliberately uses only two existing English and Japanese SRT sidecars. Translation, transcription, automatic subtitle download and audio-based sync are **disabled**. There is no API key, Jellyfin admin token, Caddy change, public port or VPN dependency. German, Spanish and other non-English films can be paired when both subtitle translations are already available; the pilot does not identify the film's spoken language.

## Safe first test

On an OS-ready Linux device with Docker Compose and Git, copy a movie and both matching sidecars into a disposable directory **separate from the live Jellyfin library**, e.g.:

```text
~/dual-subtitle-test/
  Sample Movie.mkv
  Sample Movie.en.srt
  Sample Movie.ja.srt
```

From the repository checkout:

```sh
python3 tools/bilingual_subtitles_pilot.py prepare --media-root "$HOME/dual-subtitle-test"
```

This makes a dedicated private workspace at `~/.local/share/bilingual-subtitles-pilot`, but **does not install or start anything**. Review its `compose.yaml` and secret-bearing `paircue.env` locally. Do not share the environment file or token.

Then, only after reviewing:

```sh
python3 tools/bilingual_subtitles_pilot.py start
```

The pilot fetches upstream pinned tag `v0.1.0b15`, builds locally, runs `subduet doctor`, and starts a separate Compose project on loopback port `9294` with dropped capabilities, read-only container root, non-root UID and only the **selected test folder** mounted read/write. No Jellyfin container is restarted or reconfigured.

Inspect `Sample Movie.mul.srt` in the copied directory. Validate both languages, ordering, synchronization, no missing lines, and text size. Absence of output or a review warning is not success. To check or stop:

```sh
python3 tools/bilingual_subtitles_pilot.py status
python3 tools/bilingual_subtitles_pilot.py stop
```

Stopping preserves the test directory and state. It never deletes source videos, subtitles, or the generated `.mul.srt`.

When a copied film passes, the owner may **separately, deliberately** copy that new bilingual sidecar beside the real video and refresh Jellyfin metadata if needed, then select it as the subtitle track. The pilot never copies into or scans the live Jellyfin library automatically.

## Limits and next steps

- This pilot requires **both SRT sidecars**. Missing Japanese subtitles require optional provider-backed translation or subtitle search in a future explicitly approved phase.
- Embedded PGS/VobSub/ASS extraction, remote Jellyfin discovery, provider credentials, and library-wide automation are not implemented in NOW by this experiment. SubDuet can support more complex flows, but each needs separate compatibility and privacy testing.
- A `.mul.srt` can render on multiple Jellyfin clients, but appearance, forced subtitle selection, playback fallback and Japanese font legibility need physical tests, especially on the 1024×768 projector.
- The source is built from a pinned beta tag, not a verified reproducible binary. Review upstream security and dependency changes before a production deployment.
- Future NOW `Videos → Bilingual subtitles` should be an owner-authorized setting that selects EN+JA, reports availability/preparation status and leaves movie playback and Jellyfin authentication upstream. Never provide ordinary NOW clients unrestricted Docker, media paths, or Jellyfin admin credentials.
- Keep this entirely outside the Private Alpha 1 release gate.

## Testing

```sh
python3 -m unittest discover -s tests -p "test_bilingual_subtitles_pilot.py" -v
```

The tests cover offline configuration, permission restrictions and refusal to overwrite the workspace. They are not real Docker, upstream or Jellyfin playback tests.

References: [SubDuet configuration](https://github.com/NLINEA/SubDuet/blob/main/docs/CONFIGURATION.md), [Docker guide](https://github.com/NLINEA/SubDuet/blob/main/docs/DOCKER.md), [Jellyfin external subtitle naming](https://jellyfin.org/docs/general/server/media/movies/).
