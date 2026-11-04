"""Authenticated, device-local DroppedNeedle discovery and album request adapter.

This is distinct from the OpenSubsonic streaming app-password. DroppedNeedle
v2.15.0 REST routes require a standard or companion *bearer session*.
An approved host can provision one by invoking 'link' with the secret on
stdin; it is verified against /auth/sessions and stored only in OS Secret
Service. GUI operations read the token directly from the keyring; no password
is ever sent to GTK, argv, URL, logs, or to another server.

Companion sessions expire in 30 days upstream. Host-side reissue/renewal
through a verified NOW approval channel is a separate release gate.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import time
import json
import re
import socket
import ssl
import sys
import unicodedata
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit, unquote
from urllib.request import Request, build_opener, ProxyHandler, HTTPHandler, HTTPSHandler

from music_subsonic import (
    MusicTransportError, DenyRedirects, endpoint_for, _bounded_text,
)

SCHEMA_NAME="com.bruiser.music.droppedneedle-rest"
MAX_SESSION=4096
MAX_REPLY=2*1024*1024
MAX_QUERY=200
MAX_COVER=3*1024*1024
MBID=re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z")
ALLOWED={
    "verify":("/auth/sessions","GET"),
    "search":("/search","GET"),
    "discover":("/discover","GET"),
    "artist_releases":("/artists/{id}/releases","GET"),
    "catalog_tracks":("/albums/{id}/tracks","GET"),
    "request_track":("/tracks/{id}/request","POST"),
    "request":("/requests/new","POST"),
    "activity":("/downloads/activity-summary","GET"),
    "downloads":("/downloads","GET"),
}


class MusicRESTError(Exception):
    """Human-readable error with no token, URL or server-controlled message."""


def canonical_url(base_url: str) -> str:
    try:
        validated=endpoint_for(base_url,"ping")
    except MusicTransportError as exc:
        raise MusicRESTError("Invalid Music server address.") from exc
    return validated.removesuffix("/subsonic/rest/ping")


def secret_api():
    try:
        import gi
        gi.require_version("Secret","1")
        from gi.repository import Secret
        schema=Secret.Schema.new(
            SCHEMA_NAME,Secret.SchemaFlags.NONE,
            {"server":Secret.SchemaAttributeType.STRING})
        return Secret,schema
    except (ImportError,ValueError,AttributeError) as exc:
        raise MusicRESTError("Music device keyring is unavailable.") from exc


def _valid_token(raw: object) -> str:
    if not isinstance(raw,str) or not 16<=len(raw)<=2048 or any(
        ord(c)<33 or ord(c)>126 for c in raw):
        raise MusicRESTError("Invalid Music device authorization.")
    return raw


def get_session(base_url: str, provider=None) -> str:
    base=canonical_url(base_url)
    Secret,schema=provider() if provider is not None else secret_api()
    try:
        token=Secret.password_lookup_sync(schema,{"server":base},None)
    except Exception as exc:
        raise MusicRESTError("Music device keyring is locked or unavailable.") from exc
    if not token:
        raise MusicRESTError("Music requests need owner-approved device access.")
    return _valid_token(token)


def save_session(base_url: str, token: str, provider=None,
                 verify=True) -> None:
    base=canonical_url(base_url)
    token=_valid_token(token)
    if verify:
        request(base,"verify",token=token)
    Secret,schema=provider() if provider is not None else secret_api()
    try:
        ok=Secret.password_store_sync(
            schema,{"server":base},Secret.COLLECTION_DEFAULT,
            "Bruiser Music — authorized requests",token,None)
    except Exception as exc:
        raise MusicRESTError("Could not save Music device authorization.") from exc
    if not ok:
        raise MusicRESTError("Could not save Music device authorization.")


def clear_session(base_url: str, provider=None) -> None:
    base=canonical_url(base_url)
    Secret,schema=provider() if provider is not None else secret_api()
    try:
        Secret.password_clear_sync(schema,{"server":base},None)
    except Exception as exc:
        raise MusicRESTError("Could not clear Music device authorization.") from exc


def request(base_url: str, action: str, *,
            token: str, value: str | None = None) -> dict[str, Any]:
    base=canonical_url(base_url)
    if action not in ALLOWED:
        raise MusicRESTError("Unsupported Music request.")
    path,verb=ALLOWED[action]
    query={}
    body=None
    if action=="artist_releases":
        if not isinstance(value,str) or not MBID.fullmatch(value):
            raise MusicRESTError("Cannot identify this artist's discography.")
        path=path.replace("{id}",value.lower())
        query={"limit":"200","offset":"0"}
    if action=="catalog_tracks":
        group, artist, album = _track_context(value, 3)
        path=path.replace("{id}",group)
    if action=="request_track":
        recording, artist, title, album, group = _track_context(value, 5)
        if not MBID.fullmatch(group):
            raise MusicRESTError("Cannot identify this track album.")
        path=path.replace("{id}",recording)
        body=json.dumps({"artist_name":artist,"track_title":title,
                         "album_title":album,"release_group_mbid":group},
                        separators=(",",":")).encode("utf-8")
    if action=="search":
        query={"q":_bounded_text(value,"search",MAX_QUERY),
               "limit_artists":"10","limit_albums":"25"}
    if action=="request":
        if not isinstance(value,str) or not MBID.fullmatch(value):
            raise MusicRESTError("Cannot identify this album for download.")
        body=json.dumps({"musicbrainz_id":value},separators=(",",":")).encode()
    if action=="downloads":
        # A bounded owner-scoped queue snapshot, never a new download manager.
        query={"page_size":"100"}
        if value is not None:
            if not isinstance(value,str) or not MBID.fullmatch(value):
                raise MusicRESTError("Invalid album selection.")
            query={"release_group_mbid":value,"page_size":"20"}
    parts=urlsplit(base)
    url=urlunsplit((parts.scheme,parts.netloc,
                    parts.path.rstrip("/")+"/api/v1"+path,urlencode(query),""))
    headers={"Accept":"application/json",
             "Authorization":"Bearer "+_valid_token(token),
             "Cache-Control":"no-store"}
    if body is not None:
        headers["Content-Type"]="application/json"
    req=Request(url,data=body,headers=headers,method=verb)
    opener=build_opener(ProxyHandler({}),DenyRedirects(),
                        HTTPHandler(),HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(req,timeout=18) as response:
            data=response.read(MAX_REPLY+1)
    except MusicTransportError:
        raise MusicRESTError("Music server redirected the request.") from None
    except HTTPError as exc:
        if exc.code in (401,403):
            raise MusicRESTError("Music device access has expired or was revoked.") from None
        if exc.code==409 and action in ("request","request_track"):
            raise MusicRESTError("This music has already been requested.") from None
        raise MusicRESTError("Music service could not complete this action.") from None
    except (URLError,OSError,socket.timeout):
        raise MusicRESTError("Music server is unreachable.") from None
    if len(data)>MAX_REPLY:
        raise MusicRESTError("Music response exceeded safe size.")
    try:
        value=json.loads(data)
    except (UnicodeError,ValueError):
        raise MusicRESTError("Music server returned unreadable results.") from None
    if not isinstance(value,dict):
        raise MusicRESTError("Music service returned invalid results.")
    if action=="catalog_tracks":
        value={"tracks":value.get("tracks",[]), "artist":artist,
               "album":album, "release_group_mbid":group}
    return value


def cover_bytes(base_url: str, cover_id: str, *, token: str) -> bytes:
    """Fetch one catalog image through an authenticated, fixed-path DN endpoint.

    Never fetch arbitrary upstream URLs, return SVG placeholders, or put the
    device's bearer credential in a URL, command line, or public image cache.
    """
    if not isinstance(cover_id,str):
        raise MusicRESTError("Invalid catalog cover.")
    kind,sep,mbid=cover_id.partition(":")
    if sep!=":" or kind not in ("album","artist") or not MBID.fullmatch(mbid):
        raise MusicRESTError("Invalid catalog cover.")
    base=canonical_url(base_url)
    parts=urlsplit(base)
    path="/covers/release-group/" if kind=="album" else "/covers/artist/"
    url=urlunsplit((parts.scheme,parts.netloc,
        parts.path.rstrip("/")+"/api/v1"+path+mbid, "size=250", ""))
    opener=build_opener(ProxyHandler({}),DenyRedirects(),
                        HTTPHandler(),HTTPSHandler(context=ssl.create_default_context()))
    for attempt in range(2):
        req=Request(url,headers={
            "Authorization":"Bearer "+_valid_token(token),
            "Accept":"image/jpeg, image/png, image/webp",
        },method="GET")
        try:
            with opener.open(req,timeout=12) as response:
                if response.status==202:
                    if attempt==0:
                        import time
                        time.sleep(2)
                        continue
                    raise MusicRESTError("Catalog artwork is still loading.")
                kind=response.headers.get("Content-Type","").split(";",1)[0].strip().lower()
                if kind not in ("image/jpeg","image/png","image/webp"):
                    raise MusicRESTError("Catalog artwork is not available.")
                size=response.headers.get("Content-Length")
                if size and size.isdecimal() and int(size)>MAX_COVER:
                    raise MusicRESTError("Catalog artwork is too large.")
                data=response.read(MAX_COVER+1)
                if not data or len(data)>MAX_COVER:
                    raise MusicRESTError("Catalog artwork is not usable.")
                return data
        except MusicTransportError:
            raise MusicRESTError("Catalog image redirected; access denied.") from None
        except HTTPError as exc:
            if exc.code in (401,403):
                raise MusicRESTError("Music device access has expired or was revoked.") from None
            raise MusicRESTError("Catalog artwork is temporarily unavailable.") from None
        except (URLError,OSError,socket.timeout):
            raise MusicRESTError("Catalog artwork is temporarily unavailable.") from None
    raise MusicRESTError("Catalog artwork is still loading.")


def _artist_releases_rows(result: dict[str,Any]) -> str:
    """Render bounded MusicBrainz release groups as requestable album cards.

    A real artist MBID is required upstream. Albums, EPs and singles remain
    distinct in the subtitle. Discography cards are actual artist releases,
    never a best-effort title-only search for the artist's name.
    """
    if not isinstance(result,dict):
        raise MusicRESTError("Artist discography returned invalid data.")
    out=[]
    seen=set()
    for key,label in (("albums","Album"),("eps","EP"),("singles","Single")):
        items=result.get(key)
        if not isinstance(items,list):
            continue
        for item in items[:200]:
            if len(out)>=200:
                break
            if not isinstance(item,dict):
                continue
            mbid=item.get("id")
            title=item.get("title")
            if (not isinstance(mbid,str) or not MBID.fullmatch(mbid) or
                not isinstance(title,str) or not title.strip() or mbid in seen):
                continue
            seen.add(mbid)
            year=item.get("year")
            if not isinstance(year,int) or not 1900<=year<=2100:
                date=item.get("first_release_date")
                year=(int(date[:4]) if isinstance(date,str) and
                      len(date)>=4 and date[:4].isdigit() else None)
            requested=item.get("requested") is True
            owned=item.get("in_library") is True
            status="In library" if owned else ("Requested" if requested else "Not in library")
            subtitle=" · ".join(x for x in (
                label, str(year) if year else "", status) if x)
            fields=("catalog_album",mbid,title[:512],subtitle[:256],
                    "dn-album:"+mbid)
            out.append("\t".join(base64.b64encode(x.encode("utf-8")).decode("ascii")
                                 for x in fields))
    return "\n".join(out)+("\n" if out else "")


def _rows(results: dict[str,Any]) -> str:
    """Same five-column, base64-tabbed bounded transport as library rows."""
    rows=[]
    for kind in ("artist","album"):
        entries=results.get(kind+"s",[])
        if not isinstance(entries,list):continue
        for item in entries[:100]:
            if not isinstance(item,dict) or (kind=="album" and item.get("in_library") is True):
                continue
            title=item.get("title")
            mbid=item.get("musicbrainz_id")
            if (not isinstance(title,str) or not title or
                not isinstance(mbid,str) or not MBID.fullmatch(mbid)):
                continue
            artist=item.get("artist") or ""
            if not isinstance(artist,str):artist=""
            state="Requested" if item.get("requested") else "Not in library"
            fields=("catalog_"+kind,mbid,title[:512],
                    (artist+" · "+state)[:256],"dn-"+kind+":"+mbid)
            rows.append("\t".join(base64.b64encode(x.encode()).decode()
                                  for x in fields))
    return "\n".join(rows)+("\n" if rows else "")




STATUS_NAMES = {
    "queued": "Queued", "searching": "Searching",
    "downloading": "Downloading", "processing": "Importing",
    "verifying": "Verifying", "importing": "Importing",
    "completed": "Downloaded — check library",
    "held": "Needs review", "held_for_review": "Needs review",
    "failed": "Failed", "cancelled": "Cancelled",
    "waiting": "Queued",
}


def _download_rows(result: dict[str,Any]) -> str:
    """Display a factual bounded snapshot of DroppedNeedle's own queue.

    Return only validated album IDs and fixed status labels. A completed
    download is NOT proof of playback readiness: actual library presence is
    checked through OpenSubsonic on the next library refresh.
    """
    items=result.get("items",[])
    if not isinstance(items,list):
        return ""
    seen={}
    # Task responses can represent multiple files of the same album.
    priority={
        "downloading": 7,"importing": 6,"processing": 6,
        "verifying": 6,"held": 5,"held_for_review": 5,
        "failed": 4,"searching": 3,"queued": 2,"waiting": 2,
        "completed": 1,"cancelled": 0,
    }
    for item in items[:100]:
        if not isinstance(item,dict):
            continue
        mbid=item.get("release_group_mbid")
        status=item.get("status")
        if (not isinstance(mbid,str) or not MBID.fullmatch(mbid)
            or not isinstance(status,str) or status not in STATUS_NAMES):
            continue
        if item.get("held_for_review") is True:
            status="held_for_review"
        progress=item.get("progress_percent")
        if type(progress) is not int or not 0<=progress<=100:
            progress=0
        label=STATUS_NAMES[status]
        if status=="downloading":
            label="Downloading %d%%"%progress
        previous=seen.get(mbid)
        if previous is None or priority[status]>previous[0]:
            seen[mbid]=(priority[status],label)
    return "".join(mbid+"\t"+value[1]+"\n" for mbid,value in seen.items())


# Retain a bounded, owner-device-local last-good Discover feed. DroppedNeedle
# may legitimately return refreshing=true with no sections after a container
# recreation; do not replace a healthy earlier feed with that empty response.
# Cache entries are scoped to the exact approved device bearer and host.
DISCOVER_CACHE_TTL = 7 * 86400
DISCOVER_CACHE_LIMIT = 512 * 1024

def _discover_cache_path(base_url: str, token: str) -> Path:
    origin=canonical_url(base_url)
    digest=hashlib.sha256((origin+"\\0"+token).encode("utf-8")).hexdigest()
    return Path.home()/".cache"/"optiplex-now"/"music-discover-v1"/(digest+".json")

def _last_discover_rows(base_url: str, token: str) -> str:
    path=_discover_cache_path(base_url,token)
    try:
        if path.is_symlink():
            return ""
        info=path.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_size > DISCOVER_CACHE_LIMIT
                or info.st_mode & 0o077):
            return ""
        data=json.loads(path.read_text(encoding="utf-8"))
        written=data.get("saved_at")
        rows=data.get("rows")
        if (data.get("version")!=1 or not isinstance(rows,str)
                or not isinstance(written,(int,float))
                or not 0 <= time.time()-written <= DISCOVER_CACHE_TTL
                or len(rows.encode("utf-8"))>DISCOVER_CACHE_LIMIT
                or not rows.strip()):
            return ""
        return rows
    except (OSError,ValueError,TypeError,UnicodeError):
        return ""

def _store_discover_rows(base_url: str, token: str, rows: str) -> None:
    if not rows or len(rows.encode("utf-8"))>DISCOVER_CACHE_LIMIT//2:
        return
    path=_discover_cache_path(base_url,token)
    try:
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        if path.parent.is_symlink():
            return
        fd,tmp=tempfile.mkstemp(prefix=".discover-",dir=path.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as stream:
                os.fchmod(stream.fileno(),0o600)
                json.dump({"version":1,"saved_at":time.time(),"rows":rows},stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except (OSError,ValueError):
        return

def retained_discover_rows(base_url: str, token: str, response: dict[str, Any],
                           *,favorite_artists=None,favorite_genres=None) -> str:
    """Use real current recommendations or last known valid ones after warmup.

    Requires a successful, authorized REST response: auth errors never fall
    back to cached data. Does not make a download/request or mark items liked.
    """
    rows=_discover_rows(response,favorite_artists=favorite_artists,
                        favorite_genres=favorite_genres)
    if rows.strip():
        _store_discover_rows(base_url,token,rows)
        return rows
    return _last_discover_rows(base_url,token)


# Personal discovery first. General-popularity charts should never crowd out
# recommendations from the owner's listens and favorites.
DISCOVER_SECTIONS = (
    "top_picks", "artists_you_might_like", "listeners_like_you",
    "popular_in_your_genres", "new_from_followed",
    "fresh_releases", "unexplored_genres", "missing_essentials",
    "rediscover", "anniversaries", "lastfm_weekly_album_chart",
    "lastfm_weekly_artist_chart", "globally_trending"
)


def _artist_name_key(name: object) -> str:
    """Only exact Unicode-normalized artist names qualify as a fallback ID."""
    if not isinstance(name,str) or not name.strip() or len(name)>256:
        return ""
    key=" ".join(unicodedata.normalize("NFKC",name).casefold().split())
    return "" if key in ("unknown artist","various artists","unknown") else key


def _favorite_artist_signals(starred: object) -> tuple[set[str],set[str]]:
    """Read-only, per-user signals. No playback tracking or external writes."""
    if not isinstance(starred,dict):
        return set(),set()
    names:set[str]=set()
    mbids:set[str]=set()
    for category in ("song","album","artist"):
        entries=starred.get(category,[])
        if not isinstance(entries,list):
            continue
        for item in entries[:400]:
            if not isinstance(item,dict):
                continue
            candidate=item.get("name") if category=="artist" else item.get("artist")
            name=_artist_name_key(candidate)
            if name:
                names.add(name)
            # The artistMBID is not the release/album MBID. Never compare
            # a liked track or album ID to a recommended album ID.
            identifiers=("musicBrainzId","musicbrainzId","mbid") if category=="artist" else (
                "artistMusicBrainzId","artistMbid","artistMBID")
            for key in identifiers:
                artist_mbid=item.get(key)
                if isinstance(artist_mbid,str) and MBID.fullmatch(artist_mbid):
                    mbids.add(artist_mbid.lower())
    return names,mbids


def _genre_names(value: object) -> set[str]:
    """Read only explicit, bounded genre labels; never guess from an artist."""
    if isinstance(value,str):
        candidates=[value]
    elif isinstance(value,list):
        candidates=[x if isinstance(x,str) else x.get("name") or x.get("value")
                    if isinstance(x,dict) else None for x in value[:20]]
    else:
        return set()
    return {label for entry in candidates
            if (label:=_artist_name_key(entry))}


def _favorite_genre_signals(starred: object) -> set[str]:
    """Explicit genres from THIS user's liked songs/albums, never server-wide."""
    if not isinstance(starred,dict):
        return set()
    genres:set[str]=set()
    for kind in ("song","album"):
        entries=starred.get(kind,[])
        if not isinstance(entries,list):
            continue
        for item in entries[:400]:
            if isinstance(item,dict):
                genres.update(_genre_names(item.get("genre")))
                genres.update(_genre_names(item.get("genres")))
    return genres


