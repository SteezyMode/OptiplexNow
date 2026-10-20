#!/usr/bin/env python3
"""Safely exercise NOW's MoonlightWeb backup/archive path on disposable files.

No Docker commands and no writes to the production MoonlightWeb volume.
Works from a repository checkout or downloaded into /tmp beside the helper.
"""
import importlib.util
from pathlib import Path
import tarfile
import tempfile

root = Path(__file__).resolve().parents[1]
helper = root / "server" / "moonlightweb-maintenance.py"
if not helper.is_file():
    helper = Path("/tmp/moonlightweb-maintenance.py")
if not helper.is_file():
    raise SystemExit("Download the maintenance helper to /tmp first")
spec = importlib.util.spec_from_file_location("moonlightweb_maintenance", helper)
mw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mw)

with tempfile.TemporaryDirectory(prefix="now-mw-backup-test-") as directory:
    tmp = Path(directory)
    mw.STATE = tmp / "private-backups"
    source = tmp / "source"
    source.mkdir()
    (source / "settings").mkdir()
    (source / "settings" / "marker.txt").write_text("persistent-data-marker\n")
    stamp, archive = mw.save_backup(source)
    assert stamp and archive.is_file()
    assert archive.stat().st_mode & 0o777 == 0o600
    assert mw.STATE.stat().st_mode & 0o777 == 0o700
    with tarfile.open(archive, "r:gz") as bundle:
        member = bundle.getmember("data/settings/marker.txt")
        assert member.isfile()
        assert bundle.extractfile(member).read() == b"persistent-data-marker\n"
    print("PASS: private MoonlightWeb backup archived and verified disposable data")
    print("PASS: backup permissions are 0600; containing directory is 0700")
    print("No production data, Docker containers or volumes were touched.")
print("Temporary archive and test data removed.")
