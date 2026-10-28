# NOW Host installer

**State: experimental, unaccepted installation candidate.** The [published v1.18.0 closed-beta](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.18.0) includes an opt-in guarded advanced Wolf host installer, but it has not passed clean physical host installation, encoder or gameplay acceptance. On current source, an opt-in, privileged installation path exists for *clean* Ubuntu 24.04 and Pop!_OS 24.04 amd64 hosts with AMD, Intel or NVIDIA graphics. A complete installation and working game stream have **not** been validated on independent physical hardware. Track completion in [#98](https://github.com/SteezyMode/OptiplexNow/issues/98).

This document is the authoritative **Wolf-only host technical-alpha** contract for new NOW-managed hosts, not a general server installer. The **public entertainment-server alpha** additionally requires guided Jellyfin and VPN-isolated qBittorrent with strict owner/member roles; see [Public-alpha contract](PUBLIC-ALPHA.md). [Product direction](PRODUCT.md), [current verification](CURRENT-STATUS.md) and [private client beta](BETA-ACCEPTANCE.md) cover separate stages.

## Read-only GPU target suggestion (development branch)

The ordinary **Check This PC** review now asks the packaged installer to
suggest a GPU and DRM render node. A suggestion is made **only when exactly
one** supported AMD, Intel or NVIDIA render device has a matching kernel
`/sys/class/drm/renderD*/device/vendor` mapping and the device is a
character device. Multi-GPU, missing, mismatched or unknown devices are **not
guessed**: choose GPU and render node explicitly and use the existing
eligibility check. The old blanket AMD + renderD128 defaults are removed.
Manual choices edited while a scan runs are preserved.

Detection is read-only, requires neither root nor Docker permissions, and
never enables installation. The administrator check still verifies the
selected GPU/render node and all other prerequisites before changing host
state. This is a developer-branch improvement, not a clean-host/gameplay
acceptance claim. Docker, immutable Wolf image choice, NVIDIA driver hash,
stream verification, client pairing and safe recovery remain separate gates.

## Existing Jellyfin host review (source-only, Private Alpha Videos)

The separate Server Setup window includes **VIDEOS | USE EXISTING JELLYFIN...**. The opt-in GTK window calls `host_media_adoption.py --inspect` to check only the fixed host-local Jellyfin `127.0.0.1:8096/System/Info/Public` endpoint without Docker access, configuration changes or credentials. It reports when an owner-only approved route already exists. A missing or unsafe route file is not overwritten.

After a successful local Jellyfin check, the host owner may explicitly approve a *same-host* scheme, port and single short base path through a confirmation dialog. A separate unprivileged helper validates the fields with the same allowlist as the restricted host media reply and creates only `~/.config/optiplex-now/media-public-endpoint.json` at mode `0600`, refusing pre-existing files, symlinks, root execution or unsafe directories. It does **not** configure Jellyfin, Caddy, TLS, firewalls, external hostnames, libraries or accounts; client reachability and verified playback remain separate acceptance gates. This is not a managed Jellyfin installation or complete guided adoption for every host topology. To change an already approved route, manual owner review is still required; do not casually remove it to retry.


## Existing-server shared storage review (read-only, no adoption)

On a host that **already has** Jellyfin and qBittorrent, choose **Server Setup → VERIFY EXISTING SERVICES (OS APPROVAL)**. The fixed read-only Docker census now includes a **MEDIA / DOWNLOADS SHARED STORAGE** hint in the existing host review. It compares only Docker bind-mount source metadata on one unambiguous Jellyfin container and one qBittorrent container: same source, nested sources, no shared binds observed, missing binds, or unknown/ambiguous. It neither opens paths nor returns host directories, container IDs, Docker credentials, torrent save paths, library roots, or suggested new mounts to the client.

**Important:** a shared bind mount is not proof that a qBittorrent save destination is inside a Jellyfin library, that symlinks resolve safely, or that account permissions allow file management. The status is a **candidate only** and grants no file browsing, file mutation, installation, downloader action, storage mapping, or user roles. It preserves existing media, library metadata, VueTorrent, Gluetun and the current Caddy reverse proxy. A read-only fixed `systemctl is-active jellyfin.service` check also recognizes a **native Jellyfin + Docker qBittorrent** candidate, as on the working reference OptiPlex. Its result is explicitly `native_jellyfin_library_mapping_unverified`: no library folder mapping can be inferred from a native service and a Docker volume alone. Multiple Jellyfin containers, unavailable Docker metadata or a missing downloader remain unknown. Do not install a second Jellyfin instance or invent storage mappings.

The next gated step is an **explicit owner-approved storage-root mapping** from real host inspection: canonical host paths, per-container media/save folder mapping, and server-side path containment. That cannot be inferred safely from general container image names or solved via broad SFTP. Physical and owner-permission verification will still be required.

## Clean-host Jellyfin pilot (development, NOT physically accepted)

The separate **Videos | Use Existing Jellyfin** window now offers **Set Up New Jellyfin on a Clean Host**. This is deliberately not the existing-server adoption operation. It collects an existing host-owner media folder through a GTK directory picker and a **verified immutable** official `jellyfin/jellyfin@sha256:<digest>` image. The selected library is mounted read-only; Jellyfin's persistent `/config` and `/cache` are created separately with the invoking owner's UID/GID.

The flow is **check → OS authorization → recheck → explicit installation confirmation → OS authorization → one-time create**. The installer allows only Ubuntu 24.04 / Pop!_OS 24.04 amd64 with at least 5 GiB free in the NOW state filesystem, a local **Docker Engine 28.0.0+** daemon with Compose, a valid Tailscale IPv4, available TCP 8096 on both loopback and the Tailnet address, no existing Jellyfin Docker candidate and no prior NOW Jellyfin pilot state. The actual install must run with an authenticated `PKEXEC_UID` matching the GUI user and the explicit `INSTALL-JELLYFIN` confirmation.

New state is isolated at root-owned `/var/lib/optiplex-now/jellyfin-host-pilot`, with exclusive create-only journals and the unique `optiplex-now-jellyfin-pilot` Compose project. The container uses the approved UID:GID, a verified digest, no added capabilities, and read-only media bind. The requested host port mappings are `127.0.0.1:8096` and the host's Tailscale IPv4:8096, **and the installer now checks Docker's actual runtime port mappings and read-only media mount before reporting started. If those checks fail, it attempts to stop **only** the uniquely verified NOW-owned Jellyfin pilot container by exact ID, leaving its state and media intact for owner review. It never stops an ambiguous or foreign container**. Docker Engine 28.0.0+ is required because Docker documents localhost exposure to same-L2 hosts on earlier versions. Even on Docker 28+, host IP binding alone does **not** establish Tailnet-only reachability: direct routing and Docker's NAT/firewall configuration may permit additional exposure. A live LAN/outside-Tailnet denial test and Tailnet access test are mandatory before marking the install safe. No automatic Caddy update, firewall/ACL rewrite, UDP discovery or host network mode. Existing other NOW, Docker, Wolf, Jellyfin and download services are not targeted for removal or restart. Docker itself and port publishing still require explicit administrator approval.

**Important limits:** An installed container marked `running_media_unverified` is not a configured Jellyfin account, playable library, verified client connection or alpha acceptance. Complete Jellyfin's own first-run authentication/library setup and test playback. This pilot does not enable hardware transcoding by default, acquire a verified image digest for the owner, select multiple media roots, establish fine-grained Tailscale ACLs, migrate or overwrite existing Jellyfin, or automatically repair/rollback an interrupted deployment. A stale or partial state blocks retry until inspected. Do not run on the working reference OptiPlex; test only separate disposable compatible host hardware.

Source: Jellyfin's official container instructions require persistent config/cache and support read-only media bind mounts. Docker's Compose documentation warns that omitting the host IP exposes published ports on all interfaces. Both guide this deliberately scoped pilot; actual host behavior needs physical acceptance and any Docker network/firewall effects must be reviewed first.

## Implemented path

The separate GTK window `src/host_setup.c` opens from **Settings > Connections & Server > Check This PC for Server Setup**.

1. **Review:** unprivileged read-only `host_preflight.py` and `host_plan.py` display detected prerequisites, conflicts and unknown capabilities. They make no system changes.
2. **Advanced pilot:** use the detected GPU/render node if unambiguous, or choose them manually; provide a *verified* immutable Wolf OCI `sha256:` digest. NVIDIA additionally requires a SHA256 for the official NVIDIA `.run` installer matching the **loaded** kernel driver version.
3. **Check:** `host_install.py --check` inspects real hardware, runtime prerequisites, occupied Wolf ports, driver/DRM state and existing managed paths. Non-root users need not join the Docker group; inaccessible daemon state requires a privileged recheck.
4. **Authorize:** explicit GTK confirmation and OS `pkexec` authentication precede `host_install.py --install`. The root helper rechecks eligibility and refuses existing NOW-managed workspace/project state. There is no network-facing installation API.
5. **Provision:** the helper uses only its dedicated `optiplex-now-host-pilot` Compose project, a pinned Wolf image and private `/var/lib/optiplex-now/host` state. It writes owner and phase records before starting Wolf and verifies its full container ID, image reference, Compose labels and running status.
6. **Report:** `running_stream_unverified` means only that the inspected container is running. It does **not** mean Moonlight pairing, encoding, video, audio, input or reconnection succeeded.

On clean Ubuntu/Pop!_OS 24.04 amd64 hosts, NOW offers an **optional administrator-approved Install Docker + Compose** action after a read-only APT simulation. The simulation now **rejects any Docker APT candidate below 28.0.0 or with an unverified version**, and the installer independently checks the running daemon version after installation before reporting ready. Ubuntu 24.04's amd64 `docker.io` package is already available in the 29.x series as of October 2026 (verify the actual enabled apt candidate on each host). Pop!_OS may differ according to enabled repositories and package updates; old or ambiguous candidates block clean-host setup rather than triggering a switch to Docker CE. No Docker release channel migration or third-party APT source is automated. It installs `docker.io` and `docker-compose-v2` only when no Docker binary, socket, runtime state or conflicting package already exists. No external APT repository, Docker group membership, removals or automatic upgrades. APT can start the Docker daemon and affect NAT/firewall rules; owners are warned. Interrupted transactions require inspection, never blind automatic retries. Run **Check This PC** again before Wolf setup. Source/CI only until physically accepted.

This step does not configure kernel drivers, boot settings, firewall policy, Tailscale, Steam profiles, Jellyfin or unrelated services. It is not yet a verified 15-minute consumer host setup.

## First-Games readiness from actual Wolf config (development branch)

On an initial managed Wolf start, the installer now reports a strictly read-only
`games_readiness` object. The installed `host_games_readiness.py` helper can
inspect `/var/lib/optiplex-now/host/wolf/cfg/config.toml` later as Wolf
finishes generating default state. It does not read out or log Wolf's paired
client certificates, replace the config, adopt Steam homes or run Docker.

**Compatibility checkpoint:** Wolf configurations using `config_version = 2`
with an explicit `[[profiles]] id = "user"` and nested Steam Docker
application may be classified `named_steam_candidate`. That is only an app
and profile definition, **not** proof of Steam login, video, audio, gamepad
or an accepted game stream. More recent upstream Wolf stable source uses
`config_version = 3`, global `[[apps]]`, and a per-paired-client
`app_state_folder`. NOW classifies that as
`v3_per_device_state_requires_owner_mapping`. Never claim the user gets
one durable Steam home across devices just because Steam is listed. Wolf's
documented local client-settings API can update this mapping, but a secure
owner grant and single-writer lease must be verified before NOW automates it.
No server or profile migration is performed here.

The source inspected is an **image-sensitive upstream contract**. Before
ship, record the actual pinned Wolf digest used on the clean test host and
validate its generated schema, Steam app start and client authorization
against that digest. A missing first-boot config is `wolf_config_pending`,
not a failed installation or a healthy stream.

## Supported candidates and hard stops

| GPU | Clean-host pilot | Known gate |
| --- | --- | --- |
| AMD | Ubuntu/Pop!_OS 24.04 amd64 | DRM render node must map to an AMD GPU; encoder and session unverified |
| Intel | Ubuntu/Pop!_OS 24.04 amd64 | DRM render node must map to an Intel GPU; encoder and session unverified |
| NVIDIA | Ubuntu/Pop!_OS 24.04 amd64; Pop!_OS NVIDIA Edition preferred first test | Loaded driver, DRM modesetting, device nodes and verified NVIDIA installer SHA256 required |

The helper checks architecture, OS, selected GPU vendor and render node, virtual input devices (`/dev/uinput`, `/dev/uhid`), udev, disk/memory, Docker/Compose and Wolf port bindings. Missing or unknown *required* evidence must block installation, not be interpreted as compatibility. GPU presence by itself is not a hardware-encoder test.

**Never run the installation action on the developer's existing OptiPlex or another working Wolf server.** The ordinary **Check This PC** action is read-only and is safe to use for observing existing-host conflicts. No adoption, overwrite or implicit retry of an existing NOW workspace/project is supported.

### NVIDIA driver-volume implementation

`server/host_nvidia.py` and `server/nvidia-driver.Dockerfile` implement Wolf's upstream manual userspace-driver technique. The recipe is derived from [Games on Whales](https://github.com/games-on-whales/gow/blob/a1fbf9af2babfe2065d3af55e30ecf0bcb2dcd63/images/nvidia-driver/Dockerfile), with its MIT notice in `server/LICENSE-nvidia-driver-upstream.txt`.

- NOW checks the loaded NVIDIA driver version, DRM state, device nodes and chosen vendor-matched render device.
- The owner supplies the **exact NVIDIA installer SHA256** independently. Docker downloads that version's installer from NVIDIA and verifies its complete SHA256 *before executing it inside a build container*. This does not install or load host kernel modules.
- It creates a **new** NOW-labeled volume whose name includes driver version and checksum; Docker's volume copy-up populates the userspace files. No older/foreign driver volume is adopted or deleted.
- The generated Wolf Compose definition refers to the verified versioned volume rather than the staging placeholder, and the host driver version is rechecked before startup.

**After a host NVIDIA driver update:** the existing volume may no longer match. Automated volume recreation, migration of the running Wolf service and rollback are **not implemented**. Do not claim unattended updates or reboot reliability. The base build image and apt packages are not digest/snapshot pinned, so this process is not yet byte-for-byte reproducible despite its pinned driver version and checksum.

## Safety and implementation boundaries

- **Source of authority:** only the local, owner-confirmed, administrator-authorized installer performs Docker changes. An ordinary NOW client, its Tailscale login and a paired Moonlight device do **not** receive Docker-admin rights.
- **Host isolation:** target exactly one dedicated Compose project. Reject known Wolf port conflicts, preexisting NOW-managed data and unmanaged project conflicts. Do not call broad `docker compose down`, delete volumes or rewrite other stacks.
- **Recoverable evidence:** `/var/lib/optiplex-now/host` contains a private configuration, persistent `wolf/` state, owner record and installation phase journal. An interrupted attempt cannot be silently repeated. **Automatic repair, rollback, uninstall and upgrades are not complete.**
- **Security caveat:** Wolf's documented Docker socket/device access is privileged. Root-authorized installation does not make arbitrary workloads safe. Treat official images, installer downloads and volume content as security-sensitive and retain least-privilege enrollment boundaries.
- **Historical prototypes:** `host_stage.py`, `host_transaction.py`, `host_runtime.py`, `host_docker.py` and `host_owner.py` contain review-only configuration generations, simulated startup/cleanup and local owner-ticket experiments. **They are not the live installation controller**, and their passing tests are not proof of deployment. Do not enable or wire them into production merely to increase feature count.

## What CI proves

The GitHub workflow builds the real Debian package, installs it on disposable runners, opens the actual GTK host review under Xvfb, executes **read-only host checks**, verifies refusal cases and runs Python/native tests and sanitizers. The last checked host PR ([#134](https://github.com/SteezyMode/OptiplexNow/pull/134)) passed **200 Python tests** and both CI jobs.

**CI has not** invoked a successful `--install` on a physical AMD, Intel or NVIDIA server, proven hardware encoding, or verified a Moonlight session. Do not label a host or GPU supported because the GUI says candidate or CI passes.

## Physical host acceptance before alpha sign-off

- [ ] Install the exact test `.deb` on a clean, independently controlled Ubuntu/Pop!_OS 24.04 amd64 host; preserve a separate working reference server.
- [ ] Demonstrate GPU/render selection, driver prerequisites, explicit owner confirmation and legitimate OS elevation. Wrong, unsupported or occupied hosts must refuse safely.
- [ ] Install Wolf to the dedicated project; verify server container identity, GPU access, encoder logs and persisted configuration without damaging unrelated services.
- [ ] Connect a genuinely unpaired second client; verify *video, audio, controller input and session termination*. While the remote game runs, confirm the host's **physical desktop remains independently usable**, with no unwanted input/audio takeover.
- [ ] Restart host and client; verify recovery, preserved pairing, accurate status and reconnection.
- [ ] Interrupt install, deny authorization and test network/image failures; inspect phase journal, preserve unrelated data, and establish safe documented recovery.
- [ ] On NVIDIA, verify clean volume build, driver-version alignment and behavior after a host driver update. Do not accept automatic upgrade claims until the update/recovery path exists.
- [ ] Record exact OS, GPU/driver, Docker, Wolf digest, NOW package, network conditions and pass/fail evidence in [Current status](CURRENT-STATUS.md).

**Release rule:** a proven clean-host install and stream is the next priority. Do not add more simulated infrastructure or speculative service scope before completing this test. The separate existing-host client checklist remains in [Beta acceptance](BETA-ACCEPTANCE.md).
