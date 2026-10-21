#!/usr/bin/env bash
set -euo pipefail

# Installed-package test: real host scanner, planner and GTK UI; no Docker mutations.
cd "$(dirname "$0")/.."
helper="/usr/lib/optiplex-now/now-host-setup"
preflight="/usr/lib/optiplex-now/host_preflight.py"
plan="/usr/lib/optiplex-now/host_plan.py"
test -x "$helper"
test -r "$preflight"
test -r "$plan"

python3 "$preflight" --json | python3 -c '
import json, sys
r=json.load(sys.stdin)
assert r["tool"] == "now-host-preflight"
assert r["read_only"] is True
assert r["verified_streaming"] is False
'
python3 "$plan" --json | python3 -c '
import json, sys
r=json.load(sys.stdin)
assert r["tool"] == "now-host-plan"
assert r["decision"] == "blocked"
assert r["may_apply"] is False
assert r["changes_performed"] is False
'

tmp="$(mktemp -d -t now-host-ui.XXXXXX)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/home" "$tmp/config" "$tmp/runtime"
chmod 700 "$tmp/runtime"
export NOW_HOST_SETUP="$helper"
HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config" XDG_RUNTIME_DIR="$tmp/runtime" \
xvfb-run -a dbus-run-session -- bash -c '
  set -euo pipefail
  "$NOW_HOST_SETUP" --check-on-open >"$1/stdout.log" 2>"$1/stderr.log" &
  pid=$!
  trap "kill $pid 2>/dev/null || true; wait $pid 2>/dev/null || true" EXIT
  for ((i=0; i<100; i++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "Host Setup closed unexpectedly" >&2
      cat "$1/stderr.log" >&2 || true
      exit 1
    fi
    if xwininfo -root -tree 2>/dev/null |
      grep -F "OptiPlex NOW | Server Review Complete" >/dev/null; then
      echo "NOW installed Host Setup completed real local read-only scan in GTK."
      exit 0
    fi
    if xwininfo -root -tree 2>/dev/null |
      grep -F "OptiPlex NOW | Server Review Incomplete" >/dev/null; then
      echo "NOW Host Setup returned incomplete review" >&2
      cat "$1/stderr.log" >&2 || true
      exit 1
    fi
    sleep .2
  done
  echo "Host Setup GUI did not finish within test window" >&2
  cat "$1/stderr.log" >&2 || true
  exit 1
' bash "$tmp"