def _discover_rows(result: dict[str, Any], *,
                   favorite_artists: tuple[set[str],set[str]] | None = None,
                   favorite_genres: set[str] | None = None) -> str:
    """Flatten only DroppedNeedle's known discovery sections into safe rows.

    Section boundaries are preserved for the native GTK screen. DroppedNeedle
    remains responsible for recommendation logic and album identity. When
    available, this user's likes can only reorder existing eligible entries
    inside each section; they never create a request or follow an artist.
    """
    lines=[]
    seen=set()
    total=0
    liked_names,liked_mbids=favorite_artists or (set(),set())
    liked_genres=favorite_genres or set()

    def add_section(section: object, key: str):
        nonlocal total
        if total>=180 or not isinstance(section,dict):
            return
        items=section.get("items",[])
        if not isinstance(items,list):
            return
        kind_hint=str(section.get("type","")).lower()
        accepted=[]
        for item in items[:50]:
            if not isinstance(item,dict):
                continue
            # TopPicksSection wraps a HomeAlbum in {"album": ..., "match_pct": ...}.
            # Previously these best personal recommendations were silently dropped.
            candidate=item.get("album") if key=="top_picks" else item
            if not isinstance(candidate,dict) or candidate.get("in_library") is True:
                continue
            mbid=candidate.get("mbid")
            title=candidate.get("name")
            if (not isinstance(mbid,str) or not MBID.fullmatch(mbid) or
                not isinstance(title,str) or not title.strip() or
                mbid in seen):
                continue
            artist=candidate.get("artist_name") or ""
            if not isinstance(artist,str):artist=""
            # HomeArtist has no album metadata; HomeAlbum does. Follow the
            # section's explicit type first and never infer a song request.
            is_album=("album" in kind_hint or
                      (artist and "artist" not in kind_hint))
            kind="catalog_album" if is_album else "catalog_artist"
            state="Requested" if candidate.get("requested") else "Not in library"
            artist_key=_artist_name_key(title if kind=="catalog_artist" else artist)
            artist_id=candidate.get("artist_mbid") or candidate.get("artist_musicbrainz_id")
            if kind=="catalog_artist":
                artist_id=mbid
            known=(artist_key in liked_names if artist_key else False) or (
                isinstance(artist_id,str) and artist_id.lower() in liked_mbids)
            # A loved artist is a TASTE SIGNAL, not the definition of
            # discovery. Favor unseen artists with explicit shared genres.
            # Do not invent genre similarity when the API has no genre data.
            genres=_genre_names(candidate.get("genre")) | _genre_names(candidate.get("genres"))
            relevant=bool(genres & liked_genres) and not known
            accepted.append((known,relevant,(kind,mbid,title[:512],
                             (artist+" · "+state)[:256],
                             "dn-"+("album" if is_album else "artist")+":"+mbid)))
            seen.add(mbid)
            total+=1
            if total>=180:break
        if not accepted:
            return
        heading=section.get("title")
        if not isinstance(heading,str) or not heading.strip():
            heading=key.replace("_"," ").title()
        # Keep DroppedNeedle's candidate sections and preserve upstream order
        # within equal tiers. New-artist sections never boost an already-liked
        # artist. The rediscovery/followed sections retain their own ordering.
        novelty_sections={"artists_you_might_like","listeners_like_you",
                          "unexplored_genres","popular_in_your_genres",
                          "top_picks"}
        if key in novelty_sections and (liked_names or liked_mbids or liked_genres):
            accepted.sort(key=lambda entry:(entry[0],not entry[1]))
        elif liked_genres and key not in ("rediscover","new_from_followed"):
            # A small taste hint for a new artist, not a same-artist loop.
            accepted.sort(key=lambda entry:not entry[1])
        rows=[("section",key,heading[:96],"","")]
        rows.extend(fields for _,_,fields in accepted)
        for fields in rows:
            lines.append("\t".join(base64.b64encode(x.encode()).decode()
                                   for x in fields))

    # "Because you listened to" is the most direct evidence-based shelf.
    because=result.get("because_you_listen_to",[])
    if isinstance(because,list):
        for index,pick in enumerate(because[:2]):
            if not isinstance(pick,dict):
                continue
            section=pick.get("section")
            if not isinstance(section,dict):
                continue
            seed=pick.get("seed_artist")
            # A genuinely personal tile, derived from DroppedNeedle's linked
            # ListenBrainz history, not a hard-coded genre or guessed artist.
            if isinstance(seed,str):
                seed=" ".join(seed.strip().split())
                if seed and len(seed)<=64:
                    section={**section,"title":"Because You Listen to "+seed}
            add_section(section,"because_you_listen_%d"%index)
    # Reserve a fair slice for genuine user mixes before broad discovery can
    # consume the 180-entry budget. Up to two mixes and two radio-based
    # recommendation pools (radio here means album picks, not streaming).
    personal_shelves={"top_picks","artists_you_might_like",
                      "listeners_like_you","popular_in_your_genres"}
    for key in DISCOVER_SECTIONS:
        if key in personal_shelves:
            add_section(result.get(key),key)
    for key in ("daily_mixes","radio_sections"):
        values=result.get(key,[])
        if isinstance(values,list):
            for index,section in enumerate(values[:2]):
                if key=="radio_sections" and isinstance(section,dict):
                    label=section.get("title")
                    if isinstance(label,str) and label.startswith("Radio: "):
                        # These are suggestions, NOT full audio streams yet.
                        section={**section,"title":"Artist Picks: "+label[7:]}
                add_section(section,"%s_%d"%(key,index))
    for key in DISCOVER_SECTIONS:
        if key not in personal_shelves:
            add_section(result.get(key),key)
    return "\n".join(lines)+("\n" if lines else "")

