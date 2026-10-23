#!/usr/bin/env python3
from pathlib import Path
import os, re, shutil, subprocess

# Tagged releases use the committed version. PR validation can supply a
# distinct Debian version so installation is not confused with a release.
DEFAULT_VERSION = "1.19.0"
version = os.environ.get("NOW_PACKAGE_VERSION", DEFAULT_VERSION)
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:\+pr[0-9]+\.[0-9]+)?", version):
    raise SystemExit("Invalid NOW_PACKAGE_VERSION")

root=Path(__file__).resolve().parent
out=root/'dist'; out.mkdir(exist_ok=True)
pkg=root/f'build/pkg/optiplex-now_{version}_amd64'
if pkg.exists(): shutil.rmtree(pkg)
for sub in ('DEBIAN','usr/bin','usr/lib/optiplex-now','usr/share/applications','usr/share/doc/optiplex-now'):
 (pkg/sub).mkdir(parents=True,exist_ok=True)
(pkg/'DEBIAN').chmod(0o755)
shutil.copy2(root/'build/optiplex-desk',pkg/'usr/bin/optiplex-now')
shutil.copy2(root/'build/optiplex-now-backup',pkg/'usr/lib/optiplex-now/optiplex-now-backup')
shutil.copy2(root/'src/open-remote-files.sh',pkg/'usr/lib/optiplex-now/open-remote-files')
(pkg/'usr/lib/optiplex-now/open-remote-files').chmod(0o755)
shutil.copy2(root/'src/open-web-gaming-admin.py',pkg/'usr/lib/optiplex-now/open-web-gaming-admin')
(pkg/'usr/lib/optiplex-now/open-web-gaming-admin').chmod(0o755)
shutil.copy2(root/'src/server-profile.py',pkg/'usr/lib/optiplex-now/server-profile.py')
shutil.copy2(root/'src/find-servers.py',pkg/'usr/lib/optiplex-now/find-servers.py')
shutil.copy2(root/'src/tailscale-status.py',pkg/'usr/lib/optiplex-now/tailscale-status.py')
shutil.copy2(root/'src/tailscale-install.py',pkg/'usr/lib/optiplex-now/tailscale-install.py')
shutil.copy2(root/'src/ssh-authorize.py',pkg/'usr/lib/optiplex-now/ssh-authorize.py')
# Read-only host diagnostics and GTK review; no server installer or privileges.
shutil.copy2(root/'build/now-host-setup',pkg/'usr/lib/optiplex-now/now-host-setup')
(pkg/'usr/lib/optiplex-now/now-host-setup').chmod(0o755)
for host_module in ('host_preflight.py', 'host_plan.py', 'host_services.py', 'host_adoption.py', 'host_stage.py', 'host_install.py', 'host_nvidia.py'):
 shutil.copy2(root/'server'/host_module,pkg/'usr/lib/optiplex-now'/host_module)
shutil.copy2(root/'server/nvidia-driver.Dockerfile', pkg/'usr/lib/optiplex-now/nvidia-driver.Dockerfile')
shutil.copy2(root/'server/LICENSE-nvidia-driver-upstream.txt', pkg/'usr/share/doc/optiplex-now/LICENSE-nvidia-driver-upstream.txt')
(pkg/'usr/lib/optiplex-now/host_install.py').chmod(0o755)
shutil.copy2(root/'build/now-ssh-askpass',pkg/'usr/lib/optiplex-now/now-ssh-askpass')
(pkg/'usr/lib/optiplex-now/now-ssh-askpass').chmod(0o755)
shutil.copy2(root/'src/wolf-pair-client.py',pkg/'usr/lib/optiplex-now/wolf-pair-client.py')
# Restricted per-device Games SSH transport. This is NOT a host admin key. Host enrollment and authorization
# remain explicit owner actions.
shutil.copy2(root/'src/owner-games-client.py',pkg/'usr/lib/optiplex-now/owner-games-client.py')
# Owner-only alpha enrollment: client stage request, local host approval.
# Never install a new host authorized_keys line or grant access on package setup.
for name in ('owner-enroll-client.py', 'owner-enroll-ui.py', 'owner-approvals-ui.py'):
 shutil.copy2(root/'src'/name, pkg/'usr/lib/optiplex-now'/name)
 (pkg/'usr/lib/optiplex-now'/name).chmod(0o755)
bridge=pkg/'usr/lib/optiplex-now/owner-bridge'
(bridge/'src').mkdir(parents=True,exist_ok=True)
(bridge/'server').mkdir(parents=True,exist_ok=True)
shutil.copy2(root/'src/owner_access.py',bridge/'src/owner_access.py')
for name in ('owner_enrollment.py','owner_games_enroll.py',
             'wolf_docker_adapter.py','wolf_socket_adapter.py'):
 shutil.copy2(root/'server'/name,bridge/'server'/name)
