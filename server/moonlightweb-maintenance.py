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
import tempfile
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


def recreate_args(info, image_id, env_file):
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
                   "ExtraHosts", "Dns", "DnsSearch", "Tmpfs",
                   "VolumesFrom", "GroupAdd", "Sysctls", "Ulimits")
    if any(host.get(key) for key in unsupported):
        raise RuntimeError("Custom Docker options found; refusing to drop them")
    security_opts = host.get("SecurityOpt") or []
    # This is a defense-in-depth setting in the reference deployment.
    # Preserve it exactly; reject other/unrecognized security overrides.
    if security_opts not in ([], ["no-new-privileges"]):
        raise RuntimeError("Unsupported Docker security options; refusing to drop them")
    # Preserve supported memory and fractional CPU quotas exactly.
    # Docker reports the memory limit in bytes and CPU quota in nanocpus.
    memory = host.get("Memory") or 0
    memory_swap = host.get("MemorySwap") or 0
    nano_cpus = host.get("NanoCpus") or 0
    if (type(memory) is not int or memory < 0
            or type(memory_swap) is not int or memory_swap < -1
            or (memory_swap not in (0, -1) and (not memory or memory_swap < memory))
            or type(nano_cpus) is not int or nano_cpus < 0):
        raise RuntimeError("Invalid Docker resource limits")
    # Avoid silently dropping other resource controls we don't yet recreate.
    if host.get("CpuShares") or any(host.get(key) for key in (
            "CpuPeriod", "CpuQuota", "CpuRtPeriod", "CpuRtRuntime",
            "CpusetCpus", "CpusetMems", "MemoryReservation",
            "PidsLimit", "OomKillDisable", "CgroupParent", "BlkioWeight")
            ) or host.get("MemorySwappiness") not in (None, -1):
        # -1 is Docker's default (unspecified) swappiness.
        raise RuntimeError("Unsupported additional resource limits; refusing changes")
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
    for option in security_opts:
        args.extend(["--security-opt", option])
    if memory:
        args.extend(["--memory", str(memory) + "b"])
    if memory_swap:
        args.extend(["--memory-swap", str(memory_swap) + "b" if memory_swap > 0 else "-1"])
    if nano_cpus:
        # Format without floating-point rounding; 1_000_000_000 == 1 CPU.
        cpu_limit = ("%d.%09d" % divmod(nano_cpus, 1_000_000_000)).rstrip("0").rstrip(".")
        args.extend(["--cpus", cpu_limit])
    spec = volume + ":/data"
    if mode:
        spec += ":" + mode
    args.extend(["--volume", spec])
    # Never expose PINs/tokens through Docker command-line arguments.
    args.extend(["--env-file", str(env_file)])
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


def write_private_env(info):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    STATE.chmod(0o700)
    fd, raw_path = tempfile.mkstemp(prefix=".moonlightweb-env-", dir=STATE)
    path = Path(raw_path)
    try:
        with os.fdopen(fd, "w") as handle:
            for item in info["Config"].get("Env") or []:
                key, sep, _ = item.partition("=")
                if (not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
                        or "\n" in item or "\r" in item):
                    raise RuntimeError("Unsupported environment entry")
                handle.write(item + "\n")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


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


def preflight():
    """Read-only validation, without pulling images or changing containers."""
    info = inspect()
    _ = recreate_args(info, info["Image"], STATE / ".never-written-preflight")
    check_image_defaults(info)
    if not info["State"]["Running"]:
        raise RuntimeError("MoonlightWeb is not running")
    volume, source, _ = volume_from(info)
    if not source.is_dir():
        raise RuntimeError("MoonlightWeb persistent data volume unavailable")
    sessions = active_wolf_apps()
    print("MoonlightWeb supported standalone deployment: YES")
    print("Current data volume:", volume)
    print("Wolf application containers:", ", ".join(sessions) if sessions else "none")
    print("Update allowed now:", "NO — active Wolf app containers" if sessions else "YES")
    print("No changes made.")


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
    sentinel = STATE / ".never-written-preflight"
    args_probe = recreate_args(old, old["Image"], sentinel)
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
    args = recreate_args(old, new_id, sentinel)
    if args_probe[:-1] != args[:-1]:
        raise RuntimeError("Unexpected recreation argument drift")
    if active_wolf_apps():
        raise RuntimeError("Wolf app session started; update deferred")
    _, source, _ = volume_from(old)
    print("MoonlightWeb will briefly stop. Wolf will not be touched.", flush=True)
    stopped = False
    renamed = False
    old_container_id = old["Id"]
    previous_policy = old["HostConfig"]["RestartPolicy"]["Name"]
    old_name = None
    env_file = None
    try:
        docker("stop", "--time", "20", NAME)
        stopped = True
        stamp, backup_path = save_backup(source)
        old_name = BACKUP_PREFIX + stamp
        # Retain old container and immutable image for manual recovery.
        docker("update", "--restart=no", NAME)
        docker("rename", NAME, old_name)
        renamed = True
        env_file = write_private_env(old)
        args = recreate_args(old, new_id, env_file)
        subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        docker("start", NAME)
        verify()
        print("MoonlightWeb update verified.")
        print("Private backup:", backup_path)
        print("Previous container retained:", old_name)
        print("Reopen Web Gaming and reconnect to Wolf Studio Desktop.")
    except Exception:
        print("Update failed. Attempting to restore the prior container.", file=sys.stderr)
        if renamed:
            # docker create can leave a container even when its command fails.
            # Never remove the original container; identify any replacement by ID.
            try:
                replacement = inspect(NAME)
            except subprocess.CalledProcessError:
                replacement = None
            if replacement is not None:
                if replacement.get("Id") == old_container_id:
                    raise RuntimeError("Rollback blocked: original container still owns live name")
                docker("rm", "-f", NAME)
            docker("rename", old_name, NAME)
        if stopped:
            docker("update", "--restart=" + previous_policy, NAME)
            docker("start", NAME)
        print("IMPORTANT: Existing /data volume was not deleted. Inspect the",
              "private data backup before downgrading after a schema migration.",
              file=sys.stderr)
        raise
    finally:
        if env_file is not None:
            env_file.unlink(missing_ok=True)


def menu():
    status()
    print("\n1. Check status\n2. Update MoonlightWeb (deferred while Wolf apps run)\n3. Read-only preflight\n0. Exit")
    option = input("Choose: ").strip()
    if option == "1":
        status()
    elif option == "2":
        if input('Type UPDATE to confirm: ').strip() == "UPDATE":
            update()
        else:
            print("Cancelled; no changes made.")
    elif option == "3":
        preflight()
    elif option != "0":
        raise RuntimeError("Unknown option")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("status", "preflight", "update", "menu"):
        print("Usage: moonlightweb-maintenance {status|preflight|update|menu}", file=sys.stderr)
        return 2
    if os.geteuid() != 0:
        print("Run with sudo on the OptiPlex server", file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        {"status": status, "preflight": preflight, "update": update, "menu": menu}[sys.argv[1]]()
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError,
            KeyError, IndexError, EOFError) as exc:
        # Do not print Docker stderr, which may contain sensitive environment.
        print("MoonlightWeb maintenance failed:", type(exc).__name__,
              str(exc) if isinstance(exc, RuntimeError) else "", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
