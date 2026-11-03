#!/usr/bin/env python3
"""Explicit, reversible API Bay + Bitsearch qBittorrent Nova activation.

--check is read-only. --apply changes only two search plugins after source
checks and isolated Nova tests; --rollback restores the saved API Bay version
and plugin flags. Never modifies transfers, VPN, containers, authentication,
download paths or the user's unrelated search engines.
"""
import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, HTTPCookieProcessor, build_opener, urlopen

SOURCE_COMMIT = "6220a503cc239c2cd397c8f7e67c7538de5c615c"
SOURCE_BLOBS = {
    "bruiser_apibay": "5a6a469b8f4626fded3fa19ed388ce3d8a92f318",
    "bruiser_bitsearch": "09fc0b9b86fd9827799e3961a896118dbab89734",
}
OLD_API_BAY = "871a80678abdbd302a98722811171c446e4f7e62"
CONFIG = Path("/config/qBittorrent")
ENGINES = CONFIG / "nova3/engines"
NOVA = CONFIG / "nova3"
BACKUP = CONFIG / ".bruiser-dual-search-rollback-v1"
URL = "https://raw.githubusercontent.com/SteezyMode/OptiplexNow/"
MAX_RESPONSE = 262144
MAX_SOURCE = 65536
ALLOWED_CURRENT = frozenset(("bruiser_apibay", "bruiser_bitsearch",
                             "torrentscsv", "limetorrents"))


class InstallError(RuntimeError):
    pass


def blob_hash(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def verified_source(name):
    target = URL + SOURCE_COMMIT + "/server/search_plugins/" + name + ".py"
    try:
        with urlopen(Request(target, headers={"User-Agent": "BruiserInstaller/2.0"}),
                     timeout=8) as r:
            if r.geturl() != target:
                raise InstallError("Unexpected source redirect")
            raw = r.read(MAX_SOURCE + 1)
    except OSError as exc:
        raise InstallError("Unable to fetch pinned source for " + name) from exc
    if len(raw) > MAX_SOURCE or blob_hash(raw) != SOURCE_BLOBS[name]:
        raise InstallError("Pinned source integrity failed for " + name)
    return target, raw


def installed_bytes(name):
    path = ENGINES / (name + ".py")
    try:
        mode = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1
            or mode.st_size > MAX_SOURCE):
        raise InstallError("Installed source file is not a safe regular file: " + name)
    return path.read_bytes()


def nova_test(name, raw, category, words):
    for src in ("nova2.py", "helpers.py", "novaprinter.py"):
        if not (NOVA / src).is_file():
            raise InstallError("qBittorrent Nova runtime not present")
    with tempfile.TemporaryDirectory(prefix="bruiser-dual-nova-") as root:
        folder = Path(root)
        for src in ("nova2.py", "helpers.py", "novaprinter.py"):
            shutil.copyfile(NOVA / src, folder / src)
        target = folder / "engines"
        target.mkdir()
        (target / "__init__.py").write_text("")
        (target / (name + ".py")).write_bytes(raw)
        try:
            result = subprocess.run([sys.executable, str(folder / "nova2.py"),
                                     name, category, *words],
                                    cwd=folder, capture_output=True, text=True,
                                    check=False, timeout=12)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InstallError("Temporary Nova test failed: " + name) from exc
    count = sum(line.startswith("magnet:?xt=urn:btih:")
                and len(line.split("|")) == 8
                for line in result.stdout.splitlines())
    if result.returncode or count < 1:
        raise InstallError("No usable magnet from temporary Nova: " + name)
    return count


