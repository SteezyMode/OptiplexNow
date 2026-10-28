#!/usr/bin/env bash
set -euo pipefail

# Installed package, separate Xvfb session and disposable user home. The
# Videos setup window's idle check is read-only; no approval is clicked.
tmp="$(mktemp -d -t now-host-videos-ui.XXXXXX)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir -p "$tmp/home" "$tmp/config" "$tmp/runtime"
chmod 700 "$tmp/runtime"
HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config" XDG_RUNTIME_DIR="$tmp/runtime" \
xvfb-run -a dbus-run-session -- bash -c '
  set -euo pipefail
  python3 /usr/lib/optiplex-now/host-media-setup.py > "$1/stdout" 2> "$1/stderr" &
  pid=$!
  trap "kill $pid 2>/dev/null || true; wait $pid 2>/dev/null || true" EXIT
  for ((i=0; i<30; i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "Host Videos GTK UI terminated during startup" >&2
      tail -40 "$1/stderr" >&2 || true
      exit 1
    fi
    if xwininfo -root -tree 2>/dev/null | grep -F "Videos Host Setup" >/dev/null; then
      echo "Host Videos setup window opened under isolated Xvfb."
      break
    fi
    sleep .2
  done
  xwininfo -root -tree | grep -F "Videos Host Setup" >/dev/null
' bash "$tmp"
test ! -e "$tmp/config/optiplex-now/media-public-endpoint.json"
echo "Host Videos UI smoke passed: no owner route created."
