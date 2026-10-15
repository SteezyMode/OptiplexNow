# Wolf NVIDIA maintenance (opt-in)

This tool is part of OptiPlex Now's .deb as of 1.12.0. It is a **server-side utility**, not a new-server installer. The client remains usable without Wolf, Docker or an NVIDIA GPU.

## Supported starting point

An existing Linux server with a working `wolf` Docker container using a manually managed `NVIDIA_DRIVER_VOLUME_NAME=wolf-nvidia-driver-VERSION`, an existing `wolf-start.service`, and NVIDIA drivers accessible through `nvidia-smi`. It has been designed against the reference setup, not tested on a clean server or a production upgrade. Inspect and back up the server before enabling it. This does not install Docker, Wolf, NVIDIA drivers or Tailscale.

## Install on the *server*

Install OptiPlex Now 1.12.0+ on the server, or copy the packaged script to `/usr/lib/optiplex-now/wolf-driver-maintenance` as root. This server-side action is **not automatically performed by installing the GUI on another machine**.

```sh
sudo /usr/lib/optiplex-now/wolf-driver-maintenance status
sudo /usr/lib/optiplex-now/wolf-driver-maintenance install
```

The install command adds a systemd **drop-in** for the existing `wolf-start.service`; it does not immediately restart Wolf. Its next execution prepares NVIDIA devices and checks the installed driver version. If the versions match, it starts Wolf if necessary. If they differ, it builds a version-matched `gow/nvidia-driver` image/volume, saves a root-only inspect snapshot in `/var/lib/optiplex-now`, creates a replacement container, verifies NVENC H.264/H.265, and keeps the renamed prior container as a rollback point. If verification fails, it attempts to restore the old container. The old driver may still be incompatible with the updated host driver, so this cannot guarantee streaming after a failed update.

At a manual service restart **outside the first five minutes of boot**, a running Wolf container is left alone; apply the update at the next boot instead. This avoids dropping ongoing streams. This is not an automatic periodic updater and does not handle NVIDIA OS-driver installation.

The script intentionally refuses unsupported configurations instead of guessing how to recreate extra Docker host settings. Inspect logs with `journalctl -u wolf-start.service -b`. The underlying Docker definition must stay backed up separately; `/etc/wolf` and game storage are not included in the inspect snapshot.

## Rollback / disable

Disable the automatic check without uninstalling the client:

```sh
sudo rm /etc/systemd/system/wolf-start.service.d/50-optiplex-now-maintenance.conf
sudo systemctl daemon-reload
```

The original `wolf-start.service` will once again start the named `wolf` container. It will **not** automatically switch back to an older renamed backup. For manual recovery, inspect `docker ps -a` and the root-only saved metadata before renaming or starting containers. Do not delete `/etc/wolf`, Docker volumes, or game directories as part of rollback.

## Roadmap

New server provisioning, existing-server discovery, repair after network/VPN changes, a non-GUI server package, snapshot restore tests, CI builds, configurable health checks, and managed update windows are future work. No secrets, GPU driver binaries or machine-specific paths are committed to this repository.
