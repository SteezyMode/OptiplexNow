# Bruiser Music: standard desktop player UI and contextual acquisition

**Decision (2026-11-02): replicate the established Spotify desktop information architecture and interaction conventions.** Do not invent a new navigation paradigm. Use original Bruiser colors, names, graphics, icons, and code—not Spotify brand assets or proprietary implementation. The reference is Spotify's desktop Home / Search / Your Library / Now Playing model, including left library panel, album and playlist content views, and a persistent bottom player. Primary official reference: https://newsroom.spotify.com/2023-06-20/spotify-desktop-experience-redesign-your-library-now-playing-views-customize/

## Scope / application shell

NOW remains the overarching Dashboard / Games / Downloads / Video / Music / Settings application. **Inside Music**, use an ordinary music-player layout. The Music sidebar and navigation belong to Music only; do not invent extra top-level app tabs for Artists, Albums, playlists or music transfer queues.

| Region | Exact behavior |
|---|---|
| Left navigation | Home and Search at top; Your Library below, with Playlists / Artists / Albums / Liked filters and quick library search. The filters are familiar pills or text nav, not an independent sprawling admin form. Pinned/recent lists can follow after actual playlist support. |
| Central content | Real Home sections (recently played, new additions, discovery when backed by a working API), familiar album-art grid/cards, artist and album headers with primary Play button, track-list rows, and search results grouped by owned versus discoverable content. Keep sorting, pagination and a back button standard. |
| Bottom Now Playing | Album art, title/artist, previous/play-pause/next, seek/duration, queue, volume and shuffle/repeat when supported. A real, independently working local player. The bottom bar persists while listening across Music subviews, not replicated on each page. No decorative, dead controls. |
| Optional right panel | Queue or Now Playing details only if it actually helps; collapsed at small sizes. No permanently visible debug/admin panel. |
| Compact 640×500 / 1024×768 | Collapse or scroll left rail; preserve readable central content and access to the player. Never force the main NOW window taller just because Music has more destinations. |
| Advanced | DroppedNeedle management, one-time troubleshooting, music host diagnostics and explicit Forget device. Hide credentials and technical OpenSubsonic terminology outside Advanced. |

## Downloads: one shared management page, contextual acquisition buttons

The existing **Downloads** top-level tab stays for the already-working qBittorrent/Gluetun owner workflow: queue, progress, status, troubleshooting, destinations and VPN health. It is **not** required to incorporate DroppedNeedle/slskd transfer details. Keep its current controls; do not replace them or create a second elaborate music-transfer dashboard. Music's album cards only need small acquisition status indicators.

**Music**: Reuse DroppedNeedle directly. **Do not build another music download manager, scorer, queue scheduler, importer, quality-review engine, or normalized transfer abstraction.** Music Search/Discover displays DroppedNeedle's already-produced artists/albums, in-library/requested flags, and recommendation sections; a missing album gets one **Add to Library** action calling the existing request endpoint. On the same album card show DroppedNeedle's actual status (Requested / Downloading / Importing / Ready) where known, then Play when present. On rare failures show a lightweight status and **Advanced → DroppedNeedle**. Do not duplicate DroppedNeedle's complete queue or approval controls in Bruiser.

**DroppedNeedle v2.15.0 integration:** Native library playback uses the OpenSubsonic app password; discovery, requests, and progress use a **separate** device-scoped REST companion session stored in the OS keyring. The initialized owner account is linked once on the host, while each approved client receives revocable credentials via its existing restricted NOW SSH identity. The user's private-alpha stack has completed account linking and core Music operation; this UI pass adds live Favorites, playlists, All Songs and improved player/tray controls. No additional provider login is requested on individual devices. DroppedNeedle continues to own acquisition, quality control, library imports, and file metadata; Bruiser must not grow a parallel downloader or silently rewrite tags. Detailed real-device acceptance remains required for any new UI feature.

**Video**: Request/Add to Library belongs on the movie/show detail page *only after* a real, permissioned video acquisition/request backend exists. Do not mislabel a torrent-search result as a finished media request; do not conflate downloading to a client device with server-side library acquisition. Keep Jellyfin playback independent of qBittorrent.

**Naming**: Use Add to Library / Request for server acquisition, Download to device only for actually supported offline copies, and Downloads for monitoring. Never present a working button that secretly launches an admin page, or promise film requests are already integrated.

## Technical separation / release gates

- Music browse/stream uses OpenSubsonic internally. Users must **never** see "OpenSubsonic", `apiKey`, a username input or a permanent password form in normal Music screens.
- Music discovery, requesting, import and quality are backed by DroppedNeedle's own authenticated APIs. The existing music import stack is functional on the host but **Bruiser Music's unified Discover→Request→Download→Play is not implemented** until tested.
- The owner-approved NOW device should inherit automatic, revocable Music access (#246) after the signed NOW identity and authorization boundaries (#191/#192) work; a newly installed app alone does not authorize access.
- A CI-green library/player prototype is **not** the complete UI. Acceptance requires normal music discovery, request, import, playback, seeking, volume, queue, albums, artists and playlists without opening DroppedNeedle, plus compact-window and real-device validation.
- Leave unrelated Games, Video and Downloads behavior and existing Alpha 1 release criteria unchanged.

## Music UI modernization pass (2026-11-02, PR #245)

The previously working device-authorized Music stack stays in place. This pass is deliberately limited to Music client UI, OpenSubsonic player/library interactions and an opt-in, **read-only** metadata report.

- **Your Library is clickable** and opens the **All songs** view. The child filters remain Playlists, Artists, Albums and Liked Songs; Home, Search and Discover stay separately identifiable. An active navigation destination has a visible selection state.
- **All songs** uses the existing DroppedNeedle OpenSubsonic `search3` empty-query contract and explicit 200-track pagination. **Shuffle all** queries `getRandomSongs`; the current queue uses an independent randomized sequence with no repeats until exhausted. No pretend shuffling of a ten-song list.
- **Album and song rows** use larger text and targets. Album headers show the album/artist, with simple Play and Like icons. Individual songs show title plus artist/album and expose real **Like/Unlike** and **Add to playlist** actions. The playlist chooser fetches existing playlists and can create one using OpenSubsonic's existing endpoints. These operations are asynchronous and never put playback credentials in command-line arguments.
- **Now playing** shows album art, title, artist/album, icon Shuffle/Previous/Play-Pause/Next/Stop, seek and device-local volume; transport and tray actions control the current local session only.
- **Tray** uses standard GTK/AppIndicator-compatible menu items with recognizable symbols and is placed **at the bottom** after Quit. Native menu serialization on XFCE/AppIndicator does not reliably support a custom embedded multi-button toolbar or animated text ticker; the menu therefore truncates long captions rather than faking a scroll.
- **Album art** loads as cards enter the viewport, with at most four concurrent requests, rather than stopping permanently after 16 covers. Server-returned missing artwork stays a placeholder. The packaged `music_art_audit.py` can report missing/placeholder/warming artwork, artist/title/year/genre/MusicBrainz gaps and possible duplicate album identities. It **does not alter media files, metadata, or DroppedNeedle caches or databases**.
- **Release gates:** CI and in-person acceptance on Linux Mint XFCE, Pop!_OS COSMIC and the small projector resolution. Validate nonempty large libraries, track/album likes, new/existing playlists, shuffle transitions, next/end behavior, scrolling artwork, focus/selection and native tray menu rendering before marking UI complete.
