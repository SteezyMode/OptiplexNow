"""Read-only secondary cover source for opted-in AudioDB and verified albums.

Local/embedded art and Cover Art Archive are tried first by DroppedNeedle.
This provider is only used for a documented miss, never for media imports.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unicodedata

CACHE_ROOT=Path("/app/cache/bruiser-cover-name-fallback-v1")
IMAGE_MAX=3*1024*1024
CACHE_TTL_SECONDS=30*86400


def _normalize(text: object) -> str:
    if not isinstance(text,str):
        return ""
    value=unicodedata.normalize("NFKD",text).casefold()
    value="".join(c for c in value if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in value).split())


def _mime(blob: bytes) -> str | None:
    if blob.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(blob)>=12 and blob[:4]==b"RIFF" and blob[8:12]==b"WEBP":
        return "image/webp"
    return None


def _path(identifier: str, title: str, artist: str) -> Path:
    data=json.dumps([identifier,_normalize(title),_normalize(artist)],
                    separators=(",",":")).encode()
    return CACHE_ROOT/(hashlib.sha256(data).hexdigest()+".img")


def _read(path: Path) -> tuple[bytes,str,str] | None:
    try:
        if path.is_symlink():
            return None
        info=path.stat()
        if (not path.is_file() or info.st_size<8 or info.st_size>IMAGE_MAX or
                time.time()-info.st_mtime>CACHE_TTL_SECONDS):
            return None
        blob=path.read_bytes()
        mime=_mime(blob)
        if mime is not None:
            return blob,mime,"bruiser-audiodb-name-cache"
    except OSError:
        pass
    return None


def _write(path: Path, blob: bytes) -> None:
    if not _mime(blob) or len(blob)>IMAGE_MAX:
        return
    try:
        path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
        fd,temp=tempfile.mkstemp(prefix=".cover-",dir=path.parent)
        try:
            with os.fdopen(fd,"wb") as handle:
                os.fchmod(handle.fileno(),0o600)
                handle.write(blob)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp,path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    except OSError:
        return


async def album_name_cover(
    album: object, identifier: str, coverart: object,
) -> tuple[bytes,str,str] | None:
    """Match exact normalized title in artist-scoped AudioDB search.

    Uses only the already-configured and enabled provider. The image host is
    validated with the same DroppedNeedle HTTPS allowlist as native covers.
    """
    title=getattr(album,"title",None)
    artist=getattr(album,"artist_name",None)
    if not isinstance(title,str) or not isinstance(artist,str):
        return None
    if not _normalize(title) or not _normalize(artist):
        return None
    path=_path(identifier,title,artist)
    cached=await asyncio.to_thread(_read,path)
    if cached is not None:
        return cached

    try:
        from core.dependencies.repo_providers import (
            get_audiodb_image_service,get_audiodb_repository,
        )
        from infrastructure.validators import validate_audiodb_image_url
        from infrastructure.queue.priority_queue import RequestPriority

        service=get_audiodb_image_service()
        if not service.is_enabled():
            return None
        result=await asyncio.wait_for(
            get_audiodb_repository().search_album_by_name(artist,title),7)
        if not result or _normalize(getattr(result,"strAlbum",None))!=_normalize(title):
            return None
        url=getattr(result,"strAlbumThumb",None)
        if not isinstance(url,str) or not validate_audiodb_image_url(url):
            return None
        getter=getattr(coverart,"_http_get",None)
        if not callable(getter):
            return None
        response=await asyncio.wait_for(
            getter(url,RequestPriority.IMAGE_FETCH,source="audiodb"),7)
        if getattr(response,"status_code",None)!=200:
            return None
        blob=getattr(response,"content",None)
        if not isinstance(blob,bytes) or not 8<=len(blob)<=IMAGE_MAX:
            return None
        mime=_mime(blob)
        declared=str(getattr(response,"headers",{}).get("content-type","")
                     ).lower().split(";",1)[0].strip()
        if mime is None or declared not in ("image/jpeg","image/png","image/webp"):
            return None
        await asyncio.to_thread(_write,path,blob)
        return blob,mime,"bruiser-audiodb-name"
    except Exception:
        # Transient outages do not get a negative cache entry.
        return None
