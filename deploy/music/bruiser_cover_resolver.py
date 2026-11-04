"""Conservative, persistent fallback for verified album cover IDs and editions.

This is an OptiPlex/Bruiser host-side compatibility fallback, NOT a tag writer.
DroppedNeedle's native scanner uses UUIDv5 for local album identities while
Cover Art Archive expects a genuine MusicBrainz release-group MBID. Looking
up cover art by an unrelated UUIDv5 cannot succeed remotely.

The normal local-art, native AudioDB, and release-group cover paths
retain priority. Existing v2 only helped synthetic UUIDv5 albums; when a
genuine MusicBrainz release-group had no representative front cover, v2 did
nothing. v3 also examines a bounded number of verified official *editions*
in the SAME release group, whose front art may be available independently.
No fuzzy cover assignment, new media downloads, credentials or tag edits.
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

CACHE_ROOT = Path("/app/cache/bruiser-cover-mappings-v3")
CACHE_VERSION = 3
POSITIVE_TTL = 30 * 86400
NEGATIVE_TTL = 30 * 60
SEARCH_TIMEOUT_SECONDS = 10
IMAGE_TIMEOUT_SECONDS = 12
EDITION_TIMEOUT_SECONDS = 13
MAX_EDITION_ATTEMPTS = 3
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
    # Search providers may omit accents or use compatibility forms. Compare
    # letters rather than Unicode presentation while requiring exact remaining
    # words, artist and release year for a cover assignment.
    text = unicodedata.normalize("NFKD", value).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c))
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
    # Legacy MusicBrainz release-group identifiers include UUIDv3.
    # Reject UUIDv5: that version is reserved here for synthetic local IDs.
    return str(candidate) == value.lower() and candidate.version in (3, 4)


def pick_verified_release_group(
    candidates: object, title: str, artist: str, year: int | None
) -> str | None:
    """No fuzzy title-only cover assignment. Reject ambiguous real MBIDs."""
    wanted_title = _normalize(title)
    wanted_artist = _normalize(artist)
    if not wanted_title or not wanted_artist or not isinstance(candidates, list):
        return None
    matching: dict[str, int | None] = {}
    for item in candidates[:25]:
        album_name = _normalize(_attr(item, "title"))
        artist_name = _normalize(_attr(item, "artist"))
        mbid = _attr(item, "musicbrainz_id")
        if album_name != wanted_title or artist_name != wanted_artist:
            continue
        if not _valid_rg(mbid):
            continue
        matching[mbid.lower()] = _year(_attr(item, "year"))

    # Prefer the original release year if multiple groups have exactly the
    # same artist/title. A library might tag a reissue with its reissue year:
    # when the exact artist+album identity has only ONE matching release group,
    # that unique group remains safe even if its original year differs.
    if year is not None:
        matching_year={
            key for key,value in matching.items()
            if value is not None and abs(value-year)<=1
        }
        if len(matching_year)==1:
            return next(iter(matching_year))
        if len(matching_year)>1:
            return None
    return next(iter(matching)) if len(matching)==1 else None


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


def official_edition_ids(details: object, group_id: str) -> list[str]:
    """Return up to three independently flagged front-cover editions.

    An edition must originate from the exact requested group metadata. We
    never search another artist or substitute an unrelated album. Prefer
    releases which explicitly advertise front art and are not bootlegs.
    """
    if not isinstance(details,dict) or not isinstance(details.get("releases"),list):
        return []
    metadata_id=details.get("id")
    if metadata_id and str(metadata_id).lower()!=group_id.lower():
        return []
    front=[]
    unknown=[]
    seen=set()
    for release in details["releases"][:100]:
        if not isinstance(release,dict):
            continue
        release_id=release.get("id")
        if not _valid_rg(release_id) or release_id.lower() in seen:
            continue
        seen.add(release_id.lower())
        status=release.get("status")
        if status not in ("Official",None,""):
            continue
        flag=release.get("cover-art-archive")
        if isinstance(flag,dict):
            if flag.get("front") is True:
                front.append(release_id.lower())
            # Explicitly no front art is NOT a fallback candidate.
        else:
            unknown.append(release_id.lower())
    return (front+unknown)[:MAX_EDITION_ATTEMPTS]


async def _edition_cover(
    group_id: str, coverart: object, size: str, is_disconnected: object,
) -> tuple[bytes, str, str] | None:
    """Use native cached CoverArtRepository methods; never fetch arbitrary URL."""
    from core.dependencies.repo_providers import get_musicbrainz_repository
    from infrastructure.queue.priority_queue import RequestPriority

    repository=get_musicbrainz_repository()
    details=await repository.get_release_group_by_id(
        group_id, includes=["releases"], priority=RequestPriority.IMAGE_FETCH
    )
    for edition in official_edition_ids(details,group_id):
        result=await coverart.get_release_cover(
            edition,size,is_disconnected=is_disconnected,
        )
        if result is not None:
            return result
    return None


async def missing_album_cover(
    album: object, local_id: str, coverart: object, size: str,
    is_disconnected: object = None,
) -> tuple[bytes, str, str] | None:
    """Resolve only an authenticated album whose native cover fetch missed.

    For synthetic UUIDv5, first map conservatively to a verified MusicBrainz
    release group. For an actual v3/v4 ID, avoid a redundant search and look
    for art on other official editions of that same release group.
    """
    synthetic=synthetic_album_id(local_id)
    genuine=_valid_rg(local_id)
    if not synthetic and not genuine:
        return None

    title=_attr(album,"title")
    artist=_attr(album,"artist_name")
    year=_year(_attr(album,"year")) or _year(_attr(album,"original_release_date"))
    if not isinstance(title,str) or not isinstance(artist,str):
        return None
    if not _normalize(title) or not _normalize(artist):
        return None

    path=_cache_path(local_id,title,artist,year)
    async with _sem():
        # The source album itself is authoritative if it has a genuine ID.
        if genuine:
            mbid=local_id.lower()
        else:
            projected=_attr(album,"musicbrainz_release_group_id")
            if _valid_rg(projected):
                mbid=projected.lower()
                found=True
            else:
                found,mbid=await asyncio.to_thread(_read_cache,path)
            if found and not mbid:
                return None
            if not found:
                try:
                    from core.dependencies.repo_providers import get_musicbrainz_repository
                    from infrastructure.queue.priority_queue import RequestPriority
                    repository=get_musicbrainz_repository()
                    candidates=await asyncio.wait_for(
                        repository.search_release_groups(
                            artist,title,limit=15,include_all_types=True,
                            priority=RequestPriority.IMAGE_FETCH,
                        ),timeout=SEARCH_TIMEOUT_SECONDS,
                    )
                    mbid=pick_verified_release_group(candidates,title,artist,year)
                    if candidates:
                        await asyncio.to_thread(_write_cache,path,mbid)
                except Exception:
                    return None
        if not mbid:
            return None
        if synthetic:
            # Native CoverArtRepository was already tried using the synthetic
            # local UUID, never the genuine MBID. Try that mapped MBID first.
            try:
                result=await asyncio.wait_for(
                    coverart.get_release_group_cover(
                        mbid,size,is_disconnected=is_disconnected
                    ),timeout=IMAGE_TIMEOUT_SECONDS,
                )
                if result is not None:
                    return result
            except Exception:
                pass

        # A release-group cover may be absent while another official edition
        # has front artwork. This is especially common on older MusicBrainz
        # entries, including some UUIDv3 release-group IDs.
        try:
            return await asyncio.wait_for(
                _edition_cover(mbid,coverart,size,is_disconnected),
                timeout=EDITION_TIMEOUT_SECONDS,
            )
        except Exception:
            return None
