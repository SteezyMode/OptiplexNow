# NOW Host installer

**State: experimental, unaccepted installation candidate.** The [published v1.18.0 closed-beta](https://github.com/SteezyMode/OptiplexNow/releases/tag/v1.18.0) includes an opt-in guarded advanced Wolf host installer, but it has not passed clean physical host installation, encoder or gameplay acceptance. On current source, an opt-in, privileged installation path exists for *clean* Ubuntu 24.04 and Pop!_OS 24.04 amd64 hosts with AMD, Intel or NVIDIA graphics. A complete installation and working game stream have **not** been validated on independent physical hardware. Track completion in [#98](https://github.com/SteezyMode/OptiplexNow/issues/98).

This document describes the **Wolf-only host installer**. The active release gate is [Private Alpha 1](PRIVATE-ALPHA.md), covering one owner and owner-operated devices, independent Games, Jellyfin and VPN-isolated Downloads. The broader public-alpha/member contract is deferred. [Product direction](PRODUCT.md), [current verification](CURRENT-STATUS.md) and [private client beta](BETA-ACCEPTANCE.md) cover separate stages.

## Implemented path

The separate GTK window `src/host_setup.c` opens from **Settings > Connections & Server > Check This PC for Server Setup**.

1. **Review:** unprivileged read-only `host_preflight.py` and `host_plan.py` display detected prerequisites, conflicts and unknown capabilities. They make no system changes.
2. **Advanced pilot:** choose AMD, Intel or NVIDIA, provide the correct `/dev/dri/renderD###` and a *verified* immutable Wolf OCI `sha256:` digest. NVIDIA additionally requires a SHA256 for the official NVIDIA `.run` installer matching the **loaded** kernel driver version.
3. **Check:** `host_install.py --check` inspects real hardware, runtime prerequisites, occupied Wolf ports, driver/DRM state and existing managed paths. Non-root users need not join the Docker group; inaccessible daemon state requires a privileged recheck.
4. **Authorize:** explicit GTK confirmation and OS `pkexec` authentication precede `host_install.py --install`. The root helper rechecks eligibility and refuses existing NOW-managed workspace/project state. There is no network-facing installation API.
5. **Provision:** before starting Wolf, the helper installs the pinned upstream `85-wolf.rules` only if absent (or preserves an identical trusted file), refuses conflicting Wolf-specific rules, and reloads udev without globally triggering devices. Then the helper uses only its dedicated `optiplex-now-host-pilot` Compose project, a pinned Wolf image and private `/var/lib/optiplex-now/host` state. It writes owner and phase records before starting Wolf and verifies its full container ID, image reference, Compose labels and running status.
6. **Report:** `running_stream_unverified` means only that the inspected container is running. It does **not** mean Moonlight pairing, encoding, video, audio, input or reconnection succeeded.

Docker and Docker Compose must already be installed. This pilot does **not** configure the user's package repositories, kernel drivers, boot settings, firewall, Tailscale account, Jellyfin or unrelated services. It is not yet the promised 15-minute, terminal-free consumer host installation.

## October 26 clean-host Games audit and first increment

The live path is `src/host_setup.c` → `host_install.py`; preflight, service census and adoption planning are reusable read-only components. `host_stage.py` supplies the Compose template. Transaction/runtime/owner-ticket prototypes remain disconnected. The published v1.20.0 installer is an advanced container-start path, not a completed consumer setup.

| First-game requirement | Current evidence / missing work |
| --- | --- |
| OS/GPU/dependency/conflict detection | Implemented and mock tested; Ubuntu/Pop!_OS 24.04 amd64 candidates only; render device and GPU selected manually. |
| Prerequisite provisioning | Docker/Compose, kernel modules/device nodes, drivers and remote networking must already work. No integrated dependency installation. |
| Reproducible Wolf installation | Dedicated project, immutable user-supplied digest, root recheck, persistent state and NVIDIA userspace-volume recipe exist. No curated tested image selection; NVIDIA checksum remains manual. |
| Physical desktop independence | Input nodes alone do not establish isolation. This development increment provisions pinned upstream input rules; real controller/desktop separation remains untested. |
| Owner Steam and authorized client | Clean installer does not bootstrap the existing restricted broker, durable named owner workspace, enrollment service or complete graphical pairing/discovery. Direct Wolf app authority differs from NOW managed-operation authority (#192). |
| First game and recovery | Container identity/running checks exist; no integrated encoder, video/audio/controller or session test. Interrupted installs stop; automated repair/removal and NVIDIA driver-update recovery remain unfinished. |

**First increment (development branch, not released):** provision upstream Wolf input rules before any Wolf startup. Exact upstream source: [85-wolf.rules at 9f29d9c](https://github.com/games-on-whales/wolf/blob/9f29d9c4ceb5b0fb83875d98dad67af8237f5495/85-wolf.rules), SHA256 `52567af7cce1feb6a6625938b804e0def2c1fee6f70db69f36c366f7cdf8151c`. The package carries the unmodified file and MIT notice as inert resources; installing/upgrading the Debian package alone does not activate rules. Local confirmation explicitly discloses this host change.

The installer checks the standard `/etc`, `/run` and `/usr/lib` udev rules directories for Wolf-specific conflicts. It preserves identical trusted `/etc/udev/rules.d/85-wolf.rules`, rejects different content, named masks/symlinks and unsafe directory/file ownership or write modes. It never rewrites other rules, changes group membership or globally triggers devices. This conservative review is **not** an evaluation of all effective udev/logind policy; custom rules and host users already in `input` can still affect isolation. Physical verification is mandatory.

Reload failure leaves the exact rule and a `preparing_input_rules` journal, and stops before image pulls/startup. No silent retry or automatic deletion follows. For recovery on the disposable test host, inspect the journal and exact rule bytes; remove only a rule known to have been created by this attempt after stopping its managed sessions, then reload udev. Never remove a preexisting matching file or unrelated policy. An older client package does not undo host-side setup.

**Verification:** disposable-filesystem and mocked-command tests cover conflict refusal, unchanged existing policy, exclusive creation, integrity failure, reload/timeout retention and no Docker calls after reload failure. Full package/native checks belong to PR CI. No physical host installation or input-isolation result is claimed.

**Next concrete increment:** guided prerequisite preparation for the same narrow clean-host matrix (Docker/Compose and required input modules), retaining administrator approval and existing-service refusal. Then complete owner workspace/enrollment wiring and run the separate GPU-host acceptance journey; do not install this candidate on the working OptiPlex.

**Upstream audit correction:** the old `stable` Git branch has historical explicit runtime/state mount requirements. Current Wolf source performs container mount introspection and its image supplies runtime storage; missing explicit legacy environment variables are not sufficient evidence of a defect in NOW's generated Compose. No speculative mount rewrite is included.

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
