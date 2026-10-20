#!/usr/bin/env bash
set -euo pipefail

# Test actual Gtk launcher instance handoff without touching a real user's lock,
# home, desktop, or Wolf service.
cd "$(dirname "$0")/.."
# Set NOW_BINARY to validate a package installed under /usr/bin instead of a build artifact.
export NOW_BINARY="${NOW_BINARY:-./build/optiplex-desk}"
tmp="$(mktemp -d -t now-instance.XXXXXX)"
cleanup() {
  # A GTK/GVfs child can briefly create home files while its D-Bus session
  # is shutting down; tolerate that teardown race in disposable test data.
  for attempt in 1 2 3 4 5; do
    if rm -rf -- "$tmp" 2>/dev/null && [[ ! -e "$tmp" ]]; then
      return 0
    fi
    sleep 0.2
  done
  rm -rf -- "$tmp"
}
trap cleanup EXIT
mkdir -p "$tmp/home" "$tmp/config" "$tmp/runtime" "$tmp/blocked"
chmod 700 "$tmp/runtime" "$tmp/blocked"
printf 'do not modify\n' > "$tmp/untouched"
ln -s "$tmp/untouched" "$tmp/blocked/optiplex-now.lock"

HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config" XDG_RUNTIME_DIR="$tmp/runtime" \
xvfb-run -a dbus-run-session -- bash -c '
  set -euo pipefail
  temp="$1"
  "$NOW_BINARY" >"$temp/first.log" 2>&1 &
  pid=$!
  trap "kill $pid 2>/dev/null || true; wait $pid 2>/dev/null || true" EXIT

  ready=0
  for ((i=0;i<70;i++)); do
    kill -0 "$pid" 2>/dev/null || {
      echo "First NOW process unexpectedly exited" >&2
      tail -35 "$temp/first.log" >&2
      exit 1
    }
    if [[ -f "$XDG_RUNTIME_DIR/optiplex-now.lock" ]] &&
       [[ "$(cat "$XDG_RUNTIME_DIR/optiplex-now.lock")" = "$pid" ]] &&
       xwininfo -root -tree 2>/dev/null | grep -Fq "OptiPlex Now"; then
      ready=1
      break
    fi
    sleep 0.1
  done
  [[ "$ready" = 1 ]] || {
    echo "First NOW launcher failed lock/window startup" >&2
    tail -35 "$temp/first.log" >&2
    exit 1
  }

  # Second launcher must notify the first, exit quickly, and never replace it.
  timeout 6s "$NOW_BINARY" >"$temp/second.log" 2>&1
  kill -0 "$pid"
  [[ "$(cat "$XDG_RUNTIME_DIR/optiplex-now.lock")" = "$pid" ]]
  [[ "$(stat -c "%a" "$XDG_RUNTIME_DIR/optiplex-now.lock")" = 600 ]]

  # A hostile or corrupt lock must stop the app instead of spawning unlocked.
  if XDG_RUNTIME_DIR="$temp/blocked" timeout 6s "$NOW_BINARY" \
       >"$temp/blocked.log" 2>&1; then
    echo "NOW ran even though its lock path was a symlink" >&2
    exit 1
  fi
  grep -q "Could not open instance lock" "$temp/blocked.log"
  [[ "$(cat "$temp/untouched")" = "do not modify" ]]
  kill -0 "$pid"
  echo "NOW instance test passed: one GTK window, duplicate handoff, secure lock refusal."
' bash "$tmp"
