#!/usr/bin/env bash
set -euo pipefail

# Launch the built NOW UI inside disposable X11 and home directories.
# This is a UI startup smoke test, not a Wolf or Moonlight integration test.
cd "$(dirname "$0")/.."
# Set NOW_BINARY to validate a package installed under /usr/bin instead of a build artifact.
export NOW_BINARY="${NOW_BINARY:-./build/optiplex-desk}"
tmp="$(mktemp -d -t now-gtk-smoke.XXXXXX)"
# gvfsd-fuse can outlive dbus-run-session briefly. Never recurse into an
# attached FUSE mount as part of a throwaway smoke-test cleanup.
cleanup_tmp() {
  local gvfs="$tmp/runtime/gvfs"
  for attempt in 1 2 3 4 5; do
    if ! mountpoint -q "$gvfs" 2>/dev/null; then break; fi
    if command -v fusermount3 >/dev/null 2>&1; then
      fusermount3 -u "$gvfs" 2>/dev/null || true
    elif command -v fusermount >/dev/null 2>&1; then
      fusermount -u "$gvfs" 2>/dev/null || true
    fi
    sleep 0.2
  done
  if mountpoint -q "$gvfs" 2>/dev/null; then
    echo "GTK smoke: GVFS still mounted; leaving disposable runtime for runner cleanup" >&2
    return 0
  fi
  rm -rf -- "$tmp"
}
trap cleanup_tmp EXIT
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
      break
    fi
    sleep .2
  done
  # A genuinely new profile must also show the first-run setup assistant.
  # A working Dashboard alone can mask a broken onboarding wizard.
  for ((i=0;i<50;i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "NOW exited before the fresh-client wizard appeared" >&2
      tail -40 "$1/stderr.log" >&2 || true
      exit 1
    fi
    if xwininfo -root -tree 2>/dev/null | grep -F "NOW Setup: Tailscale" >/dev/null; then
      echo "NOW first-run setup wizard opened inside an isolated profile."
      exit 0
    fi
    sleep .2
  done
  echo "First-run setup wizard did not appear within 10 seconds" >&2
  echo "X11 window tree at timeout:" >&2
  xwininfo -root -tree >&2 || true
  echo "Fresh configuration files:" >&2
  find "$XDG_CONFIG_HOME" -maxdepth 3 -type f -printf "%P\\n" >&2 || true
  tail -40 "$1/stderr.log" >&2 || true
  exit 1
' bash "$tmp"
