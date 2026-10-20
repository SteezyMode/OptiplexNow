#!/usr/bin/env python3
"""Non-disruptive Docker create acceptance test for the MoonlightWeb updater.

Creates a disposable *stopped* container with the current image and the updater's
recreation flags, using a NEW empty test volume. It neither starts the test
container nor changes moonlightweb, Wolf, Caddy, or production /data.
Run on the reference server with access to the local Docker daemon.
"""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "moonlightweb_maintenance", ROOT / "server" / "moonlightweb-maintenance.py")
mw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mw)


def command(*args):
    return subprocess.run(["docker", *args], text=True, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def main():
    name = "now-mw-create-test-" + uuid.uuid4().hex[:12]
    volume = name + "-data"
    made_volume = False
    made_container = False
    try:
        info = mw.inspect()
        # All compatibility/safety checks must pass before creating a fixture.
        mw.recreate_args(info, info["Image"], Path("/unused"))
        mw.check_image_defaults(info)
        command("volume", "create", volume)
        made_volume = True
        with tempfile.TemporaryDirectory(prefix="now-mw-create-") as tmp:
            env = Path(tmp) / "empty.env"
            env.write_text("TZ=Asia/Tokyo\n")
            args = mw.recreate_args(info, info["Image"], env)
            args[args.index("--name") + 1] = name
            old_mount = args[args.index("--volume") + 1]
            mode_suffix = old_mount.partition(":/data")[2]
            args[args.index("--volume") + 1] = volume + ":/data" + mode_suffix
            subprocess.run(args, check=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
            made_container = True
            created = mw.inspect(name)
            old_host, new_host = info["HostConfig"], created["HostConfig"]
            for key in ("Memory", "MemorySwap", "NanoCpus", "CapAdd", "CapDrop",
                        "SecurityOpt", "NetworkMode"):
                assert old_host.get(key) == new_host.get(key), (
                    "Recreation mismatch: " + key)
            mounted = created["Mounts"]
            assert len(mounted) == 1 and mounted[0]["Name"] == volume
            assert mounted[0]["Destination"] == "/data"
            assert not created["State"]["Running"]
            print("PASS: disposable Docker create preserved memory, swap, CPU,")
            print("capabilities, security, network and /data mount.")
            print("No production container stopped or modified.")
    finally:
        # Always clean up the known, unique fixture; never use a broad prune.
        if made_container:
            command("rm", "-f", name)
        if made_volume:
            command("volume", "rm", volume)
        print("Temporary test container and volume removed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, AssertionError,
            subprocess.CalledProcessError) as exc:
        print("Acceptance test failed:", type(exc).__name__, file=sys.stderr)
        sys.exit(1)
