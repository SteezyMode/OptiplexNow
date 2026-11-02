#!/usr/bin/env python3
"""Read-only Bruiser Music album metadata / artwork audit.

Uses the already-approved device's Secret Service app credential. It never
changes tags, cover files, DroppedNeedle state or provider caches explicitly.
A report distinguishes missing metadata from asynchronous art warming and from
a client that simply never requested the artwork.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import parse_qs

from music_keyring import VaultError, vault
from music_subsonic import MusicTransportError, _post, query, ALBUM_PAGE_SIZE


def _auth(server: str) -> dict[str, str]:
    form = vault("lookup", server)
    if not form:
        raise VaultError("Music is not connected on this device.")
    fields = parse_qs(form, keep_blank_values=True, strict_parsing=True)
    if set(fields) != {"api_key", "username"} or len(fields["api_key"]) != 1:
        raise VaultError("Music device credential format is invalid.")
    return {"apiKey": fields["api_key"][0]}


def cover_status(server: str, auth: dict[str, str], cover_id: str) -> str:
    if not cover_id:
        return "missing_cover_id"
    try:
        with _post(server, "getCoverArt", auth, {"id": cover_id, "size": "220"}) as response:
            if response.status == 202:
                return "warming"
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
            if mime in ("image/jpeg", "image/png", "image/webp"):
                # Reject empty response; avoid downloading full-size images.
                return "available" if response.read(48) else "empty_image"
            if mime == "image/svg+xml":
                return "placeholder"
            return "unexpected_content"
    except MusicTransportError as exc:
        # A cold cache or external cover provider failure is not proof that
        # an album has permanently missing metadata.
        return "unavailable"


def audit(server: str, auth: dict[str, str], *, max_albums: int = 500,
          delay: float = 0.8, sleep=time.sleep) -> dict:
    records: list[dict[str, str]] = []
    offset = 0
    while len(records) < max_albums:
        limit = min(ALBUM_PAGE_SIZE, max_albums-len(records))
        data = query(server, "getAlbumList2", auth, {
            "type": "alphabeticalByName", "size": str(limit), "offset": str(offset)})
        albums = data.get("albumList2", {}).get("album", [])
        if not isinstance(albums, list):
            raise MusicTransportError("Invalid album metadata response.")
        if not albums:
            break
        for album in albums[:limit]:
            if not isinstance(album, dict):
                continue
            identifier = album.get("id")
            if not isinstance(identifier, str) or not identifier:
                continue
            title = album.get("name") or album.get("title") or ""
            artist = album.get("artist") or ""
            cover_id = album.get("coverArt") or identifier
            status = cover_status(server, auth, str(cover_id))
            records.append({
                "id": identifier,
                "title": title if isinstance(title, str) else "",
                "artist": artist if isinstance(artist, str) else "",
                "cover_status": status,
                "missing_artist": not bool(artist),
                "missing_title": not bool(title),
            })
            if delay:
                sleep(delay)
        offset += len(albums)
        if len(albums) < limit:
            break
    categories: dict[str, int] = {}
    for album in records:
        kind = album["cover_status"]
        categories[kind] = categories.get(kind, 0)+1
    return {"albums_scanned": len(records), "cover_status": categories,
            "records": records, "read_only": True,
            "note": "Warming/unavailable may be transient. This does not modify metadata."}


def save_report(path: Path, report: dict) -> None:
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    content=(json.dumps(report, ensure_ascii=False, indent=2)+"\n").encode("utf-8")
    fd, temp_path = tempfile.mkstemp(prefix=".music-audit-", dir=str(path.parent))
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path,path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only album metadata and artwork audit")
    parser.add_argument("server_url", help="Approved DroppedNeedle Music URL")
    parser.add_argument("--max-albums",type=int,default=500)
    parser.add_argument("--delay",type=float,default=0.8)
    parser.add_argument("--output",type=Path,default=Path.home()/"MusicArtworkAudit.json")
    args=parser.parse_args(argv)
    if not 1 <= args.max_albums <= 5000 or not .2 <= args.delay <= 10:
        parser.error("Use 1-5000 albums and 0.2-10 seconds per cover check.")
    try:
        report=audit(args.server_url,_auth(args.server_url),
                     max_albums=args.max_albums,delay=args.delay)
        save_report(args.output,report)
    except (MusicTransportError,VaultError,OSError) as exc:
        print("Metadata audit could not complete: "+str(exc))
        return 1
    print("Albums scanned:",report["albums_scanned"])
    print("Artwork statuses:",json.dumps(report["cover_status"],sort_keys=True))
    print("Read-only report:",args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
