#!/bin/sh
# SFTP bridge for COSMIC Files: turn a remote URI into a GVFS mount path.
# No private keys or credentials are stored here. Called with validated args.
set -u

host=${1:-}
user=${2:-}
case "$host" in ''|*[!a-zA-Z0-9._:-]*) exit 2;; esac
case "$user" in ''|*[!a-zA-Z0-9._-]*) exit 2;; esac
uri="sftp://$user@$host/"

fail() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send 'OptiPlex Now | Files' "$1"
  elif command -v zenity >/dev/null 2>&1; then
    zenity --error --title='OptiPlex Now | Files' --text="$1" >/dev/null 2>&1
  fi
  printf 'OptiPlex Now: %s\n' "$1" >&2
  exit 1
}

command -v gio >/dev/null 2>&1 || fail 'SFTP support needs GIO and GVFS.'
# A pre-mounted share returns a nonzero status on some GLib versions.
mount_output=$(gio mount "$uri" 2>&1) || {
  case "$mount_output" in
    *already\ mounted*|*Already\ mounted*) ;;
    *) fail 'SFTP connection failed. Check Tailscale, SSH and GVFS.' ;;
  esac
}

mount_root="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/gvfs"
# Some desktops create the FUSE directory a moment after the mount succeeds.
n=0
mount_dir=''
while [ "$n" -lt 12 ]; do
  for candidate in "$mount_root"/sftp:*; do
    [ -d "$candidate" ] || continue
    name=${candidate##*/}
    spec=${name#sftp:}
    case ",$spec," in *,host="$host",*) ;; *) continue;; esac
    case ",$spec," in
      *,user=*,*) case ",$spec," in *,user="$user",*) ;; *) continue;; esac ;;
    esac
    mount_dir=$candidate
    break
  done
  [ -n "$mount_dir" ] && break
  n=$((n+1)); sleep 0.25
done
[ -n "$mount_dir" ] || fail 'SFTP mounted but folder is unavailable. Check gvfs-fuse.'

if command -v cosmic-files >/dev/null 2>&1; then
  exec cosmic-files "$mount_dir"
fi
if command -v thunar >/dev/null 2>&1; then
  exec thunar "$mount_dir"
fi
if command -v nautilus >/dev/null 2>&1; then
  exec nautilus "$mount_dir"
fi
if command -v dolphin >/dev/null 2>&1; then
  exec dolphin "$mount_dir"
fi
exec gio open "$mount_dir"
