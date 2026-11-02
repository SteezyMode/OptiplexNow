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

The existing **Downloads** top-level tab stays, because it is a distinct *transfer-management utility* for owner workflows: active queue, progress, status, troubleshooting, pause/resume, search plugins, destination folders and VPN health. Keep its full qBittorrent/Gluetun capabilities; do not remove it or duplicate its control panel in Music or Video.

**Music**: On a discoverable artist/album/track missing from the current library, show a standard **Add to Library / Request** action where the user sees it. This calls DroppedNeedle's authenticated discovery/request backend; show Searching / Queued / Downloading / Importing / Ready and eventually Play in place. The detailed global queue may also show Music work if a secure normalized status adapter is available, but it must not assume Soulseek requests are qBittorrent transfers. DroppedNeedle stays the sole music-acquisition/import engine; slskd is not a user-facing GUI.

**Video**: Request/Add to Library belongs on the movie/show detail page *only after* a real, permissioned video acquisition/request backend exists. Do not mislabel a torrent-search result as a finished media request; do not conflate downloading to a client device with server-side library acquisition. Keep Jellyfin playback independent of qBittorrent.

**Naming**: Use Add to Library / Request for server acquisition, Download to device only for actually supported offline copies, and Downloads for monitoring. Never present a working button that secretly launches an admin page, or promise film requests are already integrated.

## Technical separation / release gates

- Music browse/stream uses OpenSubsonic internally. Users must **never** see "OpenSubsonic", `apiKey`, a username input or a permanent password form in normal Music screens.
- Music discovery, requesting, import and quality are backed by DroppedNeedle's own authenticated APIs. The existing music import stack is functional on the host but **Bruiser Music's unified Discover→Request→Download→Play is not implemented** until tested.
- The owner-approved NOW device should inherit automatic, revocable Music access (#246) after the signed NOW identity and authorization boundaries (#191/#192) work; a newly installed app alone does not authorize access.
- A CI-green library/player prototype is **not** the complete UI. Acceptance requires normal music discovery, request, import, playback, seeking, volume, queue, albums, artists and playlists without opening DroppedNeedle, plus compact-window and real-device validation.
- Leave unrelated Games, Video and Downloads behavior and existing Alpha 1 release criteria unchanged.
