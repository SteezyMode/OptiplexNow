# Downloads: native file chooser and existing-host storage

PR #242, unreleased. No live host mounts, Steam/Wolf sessions, media files,
Jellyfin libraries or authorized SSH keys are changed by these commits.

## File picker

Selecting a torrent opens **GtkFileChooserDialog** with
`GTK_FILE_CHOOSER_ACTION_SELECT_FOLDER`, using the same native GTK/Thunar-like
folder selector used by normal Linux desktop applications. It replaces the
previous proprietary directory-list interface. The OS chooser handles folders,
Places, bookmarks/favorites, file manager shortcuts, and creating folders;
no duplicate custom favorites sidebar or hidden qBittorrent mount dropdown
is involved in the user-facing flow.

The application runs on other machines as well as on the OptiPlex. Its normal
client-local chooser cannot see server drives, so GTK/GIO uses a remote SFTP
location (`sftp://<owner>@<host>/`). Users browse all folders that account can
see on the actual OptiPlex host, including its /media, /mnt and home folders,
subject to ordinary Unix permissions. This connection uses the user's normal
SSH/SFTP credentials. The restricted NOW owner-device command key **cannot**
serve SFTP. A normal SSH/SFTP login must be configured separately if not
already present. `gvfs-backends` is a package dependency. Bookmarks are the
native chooser's GTK/GVfs bookmarks, not application-proprietary favorites.

Cancel returns directly to existing search results. Accept submits only after
explicit user action. Local file:// URIs, SFTP locations on other machines,
traversal segments and malformed paths are rejected before submission.

## Downloading is separate from browsing

A native SFTP chooser can display all mounted host drives. qBittorrent,
however, runs inside Docker and may only write folders exposed through its
writable bind mounts. The owner broker maps the selected *host* path back to
its longest matching verified qBittorrent source bind, converts that to the
real container destination, checks the target's directory chain without
following symlinks, verifies the downloader user can write, and submits the
selected magnet explicitly. An unmounted drive **can be browsed** via SFTP
but cannot be downloaded to until an authorized administrator makes it
available to the existing qBittorrent container. This code does not
silently restart Docker or auto-mount the server's OS filesystem. The older
'torrent-downloads' mount is not a special/default drive in the native chooser.

The host implementation is accessed only via the enrolled owner-device
restricted SSH broker (`downloads_add_path`). No arbitrary shell command,
client-supplied Docker mount, root privilege or raw qBittorrent endpoint is
added. Existing library paths, permissions and files are preserved.

## Other Downloads functionality

- Search pagination continues beyond qBittorrent's first batch where the
  updated host broker and plugins support it.
- Transfers rows use compact summaries and native right-click action menus,
  including separate Remove (keep files) and confirmed Delete Files.
- The latter can only delete data from a verified writable qBittorrent mount
  for one exact torrent hash; it cannot select arbitrary host files.

## Install both ends

The `.deb` carries both the GTK client and the package-owned host broker.
Installing it only on the Mac mini/MacBook will **not** activate the new
`downloads_add_path` host capability. Install the same package on the
OptiPlex. If the restricted handler is still using the legacy per-user code,
review with

    python3 /usr/lib/optiplex-now/owner-host-upgrade.py --check

Then, only if the status is `ready`, activate with an SSH-key backup:

    python3 /usr/lib/optiplex-now/owner-host-upgrade.py --activate --confirm-owner-upgrade

For `up_to_date`, no activation is needed. For `blocked` or
`not_configured`, do not force it. An opt-in host SFTP account / client
connection is independent of owner-device enrollment.

## Acceptance

Automated tests cover URI validation, SFTP host identity, host path escape
denial, root/mount mapping, downloader permission checks and package smoke
tests. Manual acceptance must verify normal GTK SFTP authentication on the
actual Mac mini, that all four mounted OptiPlex drives can be browsed, that
an existing *writable qBittorrent mount* accepts Add Torrent, and that an
unmounted host drive fails to submit without modifying files.
