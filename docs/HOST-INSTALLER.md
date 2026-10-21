# Future NOW Host installer

**Status:** design contract only. No turnkey host setup is shipped. The developer's OptiPlex is a reference machine, not an installation template. Track delivery in [#98](https://github.com/SteezyMode/OptiplexNow/issues/98).

## First implemented host preflight (source-only)

`server/host_preflight.py` provides a read-only, unprivileged host inventory.
This is **not** a server installation action and is not included in the v1.17.0 client .deb. From a checked-out repository on the intended host:

```sh
python3 server/host_preflight.py
python3 server/host_preflight.py --json
```

It reads local OS/architecture, PCI graphics vendors and render nodes, controller devices, the NVIDIA kernel version and DRM mode setting where relevant, memory, disk availability and local socket tables. It also invokes `docker info --format '{{.ServerVersion}}'` with a three-second timeout when the Docker CLI is present. This is a read-only daemon query; it does not launch containers, inspect private volume data, modify memberships or elevate privileges. No Docker access means an attention state, not permission expansion.

The reported Wolf TCP/UDP ports are based on upstream's documented defaults: 47984/tcp, 47989/tcp, 48010/tcp, 47999/udp, 48100/udp and 48200/udp. A detected socket bind is a **potential conflict**, not evidence that the bound service is incompatible or unauthorized. An empty socket table does not establish remote reachability, firewall rules or future availability. The scanner never opens sockets or probes the network.

The first host pilot is a **candidate Ubuntu 24.04 amd64 configuration**, not an already-validated support promise. Other distributions stay unknown until tested. Missing controller nodes, old NVIDIA driver and known port binds require attention. Encoder support, actual GPU container access, Wolf readiness and successful video/audio/controller streaming are **always unknown** until separate real host testing.

The JSON contract is versioned (`schema_version=1`) and contains only bounded operational findings, no user file contents, SSH keys, host names, network addresses, auth tokens or full container lists. Each check uses `pass`, `attention`, `unsupported`, or `unknown`; `overall` is `unsupported`, `requires_attention`, or `unknown`. This stage deliberately never reports `compatible` or `verified_streaming=true`. A subsequent plan/apply component must not treat a clean preflight as authorization to install or alter services.

Native Python tests construct disposable filesystem fixtures, exercise parsing and failures, assert no fixture modification, and run the JSON CLI. Tests run in normal CI; physical GPU and encoder acceptance is still outstanding. Wolf's installation requirements should be checked again when dependency versions are pinned.

## First installation plan preview (source-only)

The next step after preflight is `server/host_plan.py`. It consumes the
versioned, redacted `host_preflight.py` results and generates a deterministic
**non-executable** installation plan. It does not configure the host or generate
a runnable Compose file. Both tools remain **development source only**, not
features included in the v1.17.0 client .deb.

From the checked-out repository on a Linux host:

```sh
python3 server/host_plan.py
python3 server/host_plan.py --json
python3 server/host_preflight.py --json > scan.json
python3 server/host_plan.py --preflight-json scan.json --json
```

A saved scan is a diagnostic record. Avoid sharing it without reviewing its
contents. The planner reads a maximum 64 KiB report and accepts only the
expected scanner schema and enumerated check states; it does not propagate
arbitrary diagnostic text into its output.

The preview describes the **candidate** Ubuntu 24.04 x86-64/NVIDIA,
single-owner Wolf streaming layout, proposed managed config and state roots,
Docker project labels, required components, network ports, and lifecycle
sequence. Jellyfin is optional. Every prospective mutating operation is
marked *not implemented*. The plan always returns `may_apply=false` and
`decision=blocked`, even if every scanner check passes.

Why it always blocks: no Wolf image digest has been pinned and verified, real
encoder and streaming tests are incomplete, the least-privilege enrollment
broker is unimplemented, and rollback has not been validated on an independent
clean host. No implicit Docker group/sudo permission, network configuration,
port reassignment or host authorization is ever requested by these tools.

**Existing host behavior:** occupied Wolf ports are a known potential conflict.
On a reference host with Wolf already installed, the correct output is a
blocked plan demanding explicit owner review, not another Wolf instance, a
container restart, silent adoption, or a software downgrade. The scanner
does not know which process owns the port; ownership cannot be inferred
from port occupation. Pop!_OS 24.04 remains an unqualified distro until
tested. The optional host-import route remains separate future work.

