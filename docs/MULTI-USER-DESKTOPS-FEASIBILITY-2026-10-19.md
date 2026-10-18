# NOW 2.x — Multi-User Virtual Desktops: engineering feasibility review

**Status:** Roadmap candidate; feasibility review only. **No implementation or release-scope change approved.**  
**Reviewed:** 2026-10-19  
**Companion:** [Turnkey NOW / Wolf strategy](UPSTREAM-FIRST-WOLF-INTEGRATION.md), [existing named workspace issue #14](https://github.com/SteezyMode/OptiplexNow/issues/14), [Studio local-first architecture](https://github.com/SteezyMode/OptiplexStudio/blob/main/docs/ADR-001-LOCAL-FIRST-SHARED-STUDIO-RUNTIME.md).

## Decision recommendation

**Proceed to an isolated technical spike, not a two-user production MVP.** One-click, private persistent desktops for multiple household users is a coherent potential product differentiator. Its feasibility is credible because Wolf already streams multiple apps/virtual desktops, but **secure multi-user identity and authorized connection from any of a user's devices is not provided by container creation alone**. Avoid marketing it as 'private multi-user cloud workstations' until those security gates are met.

The two original notes correctly defer clones/quotas/cloud VM features and preserve the working host. This review narrows the validation sequence and identifies a major upstream **stable vs. beta** discrepancy.

## Findings grounded in Wolf source (as inspected 2026-10-19)

| Feature | Wolf evidence | Gap NOW owns or must verify |
| --- | --- | --- |
| Separate simultaneous desktop streams | [Stable config](https://github.com/games-on-whales/wolf/blob/stable/docs/modules/user/pages/configuration.adoc) documents simultaneous sessions with app-specific containers; [Wolf README](https://github.com/games-on-whales/wolf). | Admission control, capacity visibility, per-user session policy, graceful GPU/encoder exhaustion and performance testing. |
| Persistent homes | Stable config uses `HOST_APPS_STATE_FOLDER/<app_state_folder>/<app_title>`; paired clients typically have distinct `app_state_folder` values. [Stable docs](https://github.com/games-on-whales/wolf/blob/stable/docs/modules/user/pages/configuration.adoc). New [beta docs](https://github.com/games-on-whales/wolf/blob/beta/docs/modules/user/pages/configuration.adoc) show `profile_id/app_title` defaults, but [beta session code](https://github.com/games-on-whales/wolf/blob/beta/src/moonlight-server/state/sessions.hpp) still keys actual session state using the paired client's `app_state_folder`. | Separate human user identity from paired **device** identity, then define one stable owner-to-home mapping that survives second-device pairing, disconnect, container recreation and host reboot. Preserve Linux ownership and safe delete/restore. |
| Wolf profiles and app lists | **Beta** has named `profiles`, profile PINs, and Wolf UI profile selection ([beta docs](https://github.com/games-on-whales/wolf/blob/beta/docs/modules/user/pages/wolf-ui.adoc)). | Profile PIN is not a demonstrated full authentication, permission or security-isolation system. Do not equate it to secure user accounts. Verify whether a paired Moonlight client can invoke or list another user's apps regardless of frontend. |
| Programmatic Wolf control | [Beta Unix-socket management API](https://github.com/games-on-whales/wolf/blob/beta/docs/modules/dev/pages/api.adoc) has profiles/apps, pairing, clients, streams and session controls ([API source](https://github.com/games-on-whales/wolf/blob/beta/src/moonlight-server/api/unix_socket_server.cpp)). **Stable branch inspected** has no corresponding `src/moonlight-server/api/unix_socket_server.cpp` or beta Wolf UI documentation; its config instead has a single `apps` list. | Pin an actual Wolf **image digest and API version** on a disposable server. The product may need a compatible upgraded Wolf version, constrained config-manipulation adapter, or upstream extension. No blind beta upgrade on production. |
| Secure control boundary | Wolf [API documentation](https://github.com/games-on-whales/wolf/blob/beta/docs/modules/dev/pages/api.adoc) explicitly warns the API can pair clients and execute arbitrary commands; beta example Wolf UI mounts the management socket and sets multiple Linux capabilities. | NOW must never expose unrestricted Wolf API, Docker socket, host SSH, arbitrary mounts or shell commands to ordinary users. Build a local least-privilege **broker** with authenticated/authorized allowlisted operations and audit trail. |
| Templates and provisioning | Wolf can configure Docker applications; custom images and persistent mounted homes are standard Docker concepts. | NOW owns template versions, transactional create/rollback, ownership metadata, file permissions, image lifecycle, updates and failure diagnostics. A template is more than a display label. |
| Performance and concurrency | Multiple sessions are an explicit Wolf design goal; specific consumer hardware throughput is unproven. | Test CPU, RAM, GPU VRAM, encoder/codec session capacity, network throughput, game rendering and simultaneous stream latency under measured workloads. |
| Multi-device reconnection | Wolf pairs Moonlight **clients** by certificate and streams to those clients. | Confirm 'same user / same desktop' with a second independently paired device, including session collision policy and whether a disconnected session stays alive. |

The current home workstation includes an i7-9700, 32 GiB and RTX 3050 6 GB. **Two lightweight 720p/30 desktop streams may be plausible**, but simultaneous modern games, multiple heavy Studio sessions or guaranteed two-GPU-session performance are **not** assumed. No unverified FPS or NVENC stream limit is being claimed; measure on the actual card/driver/image combination. Keep the production machine untouched for this investigation.

## Critical architectural distinction: account / desktop / device / session

NOW's canonical data model should represent four distinct IDs:

- `user_id`: NOW principal/owner, enabled/disabled, credential/auth method and role (admin or ordinary user).
- `desktop_id`: immutable logical workspace + template version + designated persistent storage + owner/ACL; its **display name is not the ID**.
- `device_id`: individually paired Moonlight client certificate identity, authorized by an account; can be revoked without deleting files.
- `session_id`: transient live streaming/container process, reconnect and concurrency policy. Never assume identical to a desktop or device.

**Core authorization invariant:** before a Moonlight device can stream a desktop or join an existing session, NOW/Wolf must enforce that the pairing belongs to an authorized user and that the user owns (or was explicitly granted access to) the desktop. NOW-authenticated administrative UI alone is **insufficient** if a directly paired Moonlight client can bypass it via Wolf's own app list and RTSP control path. This is the chief feasibility/security blocker to prove or refute before building a GUI.

**Security options to investigate, not approved decisions:**
1. Supported per-device/profile authorization enforcement inside the tested Wolf version.
2. A small upstream Wolf enhancement for server-enforced device-to-profile policy, with integration tests and collaboration upstream.
3. Separate Wolf instances/security boundaries per user if necessary, understanding networking/pairing/ports/GPU complexity. Do not assert this fallback is cheap or always feasible.

Container boundary needs separate hardening review: some example Wolf app runners use shared host IPC, elevated capabilities, GPU/device mounts and the common Linux UID/GID `1000:1000`. Separate `/home/retro` paths alone do not guarantee protection against arbitrary malicious code, shared host mounts or privilege escalation. Define the threat model as **trusted household users** vs. **mutually untrusted tenants**; the latter is a materially different product and not part of the proposed MVP.

Credentials: use a reviewed modern password-hash/auth stack if NOW actually issues passwords; optional external identities later. Do not conflate Moonlight device certificate pairing, Wolf UI profile PIN, Linux account login, Steam account login or NOW password. Revoke devices and credentials; leave homes intact.

## Scoping correction

The proposed 'MVP' currently includes **a clean host installer plus two-user account service plus secure pairing/authorization plus desktop provisioning plus recovery plus concurrency**. That is closer to a first major product release than a smallest viable experiment.

Separate its milestones:

**Stage 0 — source/version proof (read-only):** Inventory pinned Wolf stable image/API/schema and data mapping, beta comparison and upgrade/revert path. Threat model and hardware budget. No production changes.

**Stage 1 — isolated provisioning proof:** On a spare host/VM where streaming is supported, provision a second **Standard Desktop**, unique name, independent controlled home, launch and remove (preserve data), with lifecycle checks. Human-controlled read-only discovery preferred; test transactions with safe rollback. No commercial claims or secure account promises.

**Stage 2 — multi-user security gate:** Two human accounts; two separately paired devices; user-specific desktop access **enforced on the native Moonlight path**, not merely hidden in NOW GUI. Attempt unauthorized profile/app listing, direct stream start, session hijack, path traversal, cross-home file access, unauthorized stop/delete and stolen/revoked device reconnection. If any cross-user access succeeds, **stop: this is not multi-user MVP-ready**.

**Stage 3 — persistence and concurrency gate:** Same user logs in through device B and reaches the **same logical desktop data**, irrespective of device certificate; test disconnect, stop, reboot, container recreate, data restore, concurrent two 720p/30 lightweight streams, admission-control rejection, encoder failure and safe cleanup.

**Stage 4 — simple NOW GUI and template installer:** After gates 1–3 pass, implement Create Desktop / Owner / Template / Start / Stop / Connect / Remove in NOW. Support only Standard Desktop initially; Gaming Desktop after Steam licensing/account/proton/host capacity policy is documented. Provide an actual supported-host setup and recovery wizard with redacted logs and upgrade compatibility checks. Avoid duplicating Wolf UI or building a virtualization dashboard.

**Stage 5 — outside-household validation:** Two real users, separate devices, fresh supported machine; record onboarding time, admin intervention, stream/session stability, account isolation results, maintenance burden and willingness to pay before broad commercial planning.

## Suggested objective acceptance (not acceptance of current code)

1. Safe disposable Wolf install, pinned image and rollback demonstrably work.
2. One administrative UI creates two distinct logical desktops without an operator opening a shell, with separate persistently mounted homes.
3. Two users and two Moonlight client certificates have **enforced** user-to-desktop and user-to-session authorizations; unauthorized direct Wolf/Moonlight access is rejected.
4. Each user can reconnect from a second authorized device and recover the **same** files and application settings.
5. Stop/start, disconnect, host reboot, container recreate and tested data-only restore do not lose source files/settings or replace the other's running desktop.
6. Both lightweight users can stream simultaneously for a fixed measured test window on stated hardware; publish CPU/GPU/VRAM/encoder/network findings and graceful capacity warnings.
7. Remove confirmation preserves or exports data by default; destructive deletion requires a separate unmistakable action.
8. User-visible provisioning errors and rollback do not corrupt unrelated Wolf profiles/services, NOW or Studio.

**Prototype success is not production-ready security or user experience.** Distinguish each stage's evidence, tests, known operating system, driver, image digest and endpoint limitations.

## Explicit non-goals / guardrails

No Windows VMs, GPU partitioning, cloud fleet, enterprise SSO, account billing, whole-host workstation migration, resource quotas, file-sharing between untrusted tenants, gaming account pooling, secret token in git, Wolf fork on day one, or breaking NOW's existing gaming/media/Studio paths. A fork is considered only if a specific validated Wolf authorization or lifecycle gap cannot be addressed through current stable interfaces or an acceptable upstream change.

**Current action:** Document this review and link to the existing named-desktop discovery issue #14; add one separate **NOW 2.x feasibility issue**. Do **not** change live Wolf config, launch extra desktops, create user accounts, add exposed API ports or merge a release.
