#!/usr/bin/env python3
"""Stage (but do not activate) an independent OptiPlex Studio Wolf app.

Do not modify /etc/wolf/cfg/config.toml. A separate review/apply step is required.
"""
import pathlib
import re
import tomllib

LIVE = pathlib.Path("/etc/wolf/cfg/config.toml")
CANDIDATE = pathlib.Path("/etc/wolf/cfg/config.toml.studio-candidate")
IMAGE = "optiplex-studio-desktop:v1"
TITLE = "OptiPlex Studio Desktop"
PROJECTS = pathlib.Path("/home/optiplex/StudioProjects")

raw = LIVE.read_text()
old = tomllib.loads(raw)
profiles = old["profiles"]
user_profiles = [p for p in profiles if p.get("name") == "User"]
if len(user_profiles) != 1:
    raise SystemExit("Expected exactly one Wolf 'User' profile; refusing to stage.")
user = user_profiles[0]
apps = user["apps"]
if any(a.get("title") == TITLE or a.get("runner", {}).get("name") == "WolfStudioDesktop" for a in apps):
    raise SystemExit("Studio app already exists in live config; refusing duplicate.")
if not PROJECTS.is_dir():
    raise SystemExit("StudioProjects directory missing; refusing to stage.")

prefix = (
    "    [[profiles.apps]]\n"
    "    icon_png_path = 'https://games-on-whales.github.io/wildlife/apps/xfce/assets/icon.png'\n"
    "    title = 'Desktop (xfce)'"
)
start = raw.find(prefix)
if start < 0 or raw.find(prefix, start + 1) != -1:
    raise SystemExit("Couldn't uniquely locate existing XFCE app block.")
end = raw.find("\n    [[profiles.apps]]", start + len(prefix))
if end < 0:
    raise SystemExit("Couldn't find end of existing XFCE app block.")
original = raw[start:end]

studio = original.replace("title = 'Desktop (xfce)'", "title = '" + TITLE + "'", 1)
studio, n = re.subn(r"(?m)^        image = '[^']+'$", "        image = '" + IMAGE + "'", studio)
if n != 1:
    raise SystemExit("XFCE image entry unexpectedly missing/duplicate.")
studio, n = re.subn(
    r"(?m)^        mounts = \[\n(?:.*\n)*?^        \]$",
    "        mounts = [\n            '/home/optiplex/StudioProjects:/projects:rw'\n        ]",
    studio,
)
if n != 1:
    raise SystemExit("XFCE mount block unexpectedly missing/duplicate.")
studio, n = re.subn(r"(?m)^        name = 'WolfXFCE'$", "        name = 'WolfStudioDesktop'", studio)
if n != 1:
    raise SystemExit("XFCE name entry unexpectedly missing/duplicate.")

new_raw = raw[:end] + "\n" + studio + raw[end:]
new = tomllib.loads(new_raw)
if len(new["profiles"]) != len(old["profiles"]):
    raise SystemExit("Profile count changed unexpectedly.")
for oldp, newp in zip(old["profiles"], new["profiles"]):
    if oldp.get("name") == "User":
        newapps = newp["apps"]
        if len(newapps) != len(oldp["apps"]) + 1:
            raise SystemExit("Expected exactly one new app.")
        additions = [a for a in newapps if a.get("title") == TITLE]
        if len(additions) != 1 or additions[0]["runner"].get("mounts") != [
            "/home/optiplex/StudioProjects:/projects:rw"
        ]:
            raise SystemExit("Studio profile content invalid.")
        otherapps = [a for a in newapps if a.get("title") != TITLE]
        if otherapps != oldp["apps"]:
            raise SystemExit("Existing Wolf apps changed unexpectedly.")
        copy = dict(newp)
        copy["apps"] = otherapps
        if copy != oldp:
            raise SystemExit("Existing User profile modified unexpectedly.")
    elif oldp != newp:
        raise SystemExit("Unexpected modification to another Wolf profile.")

if CANDIDATE.exists():
    raise SystemExit(f"Candidate already exists: {CANDIDATE}; inspect before overwriting.")
with CANDIDATE.open("x") as f:
    f.write(new_raw)
CANDIDATE.chmod(0o600)
print("STAGED ONLY (LIVE WOLF CONFIG UNCHANGED)")
print(f"Candidate: {CANDIDATE}")
print(f"App: {TITLE}")
print(f"Image: {IMAGE}")
print(f"Writable mount: {PROJECTS} -> /projects")
print(f"Existing apps preserved: {len(apps)}")
print("Config: TOML parsed and full existing-profile comparison PASSED")
