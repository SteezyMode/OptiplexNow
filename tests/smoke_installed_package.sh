#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Intended only for ephemeral CI runners; NEVER run on a user's active OptiPlex.
mapfile -t packages < <(find dist -maxdepth 1 -type f -name 'OptiPlex-Now_*_amd64.deb')
[[ "${#packages[@]}" -eq 1 ]] || { echo "Expected one versioned NOW package" >&2; exit 1; }
package="$(realpath "${packages[0]}")"
version="$(dpkg-deb -f "$package" Version)"
[[ "$(dpkg-deb -f "$package" Package)" = "optiplex-now" ]]
# A client .deb must not silently install a broker, rewrite host SSH rules,
# activate udev policy or enable services. All host adoption is owner-initiated.
# Inspect the built archive, not only the source packaging script.
if dpkg-deb --ctrl-tarfile "$package" | tar -tf - |
  grep -E '^\./(preinst|postinst|prerm|postrm)$'; then
  echo "A package maintainer script requires owner safety review" >&2
  exit 1
fi
if dpkg-deb --fsys-tarfile "$package" | tar -tf - |
  grep -E '^\./(etc/|run/|var/|usr/lib/systemd/system/)'; then
  echo "Package must not silently deploy host policy or services" >&2
  exit 1
fi
export DEBIAN_FRONTEND=noninteractive
sudo apt-get install -y "$package"
[[ "$(dpkg-query -W -f='${Version}' optiplex-now)" = "$version" ]]
test -x /usr/bin/optiplex-now
test -x /usr/lib/optiplex-now/optiplex-now-backup
test -x /usr/lib/optiplex-now/now-ssh-askpass
test -r /usr/lib/optiplex-now/ssh-authorize.py
test -r /usr/lib/optiplex-now/now-theme.css
test -r /usr/lib/optiplex-now/now_theme.py
# Downloads clients must resolve their shared helper FROM the actual installed
# package directory, not from a source-tree PYTHONPATH or a developer checkout.
# Invalid CLI invocations exit before touching SSH, accounts or host services.
test -r /usr/lib/optiplex-now/download_owner_transport.py
/usr/bin/python3 - <<'PY'
from pathlib import Path
import subprocess

directory = Path("/usr/lib/optiplex-now")
for filename, message in (
    ("download-search-client.py", "Search unavailable."),
    ("download-queue-client.py", "Queue unavailable."),
    ("download-operations-client.py", "Owner download request unavailable."),
):
    program = directory / filename
    assert program.is_file(), filename
    child = subprocess.run(["/usr/bin/python3", str(program)],
                           capture_output=True, text=True,
                           check=False, timeout=6)
    assert child.returncode == 1, (filename, child.returncode)
    assert message in (child.stdout + child.stderr), (
        filename, child.stdout, child.stderr)
    assert "ModuleNotFoundError" not in child.stderr, filename
PY
python3 -c 'from pathlib import Path; f=Path("/usr/lib/optiplex-now/now_theme.py"); compile(f.read_text(), str(f), "exec")'
test -x /usr/lib/optiplex-now/now-host-setup
test -r /usr/lib/optiplex-now/host_preflight.py
test -r /usr/lib/optiplex-now/host_plan.py
test -x /usr/lib/optiplex-now/host_install.py
test -x /usr/lib/optiplex-now/host_dependencies.py
test -r /usr/lib/optiplex-now/host_storage_review.py
test -r /usr/lib/optiplex-now/host_games_readiness.py
test -x /usr/lib/optiplex-now/owner-host-upgrade.py
# Search engine artifacts are bundled for later owner-approved provisioning,
# but must never be activated during installation of the desktop .deb.
test -r /usr/share/optiplex-now/search/bruiser_apibay.py
test -r /usr/share/optiplex-now/search/bruiser_bitsearch.py
test -r /usr/share/optiplex-now/search/manage_apibay_search.py
test -r /usr/share/optiplex-now/search/manage_dual_search.py
test -r /usr/share/doc/optiplex-now/search-providers.md
python3 - <<'PY'
from pathlib import Path
import hashlib
root=Path("/usr/share/optiplex-now/search")
for name in ("bruiser_apibay.py", "bruiser_bitsearch.py",
             "manage_apibay_search.py","manage_dual_search.py"):
    source=(root/name).read_bytes()
    compile(source,name,"exec")
