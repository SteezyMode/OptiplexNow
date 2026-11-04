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
import json
import re
import socket
import ssl
import sys
import unicodedata
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPHandler, HTTPSHandler

from music_subsonic import (
    MusicTransportError, DenyRedirects, endpoint_for, _bounded_text,
)

SCHEMA_NAME="com.bruiser.music.droppedneedle-rest"
MAX_SESSION=4096
MAX_REPLY=2*1024*1024
MAX_QUERY=200
MBID=re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z")
ALLOWED={
    "verify":("/auth/sessions","GET"),
    "search":("/search","GET"),
    "discover":("/discover","GET"),
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
        if exc.code==409 and action=="request":
            raise MusicRESTError("This album has already been requested.") from None
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
    return value


def _rows(results: dict[str,Any]) -> str:
    """Same five-column, base64-tabbed bounded transport as library rows."""
    rows=[]
    for kind in ("artist","album"):
        entries=results.get(kind+"s",[])
        if not isinstance(entries,list):continue
        for item in entries[:100]:
            if not isinstance(item,dict) or item.get("in_library") is True:
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
                    (artist+" · "+state)[:256],"")
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


DISCOVER_SECTIONS = (
    "fresh_releases", "missing_essentials", "new_from_followed",
    "artists_you_might_like", "popular_in_your_genres",
    "globally_trending", "rediscover", "listeners_like_you",
    "top_picks", "lastfm_weekly_artist_chart", "lastfm_weekly_album_chart",
    "anniversaries", "unexplored_genres"
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
            if not isinstance(item,dict) or item.get("in_library") is True:
                continue
            mbid=item.get("mbid")
            title=item.get("name")
            if (not isinstance(mbid,str) or not MBID.fullmatch(mbid) or
                not isinstance(title,str) or not title.strip() or
                mbid in seen):
                continue
            artist=item.get("artist_name") or ""
            if not isinstance(artist,str):artist=""
            # HomeArtist has no album metadata; HomeAlbum does. Follow the
            # section's explicit type first and never infer a song request.
            is_album=("album" in kind_hint or
                      (artist and "artist" not in kind_hint))
            kind="catalog_album" if is_album else "catalog_artist"
            state="Requested" if item.get("requested") else "Not in library"
            artist_key=_artist_name_key(title if kind=="catalog_artist" else artist)
            artist_id=item.get("artist_mbid") or item.get("artist_musicbrainz_id")
            if kind=="catalog_artist":
                artist_id=mbid
            known=(artist_key in liked_names if artist_key else False) or (
                isinstance(artist_id,str) and artist_id.lower() in liked_mbids)
            # A loved artist is a TASTE SIGNAL, not the definition of
            # discovery. Favor unseen artists with explicit shared genres.
            # Do not invent genre similarity when the API has no genre data.
            genres=_genre_names(item.get("genre")) | _genre_names(item.get("genres"))
            relevant=bool(genres & liked_genres) and not known
            accepted.append((known,relevant,(kind,mbid,title[:512],
                             (artist+" · "+state)[:256],"")))
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

    for key in DISCOVER_SECTIONS:
        add_section(result.get(key),key)
    for key in ("daily_mixes","radio_sections"):
        values=result.get(key,[])
        if isinstance(values,list):
            for index,section in enumerate(values[:8]):
                add_section(section,"%s_%d"%(key,index))
    because=result.get("because_you_listen_to",[])
    if isinstance(because,list):
        for index,pick in enumerate(because[:8]):
            if isinstance(pick,dict):
                add_section(pick.get("section"),"because_you_listen_%d"%index)
    return "\n".join(lines)+("\n" if lines else "")

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Bruiser Music authorized REST operations")
    parser.add_argument("base_url")
    parser.add_argument("operation",choices=(*ALLOWED.keys(),"link","unlink"))
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
        result=request(args.base_url,args.operation,token=token,value=args.value)
        if args.format=="rows":
            if args.operation=="search":
                sys.stdout.write(_rows(result))
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
