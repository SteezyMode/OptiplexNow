#!/usr/bin/env bash
set -euo pipefail
# Installed on disposable CI only. This never clicks Check or Install.
tmp="$(mktemp -d -t now-new-jellyfin-ui.XXXXXX)"
# GVfs may leave a transient FUSE mount at XDG_RUNTIME_DIR/gvfs.
# CI's disposable runner will clean it up; never fail a successful GTK
# smoke test just because that mount outlives the app process.
trap 'rm -rf -- "$tmp" 2>/dev/null || true' EXIT
mkdir -p "$tmp/home" "$tmp/config" "$tmp/runtime"
chmod 700 "$tmp/runtime"
HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config" XDG_RUNTIME_DIR="$tmp/runtime" \
xvfb-run -a dbus-run-session -- bash -c '
  set -euo pipefail
  /usr/bin/python3 /usr/lib/optiplex-now/host-jellyfin-new-ui.py \
    > "$1/stdout" 2> "$1/stderr" &
  pid=$!
  trap "kill $pid 2>/dev/null || true; wait $pid 2>/dev/null || true" EXIT
  for ((i=0;i<30;i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "Clean-Jellyfin GTK UI terminated during start" >&2
      tail -50 "$1/stderr" >&2 || true
      exit 1
    fi
    if xwininfo -root -tree 2>/dev/null | grep -F "New Jellyfin Host Pilot" > /dev/null; then
      echo "Clean Jellyfin setup window opened in isolated Xvfb."
      break
    fi
    sleep .2
  done
  xwininfo -root -tree | grep -F "New Jellyfin Host Pilot" > /dev/null
' bash "$tmp"
test ! -e "$tmp/config/optiplex-now/media-public-endpoint.json"
echo "Clean Jellyfin pilot GUI smoke passed: no installation or owner settings changed."
