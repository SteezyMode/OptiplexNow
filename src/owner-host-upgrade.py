#!/usr/bin/python3
"""Owner-approved one-time migration to the package-owned restricted host broker.

Ordinary .deb install is inert: it does not edit authorized_keys or host state.
After the owner explicitly migrates an existing approved host, future .deb
updates replace the code in /usr/lib while owner credentials/data remain put.
"""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import tempfile

PACKAGE_BROKER = Path("/usr/lib/optiplex-now/owner-bridge/server/owner_games_ssh.py")
MAX_AUTH = 262144
# Match ONLY the existing full-line restricted SSH key form, not arbitrary shell commands.
RESTRICTED_LINE = re.compile(
    rb'restrict,command="/usr/bin/python3 (?P<path>/[A-Za-z0-9_./-]+/owner_games_ssh\.py) '
    rb'--client-id (?P<id>[0-9]{1,20})" ssh-ed25519 [A-Za-z0-9+/=]+'
    rb'(?:[ \t]+[^\r\n]+)?'
)


class HostUpgradeError(RuntimeError):
    pass


def _trusted_file(path, owner):
    if path.is_symlink() or not path.is_file():
        raise HostUpgradeError("Unsafe owner SSH or package file")
    metadata = path.stat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != owner
            or metadata.st_nlink != 1 or metadata.st_mode & 0o022):
        raise HostUpgradeError("Owner SSH or package file permissions are unsafe")
    return metadata


def inspect(*, home=None, package_broker=PACKAGE_BROKER, package_owner=0):
    home = Path.home() if home is None else Path(home)
    package_broker = Path(package_broker)
    if (not package_broker.is_absolute() or package_broker.name != "owner_games_ssh.py"
            or not package_broker.parent.name == "server"):
        raise HostUpgradeError("Package handler path invalid")
    _trusted_file(package_broker, package_owner)
    for folder in (package_broker.parent, package_broker.parent.parent):
        if folder.is_symlink() or not folder.is_dir():
            raise HostUpgradeError("Unsafe installed package directory")
        info = folder.stat()
        if info.st_uid != package_owner or info.st_mode & 0o022:
            raise HostUpgradeError("Unsafe installed package ownership")
    ssh_dir = home / ".ssh"
    auth = ssh_dir / "authorized_keys"
    if ssh_dir.is_symlink() or not ssh_dir.is_dir():
        return {"status": "not_configured", "count": 0}, None, None
    di = ssh_dir.stat()
    if di.st_uid != os.geteuid() or di.st_mode & 0o077:
        raise HostUpgradeError("Owner SSH directory must be private")
    if not auth.exists() and not auth.is_symlink():
        return {"status": "not_configured", "count": 0}, None, None
    meta = _trusted_file(auth, os.geteuid())
    if meta.st_size > MAX_AUTH:
        raise HostUpgradeError("Owner SSH keys file exceeds safe limit")
    original = auth.read_bytes()
    if len(original) > MAX_AUTH:
        raise HostUpgradeError("Owner SSH keys file exceeds safe limit")
    old_path = (home / ".local/lib/optiplex-now-games/server/owner_games_ssh.py").as_posix().encode()
    new_path = str(package_broker).encode("ascii")
    changed = []
    count = 0
    old_count = 0
    for line in original.splitlines(keepends=True):
        body = line.rstrip(b"\r\n")
        if b"owner_games_ssh.py" not in body:
            changed.append(line)
            continue
        match = RESTRICTED_LINE.fullmatch(body)
        if not match:
            raise HostUpgradeError("Unrecognized owner broker key: manual review required")
        path = match.group("path")
        if path not in (old_path, new_path):
            raise HostUpgradeError("Different owner broker installation: manual review required")
        count += 1
        if path == old_path:
            old_count += 1
            changed.append(line.replace(old_path, new_path, 1))
        else:
            changed.append(line)
    status = ("not_configured" if count == 0 else
              "ready" if old_count else "up_to_date")
    return {"status": status, "count": count, "migrate": old_count}, original, b"".join(changed)


