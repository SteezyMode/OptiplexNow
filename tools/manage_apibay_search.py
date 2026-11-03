#!/usr/bin/env python3
"""Safely switch the *current* personal qBittorrent host to API Bay-only search.

Run INSIDE the trusted qbittorrent-vpn container. No torrent queue action,
account provisioning, network reconfiguration, container restart, or service
restart. The normal invocation without flags is read-only. --apply requires
an operator decision and --rollback restores the saved plugin enable flags.

Source is pinned to an immutable Git commit and verified as a Git blob before
installation. Only known previous plugin states are modified. Fail closed on
unknown enabled plugins, a nonmatching existing candidate or missing backup.
"""
import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

SOURCE_COMMIT = "8d6e58e8b7b603705fe7f82209a03d6dd1738da8"
SOURCE_GIT_BLOB = "871a80678abdbd302a98722811171c446e4f7e62"
PLUGIN_NAME = "bruiser_apibay"
SOURCE_URL = (
    "https://raw.githubusercontent.com/SteezyMode/OptiplexNow/"
    + SOURCE_COMMIT + "/server/search_plugins/bruiser_apibay.py"
)
CONFIG_ROOT = Path("/config/qBittorrent")
NOVA_ROOT = CONFIG_ROOT / "nova3"
PLUGIN_FILE = NOVA_ROOT / "engines" / (PLUGIN_NAME + ".py")
BACKUP_FILE = CONFIG_ROOT / ".bruiser-search-rollback-v1.json"
DEFAULT_LEGACY = frozenset(("torrentscsv", "limetorrents"))
MAX_API = 262144


class TransitionError(RuntimeError):
    pass


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def fetch_source():
    req = Request(SOURCE_URL, headers={"User-Agent": "BruiserInstaller/1.0"})
    try:
        with urlopen(req, timeout=8) as res:
            body = res.read(64 * 1024 + 1)
    except (OSError, URLError, HTTPError) as exc:
        raise TransitionError("Cannot fetch pinned search source") from exc
    if len(body) > 64 * 1024 or git_blob_sha(body) != SOURCE_GIT_BLOB:
        raise TransitionError("Search source verification failed")
    if b"class bruiser_apibay:" not in body:
        raise TransitionError("Search source has an unexpected plugin entry")
    return body


def local_code_matches():
    try:
        mode = PLUGIN_FILE.lstat()
    except FileNotFoundError:
        return False
    if (not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1
            or mode.st_size > 64 * 1024):
        raise TransitionError("Existing API Bay plugin file is unsafe")
    return git_blob_sha(PLUGIN_FILE.read_bytes()) == SOURCE_GIT_BLOB


