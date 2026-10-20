# Web Gaming maintenance (MoonlightWeb)

**Scope:** First-stage adoption of an **existing standalone** Docker
MoonlightWeb installation. This is not a fresh-server installer, an unattended
updater, or a Wolf/Studio desktop updater. No systemd timer is installed.

## Non-negotiable boundaries

- Never stop, rename, update, or delete the Wolf daemon or any Wolf app
  container. Updates are refused while a running `WolfStudioDesktop_*`,
  `WolfSteam_*` or similar Wolf application container is detected.
- Leave the existing Docker `/data` volume attached to MoonlightWeb. It holds
  certificates, host pairings, PIN/admin settings and Moonlight client identity.
- Keep current Caddy, domain, host networking and custom 8443/8080 environment
  overrides intact. MoonlightWeb's web public URL is **not** an SSH endpoint.
- Do not remove the old image/container or delete the data volume to clean up.
- A running Wolf application container is a conservative detection signal,
  not a universal guarantee of session persistence: Wolf controls lifecycle of
  graphical sessions. Unsaved Blender/Godot windows are NOT preserved by
  project bind mounts alone.
- Restore tests and compatibility between old/new `/data` schemas are not yet
  verified. An on-disk backup is retained, but **not automatically restored**.

## Supported reference configuration

The reference host (Oct 20, 2026) uses:

| Property | Value |
| --- | --- |
| Container | `moonlightweb` (standalone, not Compose-managed) |
| Image | `ghcr.io/linckosz/moonlight-web:latest` |
| Network | host |
| Volume | `moonlightweb-test-data:/data:z` |
| Public URL | `https://games.monumentrisk.com` via existing Caddy |

The manager inspects actual Docker state; only this narrow configuration family
is accepted. It refuses additional mounts, privileged/custom device settings,
Compose management, custom entrypoints, unknown capabilities and unsupported
restart policies rather than silently dropping Docker options. Do not assume
that every MoonlightWeb deployment has this shape.

## Install/operate

The NOW package contains two different helpers:

- `/usr/lib/optiplex-now/moonlightweb-maintenance`: server-side privileged
  updater; NOW must be installed **on the host** for this to exist.
- `/usr/lib/optiplex-now/web-gaming-maintenance`: client-side SSH launcher.

After installing the proposed package on both the host and a Linux client,
open **NOW → Settings → WEB GAMING MAINTENANCE**. It opens an interactive terminal
using the configured server address and SSH user; select status or update.
This is **not** an unattended update. The server's `sudo` policy still applies.
No Docker socket is copied or exposed to clients.

On the host, the equivalent explicit commands are:

```sh
sudo /usr/lib/optiplex-now/moonlightweb-maintenance status
sudo /usr/lib/optiplex-now/moonlightweb-maintenance preflight
sudo /usr/lib/optiplex-now/moonlightweb-maintenance menu
```

The menu includes a read-only preflight that checks the supported container configuration and persistent volume. It does not download images or stop services. The menu asks for `UPDATE` before changing anything. **Do not update while
someone is streaming**, especially from a Wolf Studio Desktop. The script checks
for running Wolf application containers again immediately before stopping
MoonlightWeb, but session detection is conservative and not exhaustive.

The update workflow is:

1. Inspect container settings and reject unsupported layouts.
2. Pull the new upstream image **while MoonlightWeb remains running**.
3. If the image digest is unchanged, exit with no downtime.
4. Refuse the change if Wolf application containers are active.
5. Stop **only** `moonlightweb` and save a root-private tarball under
   `/var/lib/optiplex-now/moonlightweb/`.
6. Rename and retain the stopped prior MoonlightWeb container.
7. Create the new MoonlightWeb container with the **same data volume**, port
   environment, host network and Docker restart policy.
8. Confirm Docker health and the backend `moonlightweb --status` readiness.
   On an error, attempt to restore the previous container. **The backup tarball
   is not automatically extracted**; inspect version/schema compatibility
   before restoring data after a failed migration.

The status command displays no access PIN or admin password. Docker image
and volume metadata are still sensitive on the host; keep backups root-private.
Never commit `/data`, credentials, access token files, or inspect dumps.

## Release gate

This branch requires unit tests, GTK/package CI, reference-machine inspection,
and a tested rollback using a disposable duplicate of the persistent volume.
Then test web-stream reconnect with a fresh Wolf Studio desktop before enabling
updates on the production server. No update, service restart or new .deb
deployment was performed simply by merging this code.

## Wolf desktop persistence caveat

Upstream stable Wolf documents `WOLF_STOP_CONTAINER_ON_EXIT=TRUE` as its default, which can end a desktop application container when streaming stops. The updater deliberately refuses to update while Wolf application containers are running. It therefore **does not yet** deliver an uninterrupted live desktop across a MoonlightWeb update. Preserving Studio project files and Wolf application home directories is a separate guarantee from preserving running GUI programs and unsaved edits. Confirm the actual Wolf setting and test a disconnect/reconnect before changing update policy.

## Future milestones

Once validated: installer/adoption wizard, version pinning and published update
notice, per-service update channels, active-session detection through supported
Wolf APIs, off-host encrypted backups, tested data restore, and opt-in automatic
maintenance windows. Do not install Watchtower across unrelated services.
