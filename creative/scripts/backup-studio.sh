#!/usr/bin/env bash
# Daily-capable, incremental backup of ONLY StudioProjects.
# Run as optiplex. This script does not create or enable a systemd timer.
set -Eeuo pipefail
umask 077

SOURCE=/home/optiplex/StudioProjects
DRIVE=/mnt/2TB
BASE="$DRIVE/StudioBackups"
SNAPS="$BASE/snapshots"
KEEP=14

[[ "$(id -un)" == "optiplex" ]] || { echo "ERROR: run as optiplex, not root" >&2; exit 1; }
[[ -d "$SOURCE" && ! -L "$SOURCE" ]] || { echo "ERROR: StudioProjects missing or symlinked" >&2; exit 1; }
[[ "$(findmnt --mountpoint "$DRIVE" -n -o FSTYPE 2>/dev/null)" == "ext4" ]] || {
  echo "ERROR: /mnt/2TB is not an ext4 mount; refusing to write to system disk" >&2
  exit 1
}
[[ "$(stat -c %d "$SOURCE")" != "$(stat -c %d "$DRIVE")" ]] || {
  echo "ERROR: source and backup resolve to same filesystem" >&2
  exit 1
}
[[ ! -L "$BASE" && ! -L "$SNAPS" ]] || { echo "ERROR: backup location is a symlink" >&2; exit 1; }

mkdir -p -- "$SNAPS"
chmod 700 "$BASE" "$SNAPS"
exec 9>"$BASE/.studio-backup.lock"
flock -n 9 || { echo "Backup already running; exiting" >&2; exit 1; }

stamp=$(date '+%Y-%m-%d_%H%M%S')
partial="$SNAPS/.partial-$stamp-$$"
finished="$SNAPS/$stamp"
[[ ! -e "$finished" ]] || { echo "ERROR: duplicate snapshot name" >&2; exit 1; }

previous=$(find "$SNAPS" -mindepth 1 -maxdepth 1 -type d -name '20??-??-??_??????' -printf '%f\n' | LC_ALL=C sort | tail -n 1)
args=()
if [[ -n "$previous" ]]; then
  args+=("--link-dest=$SNAPS/$previous")
fi

cleanup() {
  if [[ -n "${partial:-}" && -d "$partial" ]]; then
    rm -rf -- "$partial"
  fi
}
trap cleanup EXIT
mkdir -- "$partial"
# New destination per run; linked files are backed up snapshots, never live files.
# Normalize backup group/other write bits, leaving source permissions intact.
rsync -a --chmod=go-w "${args[@]}" -- "$SOURCE/" "$partial/"
mv -- "$partial" "$finished"
partial=''
echo "CREATED: $finished"

# Retain the 14 newest *completed* snapshots, newest first.
mapfile -t snapshots < <(
  find "$SNAPS" -mindepth 1 -maxdepth 1 -type d -name '20??-??-??_??????' -printf '%f\n' | LC_ALL=C sort -r
)
for ((i=KEEP; i<${#snapshots[@]}; i++)); do
  old="${snapshots[i]}"
  [[ "$old" =~ ^20[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{6}$ ]] || exit 1
  rm -rf -- "$SNAPS/$old"
  echo "PRUNED: $old"
done
echo "SNAPSHOT_COUNT: $(find "$SNAPS" -mindepth 1 -maxdepth 1 -type d -name '20??-??-??_??????' | wc -l)"
echo "BACKUP_BYTES: $(du -sh "$SNAPS" | cut -f1)"
