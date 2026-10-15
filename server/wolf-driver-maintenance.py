#!/usr/bin/env python3
"""Wolf NVIDIA driver volume maintenance for OptiPlex Now.

Requires an existing, manually managed Wolf Docker container. No secrets are
sent off-host; Docker inspection snapshots stay root-private on the server.
"""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

STATE = Path("/var/lib/optiplex-now")
CONTAINER = "wolf"
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)*$")
DOCKERFILE_URL = (
    "https://raw.githubusercontent.com/games-on-whales/gow/master/"
    "images/nvidia-driver/Dockerfile"
)


def run(*args, capture=False):
    return subprocess.run(args, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def output(*args):
    return run(*args, capture=True).stdout.strip()


def docker(*args):
    return output("docker", *args)


def inspect(name):
    return json.loads(docker("inspect", name))[0]


def driver_version():
    version = output("nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader").splitlines()[0]
    if not VERSION_RE.fullmatch(version):
        raise RuntimeError("Unexpected NVIDIA version: " + version)
    return version


def configured_volume(info):
    entries = [e.split("=", 1)[1] for e in info["Config"]["Env"]
               if e.startswith("NVIDIA_DRIVER_VOLUME_NAME=")]
    if len(entries) != 1:
        raise RuntimeError("Wolf has no unique NVIDIA_DRIVER_VOLUME_NAME")
    return entries[0]


def is_running(name):
    return inspect(name)["State"]["Running"]


def matching(version):
    return "wolf-nvidia-driver-" + version


def ensure_driver_volume(version):
    volume = matching(version)
    try:
        docker("volume", "inspect", volume)
        return volume
    except subprocess.CalledProcessError:
        pass
    image = "gow/nvidia-driver:" + version
    with tempfile.TemporaryDirectory(prefix="optiplex-now-nvidia-") as temp:
        dockerfile = Path(temp) / "Dockerfile"
        run("curl", "--fail", "--silent", "--show-error", "--location",
            DOCKERFILE_URL, "--output", str(dockerfile))
        run("docker", "build", "-t", image, "--build-arg", "NV_VERSION=" + version,
            "-f", str(dockerfile), temp)
    init_name = "optiplex-now-nvidia-init-" + str(os.getpid())
    try:
        docker("create", "--name", init_name, "-v", volume + ":/usr/nvidia",
               image, "/bin/sh")
    finally:
        subprocess.run(["docker", "rm", "-f", init_name], capture_output=True)
    # Ensure the volume actually contains the driver, not an empty directory.
    if not Path("/var/lib/docker/volumes").exists():
        raise RuntimeError("Docker volume storage could not be verified")
    run("docker", "run", "--rm", "-v", volume + ":/usr/nvidia:ro",
        "ubuntu:22.04", "test", "-f", "/usr/nvidia/lib/libcuda.so." + version)
    return volume


def snapshot(info):
    STATE.mkdir(parents=True, exist_ok=True)
    STATE.chmod(0o700)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = STATE / ("wolf-" + stamp + ".json")
    with path.open("x") as fh:
        json.dump(info, fh, indent=2)
    path.chmod(0o600)
    return stamp


def recreate_args(info, volume):
    host = info["HostConfig"]
    if host["NetworkMode"] != "host" or host["Privileged"]:
        raise RuntimeError("Unsupported Wolf network/privilege configuration; no changes made")
    if host.get("Binds") or host.get("Mounts") or host.get("CapAdd") or host.get("SecurityOpt"):
        raise RuntimeError("Unsupported extra Docker host options; no changes made")
    args = ["docker", "create", "--name", CONTAINER, "--network", "host",
            "--restart", host["RestartPolicy"]["Name"] or "unless-stopped"]
    for item in info["Config"]["Env"]:
        if item.startswith("NVIDIA_DRIVER_VOLUME_NAME="):
            item = "NVIDIA_DRIVER_VOLUME_NAME=" + volume
        args += ["-e", item]
    for mount in info["Mounts"]:
        if mount["Destination"] == "/usr/nvidia":
            source = volume
        elif mount["Type"] == "volume":
            source = mount["Name"]
        elif mount["Type"] == "bind":
            source = mount["Source"]
        else:
            raise RuntimeError("Unsupported mount type: " + mount["Type"])
        spec = source + ":" + mount["Destination"]
        if not mount["RW"]:
            spec += ":ro"
        args += ["-v", spec]
    for device in host["Devices"] or []:
        args += ["--device", device["PathOnHost"] + ":" +
                 device["PathInContainer"] + ":" + device["CgroupPermissions"]]
    args.append(info["Image"])  # immutable image identity; do not silently upgrade Wolf
    return args


def verify():
    # A running process does not mean NVENC works. Wait for Wolf's encoder probe.
    for _ in range(15):
        logs = subprocess.run(["docker", "logs", "--tail", "250", CONTAINER],
                              capture_output=True, text=True)
        data = logs.stdout + logs.stderr
        if "CUDA_ERROR_SYSTEM_DRIVER_MISMATCH" in data:
            break
        if ("Using h264 encoder: nvcodec" in data and
                "Using h265 encoder: nvcodec" in data and is_running(CONTAINER)):
            print("Wolf healthy: NVIDIA H.264 and H.265 encoding available")
            return
        time.sleep(2)
    raise RuntimeError("Wolf did not confirm hardware encoding; check docker logs wolf")


def boot():
    if Path("/usr/local/sbin/wolf-prepare-devices").exists():
        run("/usr/local/sbin/wolf-prepare-devices")
    version = driver_version()
    info = inspect(CONTAINER)
    desired = matching(version)
    if configured_volume(info) == desired:
        if not info["State"]["Running"]:
            docker("start", CONTAINER)
        print("Wolf NVIDIA driver is current:", version)
        return

    # Do not interrupt an active streaming session during a manual service restart.
    uptime = float(Path("/proc/uptime").read_text().split()[0])
    if info["State"]["Running"] and uptime > 300:
        print("Wolf update deferred: container running outside boot window; reboot to apply",
              file=sys.stderr)
        return

    print("Wolf NVIDIA driver mismatch; preparing", version, flush=True)
    volume = ensure_driver_volume(version)
    # Preflight full creation arguments BEFORE stopping the existing container.
    args = recreate_args(info, volume)
    stamp = snapshot(info)
    backup = "wolf-preupdate-" + stamp
    previous_restart = info["HostConfig"]["RestartPolicy"]["Name"] or "no"
    old_stopped = False
    old_renamed = False
    try:
        if info["State"]["Running"]:
            docker("stop", "--time", "20", CONTAINER)
            old_stopped = True
        docker("update", "--restart=no", CONTAINER)
        docker("rename", CONTAINER, backup)
        old_renamed = True
        run(*args)
        docker("start", CONTAINER)
        verify()
        print("Wolf updated; rollback container retained:", backup)
    except Exception:
        print("Wolf update failed. Restoring previous container.", file=sys.stderr)
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
        if old_renamed:
            docker("rename", backup, CONTAINER)
        docker("update", "--restart=" + previous_restart, CONTAINER)
        if info["State"]["Running"]:
            docker("start", CONTAINER)
        raise


def install():
    if os.geteuid() != 0:
        raise RuntimeError("Run installation with sudo")
    if not Path("/etc/systemd/system/wolf-start.service").exists():
        raise RuntimeError("Existing wolf-start.service missing; refusing to invent a service")
    inspect(CONTAINER)
    directory = Path("/etc/systemd/system/wolf-start.service.d")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "50-optiplex-now-maintenance.conf"
    if path.exists():
        if path.read_text().strip() == (
            "[Service]\nExecStart=\nExecStart=/usr/lib/optiplex-now/"
            "wolf-driver-maintenance boot"
        ):
            print("Wolf maintenance already installed")
            return
        raise RuntimeError("Existing drop-in found; refusing to overwrite " + str(path))
    path.write_text("[Service]\nExecStart=\n"
                    "ExecStart=/usr/lib/optiplex-now/wolf-driver-maintenance boot\n")
    run("systemctl", "daemon-reload")
    print("Wolf driver maintenance installed for next wolf-start.service execution")
    print("No service was restarted.")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("status", "boot", "install"):
        print("Usage: wolf-driver-maintenance {status|boot|install}", file=sys.stderr)
        return 2
    try:
        if sys.argv[1] == "status":
            info = inspect(CONTAINER)
            host = driver_version()
            print("Host:", host, "Wolf:", configured_volume(info),
                  "Running:", info["State"]["Running"])
            return 0 if configured_volume(info) == matching(host) else 1
        if sys.argv[1] == "install":
            install()
        else:
            if os.geteuid() != 0:
                raise RuntimeError("boot requires sudo")
            boot()
        return 0
    except (RuntimeError, subprocess.CalledProcessError, KeyError, OSError) as exc:
        print("Wolf maintenance:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
