# Downloads UI and owner storage access (PR #242)

This is an unreleased test build. Development and CI never modify the live
OptiPlex media folders, qBittorrent container, SSH keys or running clients.

## Interface

- Transfers are compact summaries (name, progress, state, speed, ETA, seeds).
  Right click a row, or press Shift+F10 when focused, for native Pause/Resume,
  Reannounce, Recheck, View Files, Remove (keep files) and Delete Files.
  Destructive deletion requires explicit confirmation and a verified exact
  torrent hash. No permanent ACTIONS rows or nested action panels.
- Search results retain sortable titles, sizes, seeders, leechers, dates and
  streamed additional result pages. Selecting a magnet enters the destination
  step in the same Downloads tab, without losing search results.
- The destination picker resembles a conventional file dialog: storage drives
  plus saved Favorites/Recents on the left, directory browsing and path on the
  right, Cancel and Add Torrent together at the bottom. A Locations toggle
  substitutes for the sidebar at narrow widths.
- No default or automatically remembered destination. Add submits only when
  the owner explicitly confirms. Cancel clears the pending magnet.
  Favoriting is opt-in; Recents are recorded after successful Add.
- Entire Downloads page scrolls. Advanced VueTorrent retains its own view.

## Existing owner storage

The host auto-discovers writable Docker *bind mounts of its verified VPN-bound
qBittorrent container*, instead of requiring the /library/<slug> naming
convention. Existing /library/<slug> IDs remain stable for previously saved
shortcuts. Other bind mounts get deterministic opaque IDs (derived from the
container mount destination), and readable display labels. Both old and new
mounts use their *actual container destination path* when adding a torrent.
The browser does not rename, reorganize, remount or move existing media.

The app does not gain arbitrary root/host filesystem access: qBittorrent can
only download into directories exposed to that container and writable by its
actual user. System paths and configuration mounts are not selectable.
Symlink traversal and .. remain prohibited, regardless of owner status.

An owner-created folder is opened relative to its real host bind path with
no-follow directory fds, then verified writable in the downloader container.
No Docker restart or mount modification is performed. Up to 24 mount entries
are recognized. A drive with no writable qBittorrent bind mount cannot be used
until exposed through Docker configuration.

## Deployment: both sides needed

The .deb includes the GTK client and the packaged restricted host broker.
Installing only on the Mac mini/MacBook does not update an older OptiPlex
forced-command SSH handler. Install the *same verified .deb* on the host, then
run as the host owner account:

    python3 /usr/lib/optiplex-now/owner-host-upgrade.py --check

If the result is `ready`, the owner can explicitly activate the package
broker with rollback backup:

    python3 /usr/lib/optiplex-now/owner-host-upgrade.py --activate --confirm-owner-upgrade

If `up_to_date`, no activation is needed. If `blocked` or
`not_configured`, do not force replacement of SSH keys. This change does
not restart qBittorrent, Wolf, Jellyfin or the VPN.

## Verification

CI runs Python negative tests for the downloader, path authorization and owner
transport, native GTK tests at 430, 1024×768, 1366×768, 1280×800 and
1920×1080, package smoke tests, and memory/UB diagnostics.

Real OptiPlex acceptance still needs owner confirmation of mount labels,
>25 search results, writable destination behavior, and explicit Delete
only against disposable test data.
