#!/usr/bin/env python3
"""Disposable Docker rollback mechanics test; NEVER operates on production names.

Tests the stop-free rename/replacement/remove/restore lifecycle with stopped
containers and a fresh volume. This does not prove a complete live update,
application health checks or on-disk schema migration compatibility.
"""
import json
import subprocess
import sys
import uuid


def docker(*args):
    return subprocess.run(["docker", *args], check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def exists(name):
    p = subprocess.run(["docker", "inspect", name], text=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.returncode == 0


def main():
    ident = uuid.uuid4().hex[:12]
    base = "now-mw-rollback-test-" + ident
    prior = base + "-previous"
    volume = base + "-data"
    # Read image ID only: do not pull, stop, or modify the live container.
    production = json.loads(docker("inspect", "moonlightweb"))[0]
    image = production["Image"]
    created_volume = False
    old_id = None
    try:
        docker("volume", "create", volume)
        created_volume = True
        docker("create", "--name", base, "--network", "none",
               "--restart", "no", "--volume", volume + ":/data", image)
        old_id = json.loads(docker("inspect", base))[0]["Id"]
        assert not json.loads(docker("inspect", base))[0]["State"]["Running"]
        docker("rename", base, prior)
        try:
            docker("create", "--name", base, "--network", "none",
                   "--restart", "no", "--volume", volume + ":/data", image)
            new_id = json.loads(docker("inspect", base))[0]["Id"]
            assert new_id != old_id
            raise RuntimeError("Injected replacement health failure")
        except RuntimeError as exc:
            assert str(exc) == "Injected replacement health failure"
            if exists(base):
                docker("rm", "-f", base)
            docker("rename", prior, base)
        recovered = json.loads(docker("inspect", base))[0]
        assert recovered["Id"] == old_id, "Original container was not recovered"
        assert recovered["Mounts"][0]["Name"] == volume
        assert not recovered["State"]["Running"]
        print("PASS: deliberately failed replacement removed")
        print("PASS: original stopped container restored by identity")
        print("PASS: disposable persistent volume retained through rollback")
        print("No production container or volume was altered.")
    finally:
        for name in (base, prior):
            if exists(name):
                docker("rm", "-f", name)
        if created_volume:
            docker("volume", "rm", volume)
        print("Disposable test containers and volume removed.")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError, KeyError, IndexError,
            subprocess.CalledProcessError, OSError) as exc:
        print("FAIL: disposable rollback mechanics test:", type(exc).__name__,
              file=sys.stderr)
        sys.exit(1)