def nova_preflight(source):
    for name in ("nova2.py", "helpers.py", "novaprinter.py"):
        if not (NOVA_ROOT / name).is_file():
            raise TransitionError("Installed qBittorrent Nova runtime is unavailable")
    with tempfile.TemporaryDirectory(prefix="bruiser-source-test-") as temp:
        root = Path(temp)
        for name in ("nova2.py", "helpers.py", "novaprinter.py"):
            shutil.copyfile(NOVA_ROOT / name, root / name)
        engines = root / "engines"
        engines.mkdir()
        (engines / "__init__.py").write_text("", encoding="utf-8")
        (engines / (PLUGIN_NAME + ".py")).write_bytes(source)
        try:
            result = subprocess.run(
                [sys.executable, str(root / "nova2.py"), PLUGIN_NAME, "all",
                 "resident", "evil"],
                cwd=root, capture_output=True, text=True, timeout=8, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TransitionError("Temporary Nova test timed out or failed") from exc
    valid = [
        line for line in result.stdout.splitlines()
        if len(line.split("|")) == 8
        and line.startswith("magnet:?xt=urn:btih:")
    ]
    if result.returncode or not valid:
        raise TransitionError("Temporary Nova test produced no usable magnet results")
    return len(valid)


class LocalQbit:
    def __init__(self, port):
        if not 1 <= port <= 65535:
            raise TransitionError("Invalid local WebUI port")
        self.base = f"http://127.0.0.1:{port}/"
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, route, fields=None):
        if not route.startswith("search/"):
            raise TransitionError("Only qBittorrent search APIs may be used")
        url = self.base + "api/v2/" + route
        if fields is not None and route == "search/results":
            url += "?" + urlencode(fields)
            data = None
        else:
            data = None if fields is None else urlencode(fields).encode("utf-8")
        req = Request(url, data=data, headers={
            "Referer": self.base,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            with self.opener.open(req, timeout=7) as response:
                body = response.read(MAX_API + 1)
                if response.status != 200 or len(body) > MAX_API:
                    raise TransitionError("Invalid local qBittorrent search response")
        except (OSError, URLError, HTTPError) as exc:
            raise TransitionError("Local qBittorrent search API unavailable") from exc
        return body

    def plugins(self):
        try:
            content = json.loads(self.request("search/plugins"))
        except (UnicodeError, ValueError) as exc:
            raise TransitionError("Invalid search-plugin inventory") from exc
        if (not isinstance(content, list) or len(content) > 50
                or any(not isinstance(p, dict)
                       or not isinstance(p.get("name"), str)
                       or type(p.get("enabled")) is not bool
                       for p in content)):
            raise TransitionError("Unexpected search-plugin inventory")
        names = [p["name"] for p in content]
        if len(names) != len(set(names)):
            raise TransitionError("Duplicate search-plugin names")
        return {p["name"]: p for p in content}

    def set_enabled(self, names, enabled):
        if names:
            self.request("search/enablePlugin", {
                "names": "|".join(sorted(names)),
                "enable": "true" if enabled else "false",
            })

    def find_plugin(self, name, timeout=8):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            item = self.plugins().get(name)
            if item is not None:
                return item
            time.sleep(0.25)
        return None

    def verified_search(self, plugin=PLUGIN_NAME):
        """Prove one real search from the installed plugin; add no torrents."""
        job = None
        try:
            raw = self.request("search/start", {
                "pattern": "resident evil", "plugins": plugin, "category": "all",
            })
            data = json.loads(raw)
            if type(data.get("id")) is not int:
                raise TransitionError("Search did not produce a valid job ID")
            job = data["id"]
            for _ in range(16):
                time.sleep(0.25)
                data = json.loads(self.request("search/results", {
                    "id": job, "limit": 100, "offset": 0,
                }))
                matches = data.get("results")
                if not isinstance(matches, list):
                    raise TransitionError("Search returned invalid result data")
                usable = [item for item in matches
                          if isinstance(item, dict)
                          and isinstance(item.get("fileUrl"), str)
                          and item["fileUrl"].startswith("magnet:?xt=urn:btih:")]
                if usable:
                    return len(usable)
            raise TransitionError("Installed API Bay plugin returned no usable results")
        except (ValueError, UnicodeError) as exc:
            raise TransitionError("Installed search returned malformed data") from exc
        finally:
            if job is not None:
                for operation in ("stop", "delete"):
                    try:
                        self.request("search/" + operation, {"id": job})
                    except TransitionError:
                        pass


def snapshot_write(initial):
    if BACKUP_FILE.exists() or BACKUP_FILE.is_symlink():
        raise TransitionError("Rollback backup already exists; refusing to overwrite")
    if CONFIG_ROOT.is_symlink() or not CONFIG_ROOT.is_dir():
        raise TransitionError("qBittorrent configuration directory is unsafe")
    payload = json.dumps({
        "version": 1,
        "plugin": PLUGIN_NAME,
        "git_blob_sha": SOURCE_GIT_BLOB,
        "previous": initial,
    }, sort_keys=True).encode() + b"\n"
    if len(payload) > 4096:
        raise TransitionError("Rollback backup unexpectedly large")
    fd = os.open(BACKUP_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def snapshot_read():
    try:
        info = BACKUP_FILE.lstat()
    except FileNotFoundError as exc:
        raise TransitionError("No saved plugin configuration to restore") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_size > 4096 or info.st_mode & 0o077):
        raise TransitionError("Unsafe rollback backup")
    try:
        data = json.loads(BACKUP_FILE.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise TransitionError("Invalid rollback backup") from exc
    initial = data.get("previous")
    if (data.get("version") != 1 or data.get("plugin") != PLUGIN_NAME
            or data.get("git_blob_sha") != SOURCE_GIT_BLOB
            or not isinstance(initial, dict)
            or not set(initial).issubset(DEFAULT_LEGACY)
            or any(type(flag) is not bool for flag in initial.values())):
        raise TransitionError("Rollback backup does not match known plugins")
    return initial


def restore(api, previous):
    inventory = api.plugins()
    for name, enabled in previous.items():
        if name not in inventory:
            raise TransitionError("Previously installed plugin missing during rollback")
    # Restore known existing providers before disabling the new one.
    api.set_enabled([name for name, flag in previous.items() if flag], True)
    api.set_enabled([name for name, flag in previous.items() if not flag], False)
    if PLUGIN_NAME in inventory:
        api.set_enabled([PLUGIN_NAME], False)
    current = api.plugins()
    if any(current[name]["enabled"] != flag for name, flag in previous.items()):
        raise TransitionError("Could not verify restored original plugin states")
    if current.get(PLUGIN_NAME, {}).get("enabled", False):
        raise TransitionError("New plugin remained enabled after rollback")


def activate(api):
    state = api.plugins()
    enabled = {name for name, item in state.items() if item["enabled"]}
    if PLUGIN_NAME in state:
        if local_code_matches() and enabled == {PLUGIN_NAME}:
            print("ALREADY ACTIVE: API Bay is the only enabled provider.")
            return
        raise TransitionError("API Bay is already installed; refusing to overwrite it")
    if PLUGIN_FILE.exists() or PLUGIN_FILE.is_symlink():
        raise TransitionError("Conflicting API Bay source already exists")
    if enabled != DEFAULT_LEGACY:
        raise TransitionError("Unexpected enabled search plugins; review before switching")
    if BACKUP_FILE.exists() or BACKUP_FILE.is_symlink():
        raise TransitionError("Pre-existing rollback record; review before switching")

    print("Checking pinned source and temporary Nova compatibility...", flush=True)
    payload = fetch_source()
    count = nova_preflight(payload)
    print("Temporary Nova test valid magnets:", count, flush=True)
    original = {name: state[name]["enabled"] for name in DEFAULT_LEGACY}

    installed = False
    backup_written = False
    try:
        print("Installing reviewed API Bay plugin through qBittorrent...", flush=True)
        # qBittorrent's plugin manager installs from a pinned, immutable URL.
        # The same content has just passed the local Git blob check.
        api.request("search/installPlugin", {"sources": SOURCE_URL})
        item = api.find_plugin(PLUGIN_NAME)
        if not item:
            raise TransitionError("API Bay was not registered by qBittorrent")
        installed = True
        if (item.get("fullName") != "Bruiser - API Bay"
                or item.get("url") != "https://apibay.org"
                or not local_code_matches()):
            raise TransitionError("Installed API Bay source verification failed")
        api.set_enabled([PLUGIN_NAME], True)
        results = api.verified_search()
        print("Installed plugin search produced", results, "usable magnets.", flush=True)

        # Durable original state precedes any removal of existing functionality.
        snapshot_write(original)
        backup_written = True
        api.set_enabled(DEFAULT_LEGACY, False)
        final = api.plugins()
        if (not final[PLUGIN_NAME]["enabled"]
                or any(final[name]["enabled"] for name in DEFAULT_LEGACY)
                or {name for name, item in final.items() if item["enabled"]}
                   != {PLUGIN_NAME}):
            raise TransitionError("API Bay-only search state was not verified")
        print("ACTIVE: only bruiser_apibay is enabled.", flush=True)
        print("Original engines remain installed. --rollback restores them.", flush=True)
    except (TransitionError, OSError):
        print("Activation failed; attempting to restore original plugin states.",
              flush=True)
        try:
            api.set_enabled(DEFAULT_LEGACY, True)
            if PLUGIN_NAME in api.plugins():
                api.set_enabled([PLUGIN_NAME], False)
            existing = api.plugins()
            if any(not existing[name]["enabled"] for name in DEFAULT_LEGACY):
                raise TransitionError("Original providers not restored")
            print("Original enabled providers restored.", flush=True)
        except Exception:
            print("WARNING: Automatic restore not verified. Inspect plugin states.",
                  flush=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--apply", action="store_true",
                         help="Explicitly enable only API Bay, with rollback record")
    actions.add_argument("--rollback", action="store_true",
                         help="Restore original plugin enable states")
    options = parser.parse_args()
    port = os.environ.get("WEBUI_PORT", "8085")
    if not port.isdecimal():
        raise TransitionError("Invalid WebUI port")
    api = LocalQbit(int(port))
    if options.apply:
        activate(api)
    elif options.rollback:
        previous = snapshot_read()
        restore(api, previous)
        print("ROLLED BACK: original plugin states restored.")
    else:
        print("READ-ONLY CURRENT PLUGIN STATUS:")
        for name, info in sorted(api.plugins().items()):
            print(f"  {name}: enabled={info['enabled']} "
                  f"version={info.get('version', '?')}")
        print("Rollback snapshot exists:", BACKUP_FILE.is_file())


if __name__ == "__main__":
    try:
        main()
    except (TransitionError, OSError) as exc:
        print("BLOCKED:", str(exc), file=sys.stderr)
        raise SystemExit(1)
