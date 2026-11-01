# Downloads: projector-height usability and native Transfers controls

Status: **unreleased development PR**. The published v1.21.12 client and the currently operating host services must remain unchanged until tested.

## UI corrections

- The whole native Downloads view now has a vertical scrollbar, including VPN, toolbar, Search / Transfers and the destination chooser. Advanced VueTorrent stays its own full-height embedded browser.
- Search results and destination selection now use **separate full-height steps in the same Downloads tab**, rather than splitting the viewport between two tiny list boxes. After selecting a magnet, the app switches to CHOOSE DOWNLOAD LOCATION, with BACK TO RESULTS to restore the existing search and scroll position without querying or submitting anything.
- Each focused list is a substantially larger 420px viewport by default (vs. the earlier 150px search and 300px picker). The native Downloads page still scrolls at 1024×768 and below.
- Search result selection reveals the destination work area after GTK allocation. This is purely a view/scroll operation and does not submit a torrent.
- The folder browser is raised from 110px to 420px, with a case-insensitive local folder filter. Typing “Horror” searches the approved current directory, never a host-wide path or unrestricted endpoint.
- ADD TO SELECTED FOLDER is above the folder list; it cannot be pushed below that list when many folders are present.
- Native Transfers uses page-level scrolling and wraps actions into two or three buttons per row so 1024×768 projector and narrow laptop layouts remain navigable.

## More complete native Transfers

- Keep existing pause, resume, reannounce, recheck, remove-but-keep-files.
- Add **FILES**: read-only, bounded relative paths, size, completion percentage, skipped/included priority in an in-app scrollable dialog. If the torrent has more than 120 entries, the dialog explicitly announces truncation and refers the user to Advanced VueTorrent.
- Add distinct **DELETE FILES**: removes the torrent and asks qBittorrent to delete the torrent content ONLY after an explicit destructive confirmation. The previous REMOVE action still passes `deleteFiles=false`.
- Both actions use the existing restricted SSH owner device credential. No new browser login, password storage, privileged client endpoint or arbitrary filesystem path request.
- The host rejects a data-delete operation unless an exact torrent hash exists and the content and save paths are within a configured approved writable library subfolder, with current verified VPN-bound gateway.
- The UI does not claim deletion succeeded until the broker acknowledges the operation; the response does not enumerate or report every deleted file.

## Deployment/compatibility

**Important:** FILES and DELETE FILES are **new host broker capabilities**, not client-only fixes. They will not work against the existing deployed owner broker until the host-side `server/download_files.py`, `server/download_manage.py` and `server/owner_games_request.py` are installed as one rollback-ready update and independently checked against its existing authorization setup. Do not replace the live restricted command piecemeal, as an unresolved import would break other trusted owner services.

No host deployment, host file deletion, qBittorrent configuration or running-container mutation is performed by this PR.

## Acceptance

- CI: Python backend/client negative tests, native GTK folder picker and queue tests, installed .deb smoke/sanitizer suite. The focused-view GTK regression exercises a **16:9 1920×1080 desktop**, a **16:9 1366×768 laptop**, a **16:10 1280×800 laptop**, a **1024×768 4:3 legacy projector**, and the **430px minimum-width window**. It must demonstrate that the file browser grows when desktop space is available, rather than staying at 420px everywhere.
- Device acceptance: use projector at 1024×768 4:3; choose a magnet, filter Movies → Horror, verify Add remains reachable without resizing. Test a torrent with many files. Confirm REMOVE keeps files. Test DELETE FILES only on disposable test data with verified backups and host-side authorization.
- Longer-term: per-file priorities, per-torrent filters, sorting, tracker details and better transfer statistics can be separate follow-up features; this PR does not claim qBittorrent UI parity.

## Default presentation vs. compatibility

**The product is not designed around the projector.** Desktop/laptop 16:9 and 16:10 screens are the primary layouts, with taller and wider workspaces when the app window grows. The 1024×768 projector and narrow 430px minimum-width window are **regression cases** for graceful compression and scrolling, not reference dimensions or reasons to add cramped fixed-height controls.

