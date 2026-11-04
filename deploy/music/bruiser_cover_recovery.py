"""Bruiser-owned cover recovery for DroppedNeedle's synthetic local album IDs.

Installed in a versioned derived host image. The caller must already have
authenticated via DroppedNeedle's OpenSubsonic route and proved the album is
in that user's library. This is read-only for music files/tags and uses only
the server's existing MusicBrainz and cover-art repositories.
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
import uuid

LOG = logging.getLogger(__name__)
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
_SEMAPHORE = asyncio.Semaphore(2)
_LOCKS: dict[str, asyncio.Lock] = {}


def is_local_album_id(value: str) -> bool:
    """Library indexer/grouping generate UUIDv5 local IDs, not real MBIDs."""
    try:
        return uuid.UUID(str(value)).version == 5
    except (ValueError, AttributeError, TypeError):
        return False


def folded(value: object) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def verified_release_group(album: object, results: object) -> str | None:
    """Return a single unambiguous release-group identity, never a guess.

    Strict normalized title and artist must match. Year must match whenever
    the locally indexed album has one. Alternative editions/compilations
    with distinct identities are held rather than attaching wrong cover art.
    """
    title = folded(getattr(album, "title", None))
    artist = folded(getattr(album, "artist_name", None))
    year = getattr(album, "year", None)
    if not title or not artist or not isinstance(results, list):
        return None
    matches: set[str] = set()
    for result in results[:15]:
        candidate_id = getattr(result, "musicbrainz_id", None)
        if not isinstance(candidate_id, str):
            continue
        try:
            parsed = uuid.UUID(candidate_id)
        except ValueError:
            continue
        if parsed.version == 5:
            continue
        if folded(getattr(result, "title", None)) != title:
            continue
        if folded(getattr(result, "artist", None)) != artist:
            continue
        candidate_year = getattr(result, "year", None)
        if isinstance(year, int) and year > 0:
            if not isinstance(candidate_year, int) or candidate_year != year:
                continue
        matches.add(str(parsed))
    return next(iter(matches)) if len(matches) == 1 else None


def valid_image(value: object) -> bool:
    if not isinstance(value, tuple) or len(value) != 3:
        return False
    data, mime, _source = value
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_IMAGE_BYTES:
        return False
    if mime not in MIME_TYPES:
        return False
    # Verify raster magic bytes; a remote SVG disguised as JPEG is not safe.
    if mime == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


async def recover_album_cover(
    services: object,
    album: object,
    album_id: str,
    size: str,
    *,
    mb_repository: object | None = None,
    priority: object | None = None,
) -> tuple[bytes, str, str] | None:
    """Local cover first, then a strictly verified MusicBrainz match.

    Positive matches are stored in DroppedNeedle's existing mounted
    disk-cache under the *local album ID*, so they survive image recreation,
    server restarts and provider outages. Misses get a bounded TTL.
    """
    if not is_local_album_id(album_id):
        return None
    cover = services.coverart
    disk = cover.disk_cache
    cache_file = disk.get_file_path("rg_" + album_id, size)
    lock = _LOCKS.setdefault(album_id + ":" + size, asyncio.Lock())

    async with lock:
        # Cached verified results, including art from a prior process, win.
        cached = await disk.read(cache_file, ["source"])
        if cached is not None:
            data, mime, meta = cached
            source = (meta or {}).get("source", "disk-cache")
            result = (data, mime, source)
            if valid_image(result):
                return result

        # A locally held folder.jpg or embedded image is authoritative,
        # even if a negative cache marker exists from earlier scans.
        try:
            local = await asyncio.wait_for(
                cover._local_album_cover(album_id, cache_file), timeout=4
            )
            if valid_image(local):
                return local
        except (OSError, asyncio.TimeoutError, RuntimeError):
            LOG.debug("Local cover not ready for a synthetic album")

        if await disk.is_negative(cache_file):
            return None
        if not folded(getattr(album, "title", None)) or not folded(
            getattr(album, "artist_name", None)
        ):
            await disk.write_negative(cache_file, ttl_seconds=6 * 3600)
            return None
        if mb_repository is None:
            from core.dependencies import get_musicbrainz_repository
            mb_repository = get_musicbrainz_repository()
        if priority is None:
            from infrastructure.queue.priority_queue import RequestPriority
            priority = RequestPriority.BACKGROUND_SYNC

        try:
            async with _SEMAPHORE:
                return await asyncio.wait_for(
                    _remote_cover(
                        cover, disk, cache_file, album, size,
                        mb_repository, priority
                    ),
                    timeout=19,
                )
        except asyncio.TimeoutError:
            # Providers or overloaded hardware may be temporarily slow.
            await disk.write_negative(cache_file, ttl_seconds=5 * 60)
        except Exception:
            # Always fail closed: never break audio or leak network details
            # through the authenticated OpenSubsonic response.
            LOG.warning("Automatic album-cover lookup failed; will retry")
            await disk.write_negative(cache_file, ttl_seconds=5 * 60)
        return None


async def _remote_cover(
    cover: object, disk: object, cache_file: object, album: object,
    size: str, mb_repository: object, priority: object,
) -> tuple[bytes, str, str] | None:
    results = await mb_repository.search_release_groups(
        album.artist_name,
        album.title,
        limit=10,
        include_all_types=True,
        priority=priority,
    )
    mbid = verified_release_group(album, results)
    if not mbid:
        # No match and ambiguous match both fail closed. Periodically retry
        # in case library metadata or the online catalog improves.
        await disk.write_negative(cache_file, ttl_seconds=6 * 3600)
        return None
    image = await cover.get_release_group_cover(
        mbid, size, priority=priority
    )
    if not valid_image(image):
        # CAA may be warming or unavailable. Do not permanently bank "no art".
        await disk.write_negative(cache_file, ttl_seconds=5 * 60)
        return None
    data, mime, _provenance = image
    await disk.write(
        cache_file, data, mime,
        {"source": "bruiser-verified-musicbrainz", "matched_mbid": mbid},
        is_monitored=True,
    )
    return data, mime, "bruiser-verified-musicbrainz"
