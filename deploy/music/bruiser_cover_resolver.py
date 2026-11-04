"""Conservative, persistent cover resolution for MusicBrainz-ID-less local albums.

This is an OptiPlex/Bruiser host-side compatibility fallback, NOT a tag writer.
DroppedNeedle's native scanner uses UUIDv5 for local album identities while
Cover Art Archive expects a genuine MusicBrainz release-group MBID. Looking
up cover art by an unrelated UUIDv5 cannot succeed remotely.

The normal local-art and genuine MBID paths retain priority. When those miss,
a candidate may be accepted only when both artist and album title normalize
exactly, the release year agrees (when known), and a unique MB release-group
identity is returned. All decisions are persisted in the existing /app/cache
Docker volume; no audio files or library records are modified.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import unicodedata
import uuid

CACHE_ROOT = Path("/app/cache/bruiser-cover-mappings-v1")
CACHE_VERSION = 1
POSITIVE_TTL = 30 * 86400
NEGATIVE_TTL = 30 * 60
SEARCH_TIMEOUT_SECONDS = 10
IMAGE_TIMEOUT_SECONDS = 15
MAX_CACHE_BYTES = 2048
# Successful images are cached independently in native CoverArtRepository.
MAX_CONCURRENT_LOOKUPS = 2

_semaphore: asyncio.Semaphore | None = None


def _sem() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_LOOKUPS)
    return _semaphore


def synthetic_album_id(value: object) -> bool:
    """A synthetic local UUIDv5 is not a remote MusicBrainz release-group ID."""
    if not isinstance(value, str):
        return False
    try:
        parsed = uuid.UUID(value)
        return str(parsed) == value.lower() and parsed.version == 5
    except (ValueError, AttributeError, TypeError):
        return False


def _normalize(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def _year(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value if 1900 <= value <= 2100 else None
    if isinstance(value, str) and re.match(r"^\d{4}(?:\D|$)", value):
        year = int(value[:4])
        return year if 1900 <= year <= 2100 else None
    return None


def _attr(value: object, key: str) -> object:
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def _valid_rg(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        candidate = uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return str(candidate) == value.lower() and candidate.version == 4


def pick_verified_release_group(
    candidates: object, title: str, artist: str, year: int | None
) -> str | None:
    """No fuzzy title-only cover assignment. Reject ambiguous real MBIDs."""
    wanted_title = _normalize(title)
    wanted_artist = _normalize(artist)
    if not wanted_title or not wanted_artist or not isinstance(candidates, list):
        return None
    matches: set[str] = set()
    for item in candidates[:25]:
        album_name = _normalize(_attr(item, "title"))
        artist_name = _normalize(_attr(item, "artist"))
        mbid = _attr(item, "musicbrainz_id")
        if album_name != wanted_title or artist_name != wanted_artist:
            continue
        if not _valid_rg(mbid):
            continue
        candidate_year = _year(_attr(item, "year"))
        # When the local album has a known year, require it to corroborate the
        # provider's release year. One year tolerance accommodates metadata
        # regional/early-release differences; unknown years are not evidence.
        if year is not None and (
            candidate_year is None or abs(candidate_year - year) > 1
        ):
            continue
        matches.add(mbid.lower())
        if len(matches) > 1:
            return None
    return next(iter(matches)) if len(matches) == 1 else None


def _cache_path(local_id: str, title: str, artist: str, year: int | None) -> Path:
    material = json.dumps([CACHE_VERSION, local_id, _normalize(title),
                           _normalize(artist), year], separators=(",", ":"))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return CACHE_ROOT / (digest + ".json")


def _read_cache(path: Path) -> tuple[bool, str | None]:
    try:
        if not path.is_file() or path.stat().st_size > MAX_CACHE_BYTES:
            return False, None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != CACHE_VERSION:
            return False, None
        if float(data.get("expires", 0)) <= time.time():
            return False, None
        mbid = data.get("mbid")
        return (True, mbid if _valid_rg(mbid) else None)
    except (OSError, ValueError, TypeError, AttributeError):
        return False, None


def _write_cache(path: Path, mbid: str | None) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        duration = POSITIVE_TTL if mbid else NEGATIVE_TTL
        data = json.dumps({"version": CACHE_VERSION,
                           "expires": time.time() + duration,
                           "mbid": mbid})
        fd, temp = tempfile.mkstemp(prefix=".mapping-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                os.fchmod(handle.fileno(), 0o600)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    except OSError:
        # Persistent caching failure must not stop music playback.
        return


async def missing_album_cover(
    album: object, local_id: str, coverart: object, size: str,
    is_disconnected: object = None,
) -> tuple[bytes, str, str] | None:
    """Resolve a single known-library, synthetic-ID album only on cover miss.

    No background crawler, tag rewriting, downloading audio, or invented MBID.
    MusicBrainz requests use DroppedNeedle's existing bounded repository.
    """
    if not synthetic_album_id(local_id):
        return None

    title = _attr(album, "title")
    artist = _attr(album, "artist_name")
    year = _year(_attr(album, "year")) or _year(
        _attr(album, "original_release_date")
    )
    if not isinstance(title, str) or not isinstance(artist, str):
        return None
    if not _normalize(title) or not _normalize(artist):
        return None

    path = _cache_path(local_id, title, artist, year)
    async with _sem():
        # A projected canonical ID is authoritative; UUIDv5 is never.
        projected = _attr(album, "musicbrainz_release_group_id")
        if _valid_rg(projected):
            mbid = projected.lower()
            found = True
        else:
            found, mbid = await asyncio.to_thread(_read_cache, path)
        if found and not mbid:
            return None
        if not found:
            try:
                # Resolve lazily, and never bypass the existing provider rate
                # limits, circuit breaker or MusicBrainz caches.
                from core.dependencies.repo_providers import get_musicbrainz_repository
                from infrastructure.queue.priority_queue import RequestPriority

                repository = get_musicbrainz_repository()
                candidates = await asyncio.wait_for(
                    repository.search_release_groups(
                        artist, title, limit=15, include_all_types=True,
                        priority=RequestPriority.IMAGE_FETCH,
                    ), timeout=SEARCH_TIMEOUT_SECONDS
                )
                mbid = pick_verified_release_group(candidates, title, artist, year)
                # A blank repository response can also be an upstream outage:
                # never poison the persistent mapping cache on empty search.
                if candidates:
                    await asyncio.to_thread(_write_cache, path, mbid)
            except Exception:
                # A provider outage is not proof no cover exists: do NOT
                # record a negative cache entry.
                return None
        if not mbid:
            return None
        try:
            result = await asyncio.wait_for(
                coverart.get_release_group_cover(
                    mbid, size, is_disconnected=is_disconnected
                ), timeout=IMAGE_TIMEOUT_SECONDS
            )
            return result
        except Exception:
            return None