def _track_context(value: str | None, count: int) -> tuple[str, ...]:
    """Bounded percent-escaped identifiers and metadata, never credentials."""
    if not isinstance(value, str) or len(value) > 2200:
        raise MusicRESTError("Invalid track selection.")
    parts=value.split("|")
    if len(parts)!=count:
        raise MusicRESTError("Invalid track selection.")
    decoded=[]
    for i, part in enumerate(parts):
        # Only URI-escaped printable text; reject malformed encoding and newlines.
        if re.search(r"%(?![0-9a-fA-F]{2})",part):
            raise MusicRESTError("Invalid track selection.")
        try:
            item=unquote(part,encoding="utf-8",errors="strict")
        except UnicodeError as exc:
            raise MusicRESTError("Invalid track selection.") from exc
        if i==0:
            if not MBID.fullmatch(item):
                raise MusicRESTError("Invalid MusicBrainz track or album ID.")
            item=item.lower()
        elif count==5 and i==4:
            if not MBID.fullmatch(item):
                raise MusicRESTError("Invalid album ID.")
            item=item.lower()
        else:
            try:
                item=_bounded_text(item,"track metadata",512)
            except MusicTransportError as exc:
                raise MusicRESTError("Invalid track metadata.") from exc
        decoded.append(item)
    return tuple(decoded)


