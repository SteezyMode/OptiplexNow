#!/usr/bin/env bash
set -euo pipefail

# Installed-package test: real host scanner, planner and GTK UI; no Docker mutations.
cd "$(dirname "$0")/.."
helper="/usr/lib/optiplex-now/now-host-setup"
preflight="/usr/lib/optiplex-now/host_preflight.py"
plan="/usr/lib/optiplex-now/host_plan.py"
services="/usr/lib/optiplex-now/host_services.py"
adoption="/usr/lib/optiplex-now/host_adoption.py"
test -x "$helper"
test -r "$preflight"
test -r "$plan"
test -r "$services"
test -r "$adoption"

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

# Inspect an intentionally absent/disposable Wolf config only; no real owner data.
scratch="$(mktemp -d -t now-wolf-readiness.XXXXXX)"
python3 /usr/lib/optiplex-now/host_games_readiness.py --wolf-root "$scratch" |
 python3 -c '
import json,sys
r=json.load(sys.stdin)
assert r["state"] == "wolf_config_pending"
assert r["first_game_verified"] is False
assert r["steam_login_verified"] is False
'
rm -rf "$scratch"

# Read-only dependency review. NEVER install Docker on a CI runner.
test -x /usr/lib/optiplex-now/host_dependencies.py
python3 /usr/lib/optiplex-now/host_dependencies.py --check | python3 -c '
import json,sys
r=json.load(sys.stdin)
assert r["changes_performed"] is False
assert r["installable"] in (True,False)
assert r["packages"] == ["docker.io","docker-compose-v2"]
'

# Docker service inventory is read-only. It may report Docker unavailable on CI.
python3 "$services" --json | python3 -c '
import json, sys
r=json.load(sys.stdin)
assert r["tool"] == "now-host-services"
assert r["read_only"] is True
assert r["changes_performed"] is False
assert r["may_adopt"] is False
assert set(r["services"]) == {"wolf","jellyfin","qbittorrent","gluetun"}
assert r["downloads"]["vpn_egress_verified"] is False
assert r["downloads"]["killswitch_verified"] is False
'

# This recommendation cannot approve adoption or installation, even when
# the Docker inventory sees the whole service stack.
python3 "$adoption" --json | python3 -c '
import json, sys
r=json.load(sys.stdin)
assert r["tool"] == "now-host-adoption-plan"
assert r["read_only"] is True
assert r["changes_performed"] is False
assert r["may_adopt"] is False
assert r["may_install"] is False
assert set(r["services"]) == {
    "wolf", "jellyfin", "qbittorrent", "gluetun", "downloader_network"}
'

# Run the installed NVIDIA preflight against actual CI host resources.
# This runner does not certify GPU/video readiness or invoke Docker installation.
test -r /usr/lib/optiplex-now/nvidia-driver.Dockerfile
test -r /usr/lib/optiplex-now/host_nvidia.py
python3 /usr/lib/optiplex-now/host_install.py \
  --check --gpu nvidia --render-node /dev/dri/renderD128 |
  python3 -c '
import json, sys
r=json.load(sys.stdin)
assert r["gpu"] == "nvidia"
assert r["decision"] in ("blocked", "candidate_after_admin_check", "candidate")
assert "nvidia_driver_version" in r
'
# The root entrypoint must reject missing Nvidia SHA before touching /run,
# images, volumes or Docker (even when invoked as root on CI).
if sudo /usr/lib/optiplex-now/host_install.py --install \
  --gpu nvidia --render-node /dev/dri/renderD128 \
  --image-digest "sha256:$(printf "%064d" 0)" \
  --confirm INSTALL-WOLF > /dev/null 2>&1; then
  echo "NVIDIA install accepted without required installer checksum" >&2
  exit 1
fi

tmp="$(mktemp -d -t now-host-ui.XXXXXX)"
# GVfs can keep its per-test FUSE runtime mount alive briefly after DBus exits.
# Do not let teardown of an ephemeral CI directory turn a successful host
# readiness test into a failure, or replace a real GTK failure with rm's code.
cleanup_host_ui() {
  local status=$?
  trap - EXIT
  if ! rm -rf "$tmp" 2>/dev/null; then
    echo "CI-only GVfs runtime remained mounted; ephemeral runner will discard it." >&2
  fi
  exit "$status"
}
trap cleanup_host_ui EXIT
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