Tests assert stable contract parsing, hostile/duplicate/missing checks,
unknown encoder state, occupied-port behavior, preservation of unmanaged data,
and no mutation of a disposable input file. These run in Python CI along
with the earlier preflight suite.

## Compose deployment prototype (source only, never auto-run)

`server/host_stage.py` is the first concrete Docker Compose staging
artifact. It builds on the read-only preflight and blocked installation
plan, generating a **review-only** Wolf NVIDIA Container Toolkit configuration
and an ownership manifest. It does **not** install or run Wolf. No `apply`,
`start`, `repair` or `uninstall` command exists.

This first pilot assumes NVIDIA, an explicitly chosen render device, a
preverified immutable Wolf registry SHA256 image digest, Docker/Compose and
one manually reviewable Wolf service. After checking upstream's current
[Wolf quickstart](https://games-on-whales.github.io/wolf/stable/user/quickstart.html),
the prototype now selects the **manual NVIDIA driver-volume method** rather
than the less-stable Container Toolkit method. It declares an external,
dedicated `now-nvidia-driver-vol` volume and the required NVIDIA devices.
It **does not populate the volume**: driver-volume construction needs a
trusted/pinned Dockerfile and separate verification that the volume matches
the current host driver. Rebuilding after NVIDIA driver updates is an
explicit unresolved host-upgrade requirement, never an automatic volume wipe.
Wolf also requires administrative host Docker-socket access to spawn
application containers, so deploying it remains a security and hardware
acceptance gate, not something clients may authorize themselves.

Example with an actual verified digest and explicitly selected render node:

```sh
python3 server/host_stage.py \
  --output /tmp/now-wolf-review \
  --image-digest sha256:REPLACE_WITH_VERIFIED_64_LOWERCASE_HEX_DIGITS \
  --render-node /dev/dri/renderD129
```

The example digest is a placeholder, not a valid image. Reviewers must verify
the digest against the correct Wolf image/architecture and inspect their
actual render device first. The script performs only bounded read-only
host inspection and **writes files into a new, explicitly selected staging
directory**. It refuses overwrites, symlink destinations and system folders.
The new directory contains `compose.yaml`, `manifest.json`,
`README.txt` and an initially empty `wolf/` configuration directory.

The Compose definition is JSON-formatted YAML and follows Wolf's upstream
NVIDIA manual driver-volume topology: host networking, external driver volume,
NVIDIA/DRM/input devices and udev mounts, an explicit render node and a
Docker socket mount. To reduce accidental
deployment, its service is hidden behind an inactive Compose profile,
`pull_policy=never`, `restart=no` and a unique Compose project; these
settings are not a security boundary for a person who deliberately enables
the profile. No separate container named `wolf` is created during staging,
and no existing daemon resource is adopted or restarted.

Run `docker compose -f compose.yaml config --quiet` **only for syntax
validation**. It does not prove that the Wolf image is valid, the GPU encoder
works, a stream starts, or that server authorization is secure. Automated
tests inspect the generated model, protect existing files, enforce
strict inputs and (where Docker Compose is present) validate the actual
Compose grammar without talking to the daemon.

Reference: [Wolf upstream quickstart](https://games-on-whales.github.io/wolf/stable/user/quickstart.html)
and [Docker Compose GPU support](https://docs.docker.com/compose/how-tos/gpu-support/).

## Prototype configuration transactions (no container activation)

`server/host_transaction.py` manages **configuration generations only** in a
private workspace that must be a direct child of `/tmp`. It is intentionally
unable to write to `/etc` or `/var/lib`, install system dependencies, invoke
Docker, or start/stop Wolf. An operational host installer still needs a
separately reviewed, privileged backend and hardware validation.

Given a staged review bundle, `--prepare` creates owner-marked generations,
a `current.json` pointer, and a separate persistent `wolf/` directory.
A second prepare of the same bundle is idempotent. A new generation becomes
active through atomic pointer replacement. `--rollback` returns to the
previous **configuration** generation without deleting saved Wolf data or
Docker volumes. It does not roll back a running Wolf container.

```sh
python3 server/host_transaction.py --prepare /tmp/now-wolf-review --workspace /tmp/now-host-fixture
python3 server/host_transaction.py --rollback --workspace /tmp/now-host-fixture
```

The inputs must match the known staging template, including manual NVIDIA
volume strategy. Invalid or altered bundles and foreign directories fail
closed. Lock files prevent simultaneous modifications, and the journal remains
available for manual investigation if an early write is interrupted. This is
not a security boundary against a local administrator with access to the
workspace.

This is **real filesystem transaction code**, not a fully functioning Wolf
installer. Existing server ports remain occupied, no second Wolf instance
is allowed to start, and no actual NVIDIA volume provisioning, Docker Compose
activation, host authorization or live streaming verification is implemented.
Tests run entirely in disposable fixtures, including failures and rollback.

## Initial supported scope

Start with one explicitly supported Linux distribution and a verified hardware/driver matrix. Stream one Wolf application to one Moonlight device; optionally install Jellyfin with independent credentials. Add multi-desktop and multi-user features only after security and persistence gates pass.

VPN, qBittorrent, slskd, music, Caddy and Studio are optional. They must not be installed automatically for basic gaming or video service access.

## Installation contract

1. **Preflight:** OS/architecture, network interfaces, GPU codec/encoder, driver stack, available storage, ports, Docker/runtime presence, filesystem permissions, existing services and conflict report. Never claim compatibility from a device name alone.
2. **Plan:** show exact packages, images, paths, networks, ports, accounts, secrets and service interruptions before changes. Preserve unrelated resources.
3. **Ownership:** use a dedicated managed namespace/root directory for manifests, configuration, state, backups and logs. Track service IDs and installed versions in a versioned manifest with ownership metadata, not incidental container names.
4. **Deployment:** pin upstream images and install only selected services. Use explicit service dependency ordering and documented networks. No unreviewed privileged mounts or public admin endpoints.
5. **Identity:** register host ownership, local restricted management agent and permitted actions. Pair Moonlight devices through host-local Wolf APIs, never direct remote access to Wolf/Docker sockets. Future device approval should require owner confirmation without repeated manual SSH.
6. **Verification:** test that the service starts, a supported game/desktop stream launches with input and audio, optional media login works, and client status/health reports match observed state.
7. **Lifecycle:** offer safe plan/apply/retry/repair/update/rollback/uninstall. Preserve personal media, games, profiles, pairings and backups by default. Clearly separate removing software from deleting user data.

## Proposed organization

Paths and identifiers below are **candidate conventions**, not installed artifacts:

| Category | Candidate |
| --- | --- |
| Managed system configuration | `/etc/optiplex-now/host/` |
| Persistent app-managed data | `/var/lib/optiplex-now/host/` |
| Operator logs and diagnostics | systemd journal plus `/var/log/optiplex-now/` only when needed |
| Agent executable | `/usr/libexec/optiplex-now/` or distribution-standard libexec path |
| Versioned service manifest | `/var/lib/optiplex-now/host/manifest.json` |
| Managed Docker/Compose objects | `optiplex-now.*` labels and explicit service IDs; never rely on fixed display names |

Verify Debian conventions, permissions and backup semantics before adopting these paths. Secrets must be root/agent accessible only, absent from diagnostics and Git. User library paths must remain configurable and outside auto-deletion.

## Host health contract

A future host agent should return explicit versioned states for:

- Reachability and trusted identity.
- Wolf daemon health, API compatibility, available apps and active sessions.
- GPU codec/encoder availability and resource pressure.
- Optional media readiness and login endpoint.
- Optional VPN gateway health, with separate tunnel/external-route verification if actually implemented.
- Managed image versions, failed upgrades, migrations and pending repairs.

**Running**, **healthy**, **connected**, **paired**, and **currently streaming** must remain different values. Missing healthchecks do not imply a healthy tunnel.

## Existing host import

A host with existing `music-vpn` Gluetun, Wolf, Jellyfin or qBittorrent cannot be assumed to follow managed naming or directory conventions. Provide a read-only inventory, explicit ownership selection and non-destructive adoption path. Otherwise use the existing setup without taking control of it. Do not rewrite container networks or volumes merely to standardize display names.

## Acceptance before release

- Disposable fresh-host install and clean removal, then repeat to prove idempotence.
- Failed/partial install, rollback and retry without damaged data.
- Upgrade across two supported pinned versions without lost settings or credentials.
- Non-interference with separately installed and running unrelated services.
- Least-privilege review of the pairing/management agent.
- Fresh client can reach, pair with and use a working stream without the operator editing Compose or shell scripts.
- Diagnostics expose no SSH key, Moonlight certificate private key, VPN password, Wolf pair secret or token.

See [Wolf integration](UPSTREAM-FIRST-WOLF-INTEGRATION.md) for API and fork decisions; see [Multi-user feasibility](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md) for later user isolation.
