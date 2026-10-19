#!/usr/bin/env bash
set -euo pipefail

# Launch the built NOW UI inside disposable X11 and home directories.
# This is a UI startup smoke test, not a Wolf or Moonlight integration test.
cd "$(dirname "$0")/.."
# Set NOW_BINARY to validate a package installed under /usr/bin instead of a build artifact.
export NOW_BINARY="${NOW_BINARY:-./build/optiplex-desk}"
tmp="$(mktemp -d -t now-gtk-smoke.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/home" "$tmp/config" "$tmp/runtime"
chmod 700 "$tmp/runtime"

HOME="$tmp/home" \
XDG_CONFIG_HOME="$tmp/config" \
XDG_RUNTIME_DIR="$tmp/runtime" \
xvfb-run -a dbus-run-session -- bash -c '
  set -euo pipefail
  "$NOW_BINARY" > "$1/stdout.log" 2> "$1/stderr.log" &
  pid=$!
  trap "kill $pid 2>/dev/null || true; wait $pid 2>/dev/null || true" EXIT
  for ((i=0;i<25;i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "NOW GTK application exited before a window opened" >&2
      tail -40 "$1/stderr.log" >&2 || true
      exit 1
    fi
    if xwininfo -root -tree 2>/dev/null | grep -F "OptiPlex Now" >/dev/null; then
      echo "NOW GTK window appeared under isolated Xvfb display."
      exit 0
    fi
    sleep .2
  done
  echo "NOW did not display a window inside 5 seconds" >&2
  tail -40 "$1/stderr.log" >&2 || true
  exit 1
' bash "$tmp"