# Legacy API Bay-only manager remains bundled as a historical fallback.
# Its SHA pins v1.1; this new package's provider source is deliberately v1.3.
legacy=(root/"manage_apibay_search.py").read_text()
assert 'SOURCE_GIT_BLOB = "871a80678abdbd302a98722811171c446e4f7e62"' in legacy
for name, expected in (("bruiser_apibay.py","class bruiser_apibay"),
                       ("bruiser_bitsearch.py","class bruiser_bitsearch")):
    assert expected in (root/name).read_text()
manager=(root/"manage_dual_search.py").read_text()
for name in ("bruiser_apibay","bruiser_bitsearch"):
    data=(root/(name+".py")).read_bytes()
    source_hash=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
    assert f'"{name}": "{source_hash}"' in manager, "Dual-search manager/source mismatch"

PY
for f in owner_games_ssh.py owner_games_request.py owner_games_enroll.py download_inventory.py download_queue.py download_search.py download_manage.py download_destinations.py media_endpoint.py; do
  test -r "/usr/lib/optiplex-now/owner-bridge/server/$f"
done
for f in owner_access.py owner_launch.py owner_lobby.py owner_host_pilot.py wolf_docker_adapter.py wolf_socket_adapter.py; do
  test -r "/usr/lib/optiplex-now/owner-bridge/src/$f"
done
PYTHONPATH="/usr/lib/optiplex-now/owner-bridge/server:/usr/lib/optiplex-now/owner-bridge/src" python3 -c 'import owner_games_ssh, owner_games_request, owner_games_enroll, download_search, download_manage'

# Exercise the ACTUAL installed owner bridge over isolated loopback/temporary
# credentials; source-tree imports and host-network access are prohibited.
/usr/bin/python3 tests/smoke_installed_owner_bridge.py
test -r /usr/lib/optiplex-now/media_endpoint.py
test -x /usr/lib/optiplex-now/host_media_adoption.py
test -x /usr/lib/optiplex-now/host_jellyfin_install.py
test -x /usr/lib/optiplex-now/host-jellyfin-new-ui.py
test -x /usr/lib/optiplex-now/host-media-setup.py
test -r /usr/lib/optiplex-now/host_stage.py
test -r /usr/lib/optiplex-now/host_nvidia.py
test -r /usr/lib/optiplex-now/nvidia-driver.Dockerfile
test -r /usr/share/doc/optiplex-now/LICENSE-nvidia-driver-upstream.txt
[[ "$(readlink /usr/bin/optiplex-desk)" = "optiplex-now" ]]
desktop-file-validate /usr/share/applications/optiplex-now.desktop
desktop-file-validate /usr/share/applications/optiplex-desk.desktop

# Run the actual installed binary under disposable Xvfb/DBus/home/runtime directories.
NOW_BINARY=/usr/bin/optiplex-now bash tests/smoke_gtk.sh
NOW_BINARY=/usr/bin/optiplex-now bash tests/smoke_fresh_layout.sh
NOW_BINARY=/usr/bin/optiplex-now bash tests/smoke_instance.sh
NOW_ASKPASS=/usr/lib/optiplex-now/now-ssh-askpass bash tests/smoke_ssh_askpass.sh
bash tests/smoke_host_readiness.sh
bash tests/smoke_host_media_ui.sh
bash tests/smoke_host_jellyfin_new_ui.sh
echo "NOW installed-package acceptance passed: Debian install, desktop files, GUI and lock."