# The owner Games forced broker is NOT installed/enabled by this client .deb.
# Approval on an existing owner host reuses its separately adopted, reviewed broker.

shutil.copy2(root/'src/media-discover.py',pkg/'usr/lib/optiplex-now/media-discover.py')
shutil.copy2(root/'src/download-queue-client.py',pkg/'usr/lib/optiplex-now/download-queue-client.py')
(pkg/'usr/lib/optiplex-now/owner-games-client.py').chmod(0o755)
shutil.copy2(root/'src/restart-streaming.sh',pkg/'usr/lib/optiplex-now/restart-streaming')
shutil.copy2(root/'server/wolf-driver-maintenance.py',pkg/'usr/lib/optiplex-now/wolf-driver-maintenance')
(pkg/'usr/lib/optiplex-now/wolf-driver-maintenance').chmod(0o755)
shutil.copy2(root/'server/moonlightweb-maintenance.py',pkg/'usr/lib/optiplex-now/moonlightweb-maintenance')
(pkg/'usr/lib/optiplex-now/moonlightweb-maintenance').chmod(0o755)
shutil.copy2(root/'src/web-gaming-maintenance.sh',pkg/'usr/lib/optiplex-now/web-gaming-maintenance')
(pkg/'usr/lib/optiplex-now/web-gaming-maintenance').chmod(0o755)
(pkg/'usr/lib/optiplex-now/restart-streaming').chmod(0o755)
(pkg/'usr/bin/optiplex-desk').symlink_to('optiplex-now')
for f in (pkg/'usr/bin/optiplex-now',pkg/'usr/lib/optiplex-now/optiplex-now-backup'): f.chmod(0o755)
try:
 from PIL import Image
 icon=Image.open(root/'assets/optiplex-now.png').convert('RGBA')
 for n in (16,22,24,32,48,64,128,256):
  dest=pkg/f'usr/share/icons/hicolor/{n}x{n}/apps'; dest.mkdir(parents=True,exist_ok=True)
  icon.resize((n,n),Image.Resampling.NEAREST).save(dest/'optiplex-now.png')
 # Tray art is borderless with a genuine alpha channel and enlarged silhouette.
 small=Image.open(root/'assets/optiplex-now-tray.png').convert('RGBA')
 for n in (16,22,24,32,48,64):
  dest=pkg/f'usr/share/icons/hicolor/{n}x{n}/apps'; dest.mkdir(parents=True,exist_ok=True)
  small.resize((n,n),Image.Resampling.NEAREST).save(dest/'optiplex-now-tray.png')
except ImportError as exc:
 raise SystemExit('ERROR: Pillow is required to package all tray icon sizes. Install python3-pil or pip install Pillow.') from exc
(pkg/'usr/share/applications/optiplex-now.desktop').write_text('''[Desktop Entry]
Type=Application
Name=OptiPlex Now
GenericName=Remote server launcher
Comment=Games, video, music and remote control
Exec=/usr/bin/optiplex-now
Icon=optiplex-now
Terminal=false
Categories=Network;Utility;
StartupNotify=true
''')
(pkg/'usr/share/applications/optiplex-desk.desktop').write_text((pkg/'usr/share/applications/optiplex-now.desktop').read_text()+'NoDisplay=true\n')
(pkg/'usr/share/applications/optiplex-now-owner-approvals.desktop').write_text('''[Desktop Entry]
Type=Application
Name=NOW Owner Device Approvals (Host)
Comment=Local owner-only approval of paired streaming devices
Exec=/usr/bin/python3 /usr/lib/optiplex-now/owner-approvals-ui.py
Icon=optiplex-now
Terminal=false
Categories=Network;Utility;
StartupNotify=true
''')
shutil.copy2(root/'OFL-1.1.txt',pkg/'usr/share/doc/optiplex-now/OFL-1.1.txt')
(pkg/'DEBIAN/control').write_text(f'''Package: optiplex-now
Replaces: optiplex-desk
Conflicts: optiplex-desk
Provides: optiplex-desk
Version: {version}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: OptiPlex Now <local@localhost>
Depends: python3, python3-gi, gir1.2-gtk-3.0, libc6 (>= 2.34), libgtk-3-0t64 | libgtk-3-0, libfontconfig1, openssh-client, xdg-utils, gvfs-backends, gvfs-fuse, libglib2.0-bin, libssl3t64 | libssl3
Recommends: libayatana-appindicator3-1, flatpak, curl, gvfs-backends, pkexec, libwebkit2gtk-4.1-0
Description: OptiPlex Now remote server launcher
 Native GTK client with native tray quick actions, owner-managed Steam streaming, live hardware info and encrypted backup.
''')
subprocess.run(['dpkg-deb','--build','--root-owner-group',str(pkg),str(out/f'OptiPlex-Now_{version}_amd64.deb')],check=True)
