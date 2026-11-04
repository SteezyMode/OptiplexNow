# Automatic library artwork recovery (Bruiser host)

## Purpose

DroppedNeedle v2.15.0's OpenSubsonic `getCoverArt` tries release-group cover
resolution for the locally indexed album ID. Albums with no verified MusicBrainz
release-group identifier get a **synthetic UUIDv5**, so remote cover providers
can't resolve them by that key. Examples include:

- Circa Survive — **Blue Sky Noise** (2010)
- Kid Cudi — **Man on the Moon: The End of Day** (2009)

This is a server-side fix for **any** locally indexed synthetic album, not a
one-time script adding a few covers. Music files, tags, library folder layout,
and all acquisition settings remain untouched.

## How it works

The authenticated OpenSubsonic cover route recognizes local UUIDv5 album IDs.
It checks Bruiser's persistent isolated album-art disk cache first, then the
original local cover extractor (folder art and embedded audio art). Only after
both miss does it ask the already-configured MusicBrainz repository to look up
the album using artist + title + year. It requires exactly **one unambiguous
candidate** with exact normalized artist and title, and matching year when
known. The resulting release-group ID, not the synthetic UUID, is passed into
DroppedNeedle's existing album-art fetcher. Raster bytes (no SVG) are saved
under the original local album ID using the existing `/app/cache` mounted
volume, marked as monitored, and served again offline. Failed or ambiguous
matches negative-cache for a bounded period, not indefinitely. Local art
always wins. Only two remote lookups can run at once; the network request is
bounded by a timeout.

The background/optional-work Discover budget correction remains intact.

## Deployment on an existing Bruiser host

Prerequisite: the existing permanent Discover image must already be installed,
and running from `~/music-vpn/compose.json`. The new installer refuses to
modify other deployments. The two files must be in the same host directory:

```
python3 install_album_art_recovery.py
```

The script builds a versioned Docker image FROM the exact currently-running
Discover-patched image (not `:latest`), changes only the cover route and the
new helper, saves the original Compose file and router plus image manifest
under `~/bruiser-repairs/album-art-persistent-.../`, then recreates **only**
DroppedNeedle. Docker mount fingerprints and service health are checked.
If deployment fails, Compose and DroppedNeedle are restored automatically.

Survives ordinary container restarts, recreation and unrelated image updates.
Future DroppedNeedle upgrades should be intentionally rebased and tested against
this patch rather than pulling over it.

## Acceptance

After deployment, open Music → Library and check the named albums. The first
cover access may take seconds because it asks MusicBrainz/CAA; if a provider is
warming or offline, revisit later. Previously cached verified covers stay
available offline. Confirm library music still plays, Discover recommendations
still populate, and restart/recreation preserves the covers. Any ambiguous
match remains an honest placeholder rather than guessed art.

**Important:** This fix cannot manufacture art when there is no embedded or
folder image and remote providers lack a safe, unambiguous release-group match.
Keep reporting such albums for manual review; do not force a wrong cover.
