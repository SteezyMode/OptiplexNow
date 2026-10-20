#!/usr/bin/env python3
"""Conservative lifecycle management for an existing standalone MoonlightWeb.

Operates only on the named MoonlightWeb container. Never stops Wolf, modifies
its application containers, or deletes a Docker volume. Run as root on the
server; installing the NOW GUI on a client alone does not install this helper.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time

NAME = "moonlightweb"
IMAGE = "ghcr.io/linckosz/moonlight-web:latest"
STATE = Path("/var/lib/optiplex-now/moonlightweb")
BACKUP_PREFIX = "moonlightweb-preupdate-"
# Wolf-UI is a management component, not an application desktop.
WOLF_SESSION = re.compile(r"^Wolf[A-Za-z0-9][A-Za-z0-9_-]*$")
SAFE_VOLUME_MODE = {"", "z", "Z", "rw", "rw,z", "rw,Z"}


def docker(*args):
    result = subprocess.run(["docker", *map(str, args)], text=True, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.strip()


def inspect(name=NAME):
    return json.loads(docker("inspect", name))[0]


def active_wolf_apps():
    return [name for name in docker("ps", "--format", "{{.Names}}").splitlines()
            if WOLF_SESSION.fullmatch(name)]


def volume_from(info):
    mounts = info.get("Mounts") or []
    if len(mounts) != 1:
        raise RuntimeError("Unexpected MoonlightWeb mounts; refusing changes")
    mount = mounts[0]
    if (mount.get("Type") != "volume" or mount.get("Destination") != "/data"
            or not mount.get("RW") or mount.get("Mode", "") not in SAFE_VOLUME_MODE):
        raise RuntimeError("Unsupported /data mount; refusing changes")
    name = mount.get("Name", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise RuntimeError("Invalid volume name")
    return name, Path(mount["Source"]), mount.get("Mode", "")


def recreate_args(info, image_id):
    """Build a replacement ONLY for the explicitly supported standalone shape."""
    host = info["HostConfig"]
    cfg = info["Config"]
    volume, _, mode = volume_from(info)
    if (info.get("Name") != "/" + NAME or cfg.get("Image") != IMAGE
            or host.get("NetworkMode") != "host" or host.get("Privileged")
            or host.get("AutoRemove") or host.get("ReadonlyRootfs")):
        raise RuntimeError("Not the supported standalone MoonlightWeb deployment")
    if "com.docker.compose.project" in (cfg.get("Labels") or {}):
        raise RuntimeError("Compose-managed service: update through its Compose project")
    unsupported = ("Devices", "DeviceRequests", "Mounts", "PortBindings", "Links",
                   "ExtraHosts", "Dns", "DnsSearch", "SecurityOpt", "Tmpfs",
                   "VolumesFrom", "GroupAdd", "Sysctls", "Ulimits")
    if any(host.get(key) for key in unsupported):
        raise RuntimeError("Custom Docker options found; refusing to drop them")
    if host.get("Memory", 0) or host.get("NanoCpus", 0) or host.get("CpuShares", 0):
        raise RuntimeError("Custom resource limits found; refusing changes")
    binds = host.get("Binds") or []
    if len(binds) > 1 or (binds and binds[0].split(":")[:2] != [volume, "/data"]):
        raise RuntimeError("Unsupported Docker volume binding")
    caps_add = sorted(host.get("CapAdd") or [])
    caps_drop = sorted(host.get("CapDrop") or [])
    if caps_add not in ([], ["NET_BIND_SERVICE"]) or caps_drop not in ([], ["ALL"]):
        raise RuntimeError("Custom capabilities found; refusing changes")
    restart = (host.get("RestartPolicy") or {}).get("Name", "no")
    if restart not in ("unless-stopped", "always"):
        raise RuntimeError("Unsupported restart policy; refusing changes")
    args = ["docker", "create", "--name", NAME, "--network", "host",
            "--restart", restart]
    for cap in caps_drop:
        args.extend(["--cap-drop", cap])
    for cap in caps_add:
        args.extend(["--cap-add", cap])
    spec = volume + ":/data"
    if mode:
        spec += ":" + mode
    args.extend(["--volume", spec])
    # Container environment is explicitly preserved (including port overrides).
    for item in cfg.get("Env") or []:
        args.extend(["--env", item])
    if cfg.get("User"):
        args.extend(["--user", cfg["User"]])
    if cfg.get("WorkingDir"):
        args.extend(["--workdir", cfg["WorkingDir"]])
    # Entrypoint/Cmd must be the image defaults; checked before downtime.
    args.append(image_id)
    return args


def check_image_defaults(info):
    original = json.loads(docker("image", "inspect", info["Image"]))[0]["Config"]
    for field in ("Entrypoint", "Cmd"):
        if info["Config"].get(field) != original.get(field):
            raise RuntimeError("Custom " + field + " found; refusing changes")


def save_backup(source):
    if not source.is_dir():
        raise RuntimeError("Mounted volume source unavailable; refusing update")
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    STATE.chmod(0o700)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = STATE / ("moonlightweb-data-" + stamp + ".tar.gz")
    with path.open("xb") as target:
        os.fchmod(target.fileno(), 0o600)
        with tarfile.open(fileobj=target, mode="w:gz") as archive:
            archive.add(source, arcname="data", recursive=True)
    return stamp, path


def verify():
    for _ in range(40):
        current = inspect()
        if not current["State"]["Running"]:
            raise RuntimeError("MoonlightWeb exited after upgrade")
        health = (current["State"].get("Health") or {}).get("Status")
        if health == "unhealthy":
            raise RuntimeError("MoonlightWeb health check failed")
        if health in (None, "healthy"):
            try:
                # Capture and discard output; --status can print the access PIN.
                docker("exec", NAME, "moonlightweb", "--status")
                return
            except subprocess.CalledProcessError:
                pass
        time.sleep(1)
    raise RuntimeError("MoonlightWeb did not become healthy")


def status():
    info = inspect()
    volume, _, _ = volume_from(info)
    print("MoonlightWeb:", "running" if info["State"]["Running"] else "stopped")
    print("Image:", info["Config"]["Image"])
    print("Image ID:", info["Image"])
    print("Data volume:", volume)
    sessions = active_wolf_apps()
    print("Active Wolf app sessions:", ", ".join(sessions) if sessions else "none")
    print("Updates are manual; Docker restart policy is not auto-update.")


def update():
    if active_wolf_apps():
        raise RuntimeError("Wolf app session active. Update deferred to protect desktop state")
    old = inspect()
    args_probe = recreate_args(old, old["Image"])
    check_image_defaults(old)
    if not old["State"]["Running"]:
        raise RuntimeError("MoonlightWeb is not running; inspect before updating")
    print("Pulling MoonlightWeb without disturbing running services...", flush=True)
    docker("pull", IMAGE)
    new_id = json.loads(docker("image", "inspect", IMAGE))[0]["Id"]
    if new_id == old["Image"]:
        print("Already running the current pulled image; no changes made.")
        return
    # Validate replacement arguments and inspect BEFORE any interruption.
    args = recreate_args(old, new_id)
    if args_probe[:-1] != args[:-1]:
        raise RuntimeError("Unexpected recreation argument drift")
    if active_wolf_apps():
        raise RuntimeError("Wolf app session started; update deferred")
    _, source, _ = volume_from(old)
    print("MoonlightWeb will briefly stop. Wolf will not be touched.", flush=True)
    stopped = False
    renamed = False
    created = False
    previous_policy = old["HostConfig"]["RestartPolicy"]["Name"]
    old_name = None
    try:
        docker("stop", "--time", "20", NAME)
        stopped = True
        stamp, backup_path = save_backup(source)
        old_name = BACKUP_PREFIX + stamp
        # Retain old container and immutable image for manual recovery.
        docker("update", "--restart=no", NAME)
        docker("rename", NAME, old_name)
        renamed = True
        subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        created = True
        docker("start", NAME)
        verify()
        print("MoonlightWeb update verified.")
        print("Private backup:", backup_path)
        print("Previous container retained:", old_name)
        print("Reopen Web Gaming and reconnect to Wolf Studio Desktop.")
    except Exception:
        print("Update failed. Attempting to restore the prior container.", file=sys.stderr)
        if created:
            subprocess.run(["docker", "rm", "-f", NAME], capture_output=True)
        if renamed:
            docker("rename", old_name, NAME)
        if stopped:
            docker("update", "--restart=" + previous_policy, NAME)
            docker("start", NAME)
        print("IMPORTANT: Existing /data volume was not deleted. Inspect the",
              "private data backup before downgrading after a schema migration.",
              file=sys.stderr)
        raise


def menu():
    status()
    print("\n1. Check status\n2. Update MoonlightWeb (deferred while Wolf apps run)\n0. Exit")
    option = input("Choose: ").strip()
    if option == "1":
        status()
    elif option == "2":
        if input('Type UPDATE to confirm: ').strip() == "UPDATE":
            update()
        else:
            print("Cancelled; no changes made.")
    elif option != "0":
        raise RuntimeError("Unknown option")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("status", "update", "menu"):
        print("Usage: moonlightweb-maintenance {status|update|menu}", file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        print("Run with sudo on the OptiPlex server", file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        {"status": status, "update": update, "menu": menu}[sys.argv[1]]()
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError,
            KeyError, IndexError, EOFError) as exc:
        # Do not print Docker stderr, which may contain sensitive environment.
        print("MoonlightWeb maintenance failed:", type(exc).__name__,
              str(exc) if isinstance(exc, RuntimeError) else "", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