class API:
    def __init__(self):
        port = os.environ.get("WEBUI_PORT", "8085")
        if not port.isdecimal() or not 1 <= int(port) <= 65535:
            raise InstallError("Invalid local WebUI port")
        self.base = f"http://127.0.0.1:{port}/"
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, fields=None):
        if method not in ("plugins", "installPlugin", "uninstallPlugin",
                          "enablePlugin", "start", "results", "stop", "delete"):
            raise InstallError("Unsupported qBittorrent API operation")
        url = self.base + "api/v2/search/" + method
        if method == "results":
            url += "?" + urlencode(fields or {})
            payload = None
        else:
            payload = None if fields is None else urlencode(fields).encode()
        request = Request(url, data=payload, headers={
            "Referer": self.base,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            with self.opener.open(request, timeout=8) as res:
                raw = res.read(MAX_RESPONSE + 1)
                if res.status != 200 or len(raw) > MAX_RESPONSE:
                    raise InstallError("Unexpected qBittorrent Search API response")
        except OSError as exc:
            raise InstallError("Local qBittorrent Search API failed: " + method) from exc
        return raw

    def plugins(self):
        try:
            data = json.loads(self.call("plugins"))
        except (UnicodeError, ValueError) as exc:
            raise InstallError("Invalid qBittorrent search-plugin status") from exc
        if (not isinstance(data, list) or len(data) > 50
                or any(not isinstance(x, dict) or not isinstance(x.get("name"), str)
                       or type(x.get("enabled")) is not bool for x in data)):
            raise InstallError("Unexpected plugin inventory")
        result = {x["name"]: x for x in data}
        if len(result) != len(data):
            raise InstallError("Duplicate search-plugin names")
        return result

    def wait_for_hash(self, name, expected, timeout=12):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            current = installed_bytes(name)
            if current is not None and blob_hash(current) == expected:
                if name in self.plugins():
                    return True
            time.sleep(.25)
        return False

    def enable(self, name, value):
        self.call("enablePlugin", {"names": name,
                                   "enable": "true" if value else "false"})

    def test_search(self, name, category, pattern):
        job = None
        try:
            resp = json.loads(self.call("start", {
                "pattern": pattern, "category": category, "plugins": name,
            }))
            job = resp.get("id")
            if type(job) is not int or not 0 <= job < 2**31:
                raise InstallError("Invalid search-job ID")
            for _ in range(20):
                time.sleep(.25)
                content = json.loads(self.call("results", {
                    "id": job, "limit": 100, "offset": 0,
                }))
                results = content.get("results", [])
                if not isinstance(results, list):
                    raise InstallError("Invalid search results")
                magnets = [r for r in results if isinstance(r, dict)
                           and isinstance(r.get("fileUrl"), str)
                           and re.match(r"\Amagnet:\?xt=urn:btih:[a-fA-F0-9]{40}\b",
                                        r["fileUrl"])]
                if magnets:
                    return len(magnets)
            raise InstallError("No usable results from installed " + name)
        finally:
            if job is not None:
                for action in ("stop", "delete"):
                    try:
                        self.call(action, {"id": job})
                    except InstallError:
                        pass


def save_backup(original, states):
    if BACKUP.exists() or BACKUP.is_symlink():
        raise InstallError("Dual-search backup already exists; no overwrite")
    if CONFIG.is_symlink() or not CONFIG.is_dir():
        raise InstallError("Unsafe qBittorrent configuration path")
    BACKUP.mkdir(mode=0o755)
    plugin_file = BACKUP / "bruiser_apibay.py"
    with plugin_file.open("xb") as stream:
        stream.write(original)
    plugin_file.chmod(0o644)  # qBittorrent process must be able to read it
    metadata = BACKUP / "state.json"
    with metadata.open("x") as stream:
        json.dump({"version": 1, "old_blob": OLD_API_BAY,
                   "enabled": states}, stream, sort_keys=True)
    metadata.chmod(0o600)
    print("Rollback record saved to", BACKUP, flush=True)


def read_backup():
    metadata = BACKUP / "state.json"
    if metadata.is_symlink() or not metadata.is_file():
        raise InstallError("Rollback record absent or unsafe")
    if metadata.stat().st_size > 4096:
        raise InstallError("Rollback record too large")
    try:
        record = json.loads(metadata.read_text())
    except (UnicodeError, ValueError) as exc:
        raise InstallError("Invalid rollback record") from exc
    states = record.get("enabled", {})
    if (record.get("version") != 1 or record.get("old_blob") != OLD_API_BAY
            or not isinstance(states, dict)
            or not set(states).issubset(ALLOWED_CURRENT)
            or any(type(x) is not bool for x in states.values())):
        raise InstallError("Invalid original plugin states")
    original = BACKUP / "bruiser_apibay.py"
    if (original.is_symlink() or not original.is_file()
            or blob_hash(original.read_bytes()) != OLD_API_BAY):
        raise InstallError("Original API Bay backup is missing or changed")
    return states, original


def apply(api):
    plugins = api.plugins()
    current = installed_bytes("bruiser_apibay")
    if (current is None or blob_hash(current) != OLD_API_BAY
            or "bruiser_apibay" not in plugins):
        raise InstallError("Expected previously reviewed API Bay v1.1, unchanged")
    if "bruiser_bitsearch" in plugins or installed_bytes("bruiser_bitsearch") is not None:
        raise InstallError("Bitsearch is already installed; manual review required")
    if BACKUP.exists() or BACKUP.is_symlink():
        raise InstallError("Existing dual-search backup; refused")
    previous = {name: row["enabled"] for name, row in plugins.items()}
    if any(name not in ALLOWED_CURRENT and enabled
           for name, enabled in previous.items()):
        raise InstallError("Unknown enabled plugin; won't alter active search")

    sources = {}
    for name in SOURCE_BLOBS:
        sources[name] = verified_source(name)
        print("Source verified:", name, flush=True)
    # Validate Nova without changing any installed search plugin.
    print("Temporary API Bay magnets:",
          nova_test("bruiser_apibay", sources["bruiser_apibay"][1],
                    "all", ["south", "park", "s29e04"]), flush=True)
    print("Temporary Bitsearch magnets:",
          nova_test("bruiser_bitsearch", sources["bruiser_bitsearch"][1],
                    "games", ["resident", "evil", "requiem"]), flush=True)
    # Durable rollback copy exists before any qBittorrent plugin change.
    save_backup(current, previous)
    try:
        for name in SOURCE_BLOBS:
            api.call("installPlugin", {"sources": sources[name][0]})
            if not api.wait_for_hash(name, SOURCE_BLOBS[name]):
                raise InstallError("New plugin wasn't installed correctly: " + name)
            api.enable(name, True)
            print("Installed and enabled:", name, flush=True)
        # Test both search engines through actual qBittorrent, not HTTP alone.
        print("Installed API Bay TV magnets:",
              api.test_search("bruiser_apibay", "all", "south park s29e04"),
              flush=True)
        print("Installed Bitsearch PC game magnets:",
              api.test_search("bruiser_bitsearch", "games", "resident evil requiem"),
              flush=True)
        final = api.plugins()
        if any(not final[n]["enabled"] for n in SOURCE_BLOBS):
            raise InstallError("Both reviewed plugins must remain enabled")
        if any(final[name]["enabled"] != flag for name, flag in previous.items()
               if name not in SOURCE_BLOBS):
            raise InstallError("An unrelated plugin's enabled state changed")
        print("ACTIVE: API Bay and Bitsearch verified. Prior state saved.", flush=True)
    except (InstallError, OSError):
        print("ACTIVATION INCOMPLETE: use --rollback with the same script.",
              file=sys.stderr, flush=True)
        raise


def rollback(api):
    states, oldpath = read_backup()
    current = installed_bytes("bruiser_apibay")
    if current is None or blob_hash(current) not in (SOURCE_BLOBS["bruiser_apibay"], OLD_API_BAY):
        raise InstallError("Unexpected API Bay version; refusing destructive rollback")
    bit = installed_bytes("bruiser_bitsearch")
    if bit is not None and blob_hash(bit) != SOURCE_BLOBS["bruiser_bitsearch"]:
        raise InstallError("Unexpected Bitsearch version; refusing destructive rollback")
    api.enable("bruiser_bitsearch", False)
    if bit is not None:
        api.call("uninstallPlugin", {"names":"bruiser_bitsearch"})
    if blob_hash(current) != OLD_API_BAY:
        api.call("uninstallPlugin", {"names":"bruiser_apibay"})
        api.call("installPlugin", {"sources":str(oldpath)})
        if not api.wait_for_hash("bruiser_apibay", OLD_API_BAY):
            raise InstallError("Could not restore original API Bay source")
    for name, flag in states.items():
        if name in api.plugins():
            api.enable(name, flag)
    final = api.plugins()
    if (final.get("bruiser_apibay", {}).get("enabled") != states.get("bruiser_apibay")
            or final.get("bruiser_bitsearch", {}).get("enabled", False)):
        raise InstallError("Could not verify original search-provider selection")
    print("ROLLED BACK: original API Bay plugin and provider state restored.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true")
    group.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    api = API()
    if args.apply:
        apply(api)
    elif args.rollback:
        rollback(api)
    else:
        print("READ-ONLY SEARCH PLUGIN STATUS")
        for name, plugin in sorted(api.plugins().items()):
            print(name, "enabled="+str(plugin["enabled"]),
                  "version="+str(plugin.get("version", "?")))
        print("Dual-search rollback record:", BACKUP.is_dir())


if __name__ == "__main__":
    try:
        main()
    except (InstallError, OSError, ValueError) as exc:
        print("BLOCKED:", exc, file=sys.stderr)
        raise SystemExit(1)