No 4:3-only UI mode, aspect-ratio detection, device-specific workaround, fullscreen requirement, or new user settings are introduced. The same focused Search → Destination flow is used consistently across supported displays.

## GTK3 design pattern

Official [GTK3 GtkPaned documentation](https://docs.gtk.org/gtk3/class.Paned.html)
describes adjustable split views with drag handles; these are appropriate when
both panes genuinely need to be visible at once. For a 1024×768 projector,
however, a splitter cannot create additional vertical real estate: a 50/50
results + destination split would leave two constrained browsers. The GNOME
[HIG navigation guidance](https://developer.gnome.org/hig/guidelines/navigation.html)
prefers in-place switching between views for multi-step tasks. This feature
therefore uses a GTK3 GtkStack workflow (Search → Destination → Add), without
adding a modal dialog, extra window, or more deeply nested scroll regions.

Manual acceptance includes checking that the Back button preserves the last
search results, that the picker can reach Horror without micro-scrolling, and
that the confirmation button remains visible after a long folder list.

## Additional download locations and search pagination

- The owner can select any existing subfolder within qBittorrent's approved
  writable `/library/<slug>` mounts; folders are not restricted to Movies/TV.
  **NEW FOLDER** creates one checked child directory (e.g. `Games`) inside
  the selected, already mounted drive. This request uses the same verified owner
  device identity, parent directory file descriptor without symlink traversal,
  and qBittorrent's actual user write check. Existing files are never moved.
- **SAVE LOCATION** remembers the originating verified host and SSH user plus
  a validated root ID and relative folder on the current client (up to 24). **SAVED LOCATIONS** jump directly to Games,
  Movies/Horror, etc.; the host revalidates each saved folder on every visit.
  **REMOVE SAVED** only deletes a local bookmark, never host media.
  New folders are saved automatically once a subsequent host browse succeeds.
- New *physical drives* are not auto-mounted by the client: the host must first
  expose a writable Docker bind under `/library/<slug>`. No unrestricted
  file chooser, arbitrary host path, SSH shell, or Docker restart is introduced.
- Streaming search now **drains paginated results after qBittorrent reports
  Stopped** when the advertised total exceeds retrieved rows. This directly
  addresses APIs returning only an initial 25-row page. An inaccurate upstream
  total is retried a bounded number of times and reported as incomplete rather
  than fabricated. Search plugin results remain external-source dependent.
- A host broker update (including `server/download_search.py`,
  `server/download_destinations.py`, `server/owner_games_request.py`) is
  needed for the search-drain and NEW FOLDER features; updating only a client
  will not replace a stale host broker. Keep the host update atomic with an
  independently reviewed rollback plan.

## Simplified picker and Transfers (curated server workflow)

- **There is intentionally no default download location**, no automatic
  last-used location preselection and no automatic torrent submission. Every
  Add still requires a visible current folder and explicit final confirmation.
- A compact **Favorites / Recent Locations** chooser sits above the normal
  folder list. Favorites can be toggled with a single star button, and Recents
  are recorded **only after qBittorrent acknowledges a successful Add**, up
  to eight per client. Saved places remain scoped to the owning server/user,
  store only mount IDs and relative paths, and are revalidated before use.
- Folder rows have normal folder icons and flat list styling; removable
  "Save" / "Remove Saved" toolbar clutter has been replaced by one star toggle.
- Transfers show compact filename/progress/speed rows with a keyboard-
  accessible collapsed **Actions** expander. Open state is restored after
  a queue refresh for the same torrent hash; data removal still requires
  the original separate confirmation.
- The remaining 25-result bug requires the updated **live host broker**. A
  newer client .deb alone cannot upgrade a legacy host's server/download_search.py.
  Before claiming this fixed on the actual machine, inspect owner-host-upgrade
  status and verify the host's real search stream returns more than 25 results.