def activate(*, home=None, package_broker=PACKAGE_BROKER, package_owner=0):
    home = Path.home() if home is None else Path(home)
    state, original, updated = inspect(
        home=home, package_broker=package_broker, package_owner=package_owner)
    if state["status"] != "ready":
        raise HostUpgradeError("No approved legacy broker to migrate")
    auth = home / ".ssh/authorized_keys"
    backups = home / ".local/share/optiplex-now/backups"
    if backups.is_symlink():
        raise HostUpgradeError("Unsafe backup location")
    backups.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = backups.stat()
    if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
        raise HostUpgradeError("Backup directory is not owner-private")
    # Never modify the SSH file if it changed during the review.
    if auth.read_bytes() != original:
        raise HostUpgradeError("Owner SSH keys changed; retry only after inspection")
    backup_dir = Path(tempfile.mkdtemp(prefix="packaged-host-", dir=backups))
    backup = backup_dir / "authorized_keys"
    staged = None
    replaced = False
    try:
        with backup.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        mode = stat.S_IMODE(auth.stat().st_mode)
        fd, name = tempfile.mkstemp(prefix=".now-packaged-", dir=auth.parent)
        staged = Path(name)
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        if auth.read_bytes() != original:
            raise HostUpgradeError("Owner SSH keys changed before activation")
        os.replace(staged, auth)
        staged = None
        replaced = True
        if auth.read_bytes() != updated:
            raise HostUpgradeError("Cannot verify upgraded owner SSH keys")
    except Exception:
        if replaced:
            # Restore the original from the already durable backup, atomically.
            fd, name = tempfile.mkstemp(prefix=".now-rollback-", dir=auth.parent)
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), stat.S_IMODE(auth.stat().st_mode))
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, auth)
        raise
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    return {"status": "activated", "count": state["migrate"],
            "backup": str(backup)}


def gui():
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    def message(title, detail, *, question=False):
        dialog = Gtk.MessageDialog(
            message_type=Gtk.MessageType.QUESTION if question else Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.YES_NO if question else Gtk.ButtonsType.OK,
            text=title)
        dialog.format_secondary_text(detail)
        response = dialog.run()
        dialog.destroy()
        return response == (Gtk.ResponseType.YES if question else Gtk.ResponseType.OK)

    try:
        state, _, _ = inspect()
        if state["status"] == "not_configured":
            message("No existing owner host found",
                    "This computer has no previously approved restricted NOW host keys. "
                    "Use normal Host Setup; nothing was modified.")
            return
        if state["status"] == "up_to_date":
            message("NOW host code already uses the installed package",
                    "Future NOW .deb upgrades will update the same trusted owner host code. "
                    "No Steam, Jellyfin, VPN or SSH credentials were changed.")
            return
        if not message("Use installed NOW host code?", 
                       "This one-time change switches only the approved NOW restricted "
                       "SSH commands to the package-owned handler. Owner devices, keys, "
                       "Steam, Wolf, Jellyfin, VPN and files stay unchanged. An exact "
                       "SSH key backup will be saved first. Future .deb updates will "
                       "update both host and client code together.",
                       question=True):
            return
        result = activate()
        message("NOW host package activated",
                "Updated %d previously approved restricted key entries. Backup: %s"
                % (result["count"], result["backup"]))
    except (HostUpgradeError, OSError, UnicodeError) as exc:
        message("Host upgrade blocked", str(exc) + "\nNo unrelated services were changed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--confirm-owner-upgrade", action="store_true")
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if args.gui:
        gui()
        return
    if args.activate:
        if not args.confirm_owner_upgrade:
            parser.error("An explicit owner upgrade confirmation is required")
        try:
            print(json.dumps(activate(), sort_keys=True))
        except (HostUpgradeError, OSError) as exc:
            print(json.dumps({"status": "blocked", "reason": str(exc)}))
            raise SystemExit(1)
        return
    if args.check:
        try:
            print(json.dumps(inspect()[0], sort_keys=True))
        except (HostUpgradeError, OSError) as exc:
            print(json.dumps({"status": "blocked", "reason": str(exc)}))
            raise SystemExit(1)
        return
    parser.error("Use the Host Setup GUI or an explicitly confirmed owner upgrade; --check is read-only")


if __name__ == "__main__":
    main()
