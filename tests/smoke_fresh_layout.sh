#!/usr/bin/env bash
set -euo pipefail

# Real installed (or built) GTK binary, disposable home, DBus and X server.
# Exercises first-run startup at a large monitor and a low-resolution client.
# No server enrollment, SSH pairing or customer configuration is involved.
cd "$(dirname "$0")/.."
export NOW_BINARY="${NOW_BINARY:-./build/optiplex-desk}"

test -x "$NOW_BINARY"

for screen in 3440x1440 1024x768; do
  tmp="$(mktemp -d -t now-fresh-layout.XXXXXX)"
  mkdir -p "$tmp/home" "$tmp/config" "$tmp/runtime"
  chmod 700 "$tmp/runtime"

  HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config" \
  XDG_RUNTIME_DIR="$tmp/runtime" \
  xvfb-run -a -s "-screen 0 ${screen}x24" dbus-run-session -- bash -c '
    set -euo pipefail
    logfile="$1"
    screen="$2"
    "$NOW_BINARY" >"$logfile/stdout" 2>"$logfile/stderr" &
    pid=$!
    trap "kill $pid 2>/dev/null || true; wait $pid 2>/dev/null || true" EXIT

    info=""
    for ((n=0;n<50;n++)); do
      kill -0 "$pid" 2>/dev/null || {
        echo "NOW exited before opening a window at $screen" >&2
        tail -30 "$logfile/stderr" >&2
        exit 1
      }
      info="$(xwininfo -name "OptiPlex Now" 2>/dev/null || true)"
      [[ -n "$info" ]] && break
      sleep .1
    done
    [[ -n "$info" ]] || {
      echo "No NOW dashboard window at $screen" >&2
      exit 1
    }
    width="$(awk "/^[[:space:]]*Width:/{print \$2}" <<<"$info")"
    height="$(awk "/^[[:space:]]*Height:/{print \$2}" <<<"$info")"
    IFS=x read -r maxw maxh <<<"$screen"

    # The user explicitly requested a compact normal window even on an
    # ultrawide monitor. Each page has its own scrolling container; size
    # should be comfortable without filling a substantial part of the screen.
    if [[ "$screen" == "3440x1440" ]]; then
      [[ "$width" -ge 600 && "$width" -le 740 &&
         "$height" -ge 470 && "$height" -le 590 ]] || {
        echo "Ultrawide initial window not compact: ${width}x${height}" >&2
        exit 1
      }
    else
      [[ "$width" -ge 600 && "$width" -le 740 &&
         "$height" -ge 470 && "$height" -le 590 ]] || {
        echo "Notebook initial window not compact: ${width}x${height}" >&2
        exit 1
      }
    fi
    [[ "$width" -le "$maxw" && "$height" -le "$maxh" ]] || {
      echo "Dashboard clipped by monitor at $screen: ${width}x${height}" >&2
      exit 1
    }
    # A fresh launch should not create or overwrite a stored connection.
    [[ ! -f "$XDG_CONFIG_HOME/optiplex-desk/config.ini" ]] || {
      echo "Fresh startup wrote a connection file before setup" >&2
      exit 1
    }
    echo "Fresh GUI: $screen -> ${width}x${height}; empty profile preserved."
  ' bash "$tmp" "$screen"
  # GVfs can briefly recreate runtime entries while DBus terminates.
  # Retry only within our disposable test directory, never a user's HOME.
  cleaned=0
  for attempt in 1 2 3 4 5; do
    if rm -rf -- "$tmp" 2>/dev/null && [[ ! -e "$tmp" ]]; then
      cleaned=1
      break
    fi
    sleep 0.2
  done
  [[ "$cleaned" -eq 1 ]] || { echo "Could not clean disposable GUI test directory" >&2; exit 1; }
done
