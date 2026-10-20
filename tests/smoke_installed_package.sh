#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Intended only for ephemeral CI runners; NEVER run on a user's active OptiPlex.
mapfile -t packages < <(find dist -maxdepth 1 -type f -name 'OptiPlex-Now_*_amd64.deb')
[[ "${#packages[@]}" -eq 1 ]] || { echo "Expected one versioned NOW package" >&2; exit 1; }
package="$(realpath "${packages[0]}")"
version="$(dpkg-deb -f "$package" Version)"
[[ "$(dpkg-deb -f "$package" Package)" = "optiplex-now" ]]
export DEBIAN_FRONTEND=noninteractive
sudo apt-get install -y "$package"
[[ "$(dpkg-query -W -f='${Version}' optiplex-now)" = "$version" ]]
test -x /usr/bin/optiplex-now
test -x /usr/lib/optiplex-now/optiplex-now-backup
test -x /usr/lib/optiplex-now/find-now-hosts.py
test -x /usr/bin/optiplex-now-host-agent
test -x /usr/lib/optiplex-now/now-host-agent
# CLI help only; no listener starts or daemon configuration changes.
optiplex-now-host-agent --help >/dev/null
python3 /usr/lib/optiplex-now/find-now-hosts.py --help >/dev/null
test -x /usr/bin/optiplex-now-preflight
test -x /usr/lib/optiplex-now/server-preflight
optiplex-now-preflight --json | python3 -c 'import json,sys; data=json.load(sys.stdin); assert data["scope"] == "this_computer_read_only"; assert data["streaming_ready"] == "not_tested"; assert data["changes_made"] is False'
optiplex-now-preflight --json --backend sunshine | python3 -c 'import json,sys; p=json.load(sys.stdin)["install_plan"]; assert p["backend"] == "sunshine" and p["can_install"] is False and p["phase"] == "advisory_only"'
optiplex-now-preflight --json --backend wolf | python3 -c 'import json,sys; p=json.load(sys.stdin)["install_plan"]; assert p["backend"] == "wolf" and p["can_install"] is False and p["needs_explicit_approval"] is True'
[[ "$(readlink /usr/bin/optiplex-desk)" = "optiplex-now" ]]
desktop-file-validate /usr/share/applications/optiplex-now.desktop
desktop-file-validate /usr/share/applications/optiplex-desk.desktop

# Run the actual installed binary under disposable Xvfb/DBus/home/runtime directories.
NOW_BINARY=/usr/bin/optiplex-now bash tests/smoke_gtk.sh
NOW_BINARY=/usr/bin/optiplex-now bash tests/smoke_instance.sh
echo "NOW installed-package acceptance passed: Debian install, desktop files, GUI and lock."