def _catalog_track_rows(result: dict[str,Any]) -> str:
    """Separate acquisition-only rows; never pretend remote songs are playable."""
    out=[]
    tracks=result.get("tracks",[])
    if not isinstance(tracks,list):
        return ""
    artist=result.get("artist","")
    album=result.get("album","")
    group=result.get("release_group_mbid","")
    for track in tracks[:200]:
        if not isinstance(track,dict):
            continue
        recording=track.get("recording_id")
        title=track.get("title")
        if not isinstance(recording,str) or not MBID.fullmatch(recording):
            continue
        if not isinstance(title,str) or not title.strip():
            continue
        fields=("catalog_track",recording.lower(),title[:512],
                artist[:512],"dn-album:"+group,album[:512],"0")
        out.append("\t".join(base64.b64encode(x.encode("utf-8")).decode("ascii")
                             for x in fields))
    return "\n".join(out)+("\n" if out else "")


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Bruiser Music authorized REST operations")
    parser.add_argument("base_url")
    parser.add_argument("operation",choices=(*ALLOWED.keys(),"cover","link","unlink"))
    parser.add_argument("value",nargs="?")
    parser.add_argument("--format",choices=("json","rows"),default="json")
    args=parser.parse_args(argv)
    try:
        if args.operation=="link":
            # Only a separately authorized host/device provisioning flow may
            # hand a DN companion bearer here. Never put it in a URL/argv.
            data=sys.stdin.buffer.read(MAX_SESSION+1)
            if len(data)>MAX_SESSION:
                raise MusicRESTError("Music authorization was too large.")
            try:token=data.decode().strip()
            except UnicodeError:raise MusicRESTError("Invalid Music authorization.") from None
            save_session(args.base_url,token)
            print('linked')
            return 0
        if args.operation=="unlink":
            clear_session(args.base_url)
            print('unlinked')
            return 0
        token=get_session(args.base_url)
        if args.operation=="cover":
            sys.stdout.buffer.write(cover_bytes(args.base_url,args.value,token=token))
            return 0
        result=request(args.base_url,args.operation,token=token,value=args.value)
        if args.format=="rows":
            if args.operation=="search":
                sys.stdout.write(_rows(result))
            elif args.operation=="artist_releases":
                sys.stdout.write(_artist_releases_rows(result))
            elif args.operation=="catalog_tracks":
                sys.stdout.write(_catalog_track_rows(result))
            elif args.operation=="discover":
                sys.stdout.write(_discover_rows(result))
            elif args.operation=="downloads":
                sys.stdout.write(_download_rows(result))
            else:
                raise MusicRESTError("Row output unavailable for this Music action.")
        else:
            json.dump(result,sys.stdout,ensure_ascii=False,separators=(",",":"))
            sys.stdout.write("\n")
        return 0
    except (MusicRESTError,MusicTransportError) as exc:
        # No secret-bearing exception details, URL, or server JSON emitted.
        print(str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
