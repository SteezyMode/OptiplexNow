# Streaming integration and fork policy

**Status:** future design, not a release promise. Scope and sequencing are controlled by [Product direction](PRODUCT.md) and [Beta acceptance](BETA-ACCEPTANCE.md).

## Default decision

**Use upstream Wolf, Moonlight, Jellyfin and networking tools. Build NOW's installer, client UX, restricted host broker, status aggregation and service lifecycle around tested interfaces.** Own the integration, not a duplicate streaming engine.

A Wolf fork is an exception. Forking transfers responsibility for security fixes, codecs, driver compatibility, device pairing and upstream regression testing onto NOW. It does not automatically solve host installation or account registration.

## Actual Wolf evidence

The reference host has a running `wolf` container with a local Unix socket at `/run/user/wolf/wolf.sock` inside that container. On 2026-10-21, its local API exposed:

- `GET /api/v1/openapi-schema`
- `GET /api/v1/pair/pending`
- `POST /api/v1/pair/client`
- `GET /api/v1/sessions`
- `POST /api/v1/sessions/stop`

The exact running image digest, API compatibility across stable/beta tags, permission boundaries and full session semantics still need a reproducible test matrix. Earlier stable-vs-beta source comparisons do not override an observed API on the deployed host. The privileged socket must not be published to remote clients.

Wolf desktops, user profiles, paired device certificates and stream sessions are different concepts. Per-user access is not proven merely by a GUI list or separate home directories.

## Candidate changes and fork evaluation

| Gap | First approach | Possible fork justification |
| --- | --- | --- |
| Device-specific profile authorization | Inspect tested native Wolf access path, supported config/API and upstream feature requests | Mandatory server-enforced authorization remains unavailable upstream |
| Existing-account, second-device reconnect | Map NOW account, device and logical desktop in a host broker; measure actual pairing semantics | Critical stream/home identity model requires minimal server modification |
| Reliable session lifecycle | Pin Wolf/API version, use supported management API, request missing endpoints upstream | Supported versions cannot deliver necessary lifecycle behavior |
| Low-end game client UX | Expose existing Moonlight codec, bitrate, scaling and controller settings | Necessary feature cannot be achieved through supported launch/options/extensions |
| Host install, recovery or branding | NOW manifests, adapter and UI | Normally **not** a reason to fork Wolf |

Do not fork Headscale/Tailscale just to own sign-in; evaluate supported interfaces and existing enrollment mechanisms. Do not fork Moonlight or Jellyfin without a separate measured, critical gap.

## Required decision record before a fork

1. User-visible blocked behavior reproduced against an exact upstream release/image digest.
2. Upstream issue/PR status; API/config workaround attempted; why an adapter fails.
3. Smallest patch and a maintainer responsible for upstream rebases.
4. Security/certificate implications, test coverage, client and host compatibility.
5. Licenses and all dependency/redistribution notices, trademark restrictions and distribution plan.
6. Build, upgrade and playback checks against at least two upstream versions.
7. Ongoing maintenance and support cost compared with the value delivered.
8. Rollback plan and exit path back to upstream.

Preferred order: upstream configuration -> NOW adapter -> upstream PR -> isolated patch set -> full fork. Branding alone is insufficient.

## Privilege and authorization rules

A future NOW host agent should be local, least-privileged, versioned and limited to allowed operations. Never expose Wolf's management socket or Docker socket on a public listener. A NOW GUI hiding an application does not authorize a user if a paired Moonlight client can request it directly. Test native permission enforcement and second-device reconnect before claiming secure multi-user desktops.

## Roadmap sequence

1. Complete private client Beta 1 on a fresh unpaired device.
2. Pin a disposable Wolf integration test fixture and map actual capabilities.
3. Deliver a reproducible minimal host installer on a supported Linux machine.
4. Prove device approval, durable desktop ownership and revoked-device behavior.
5. Only then consider an upstream change or fork backed by test evidence.

See [Host installer](HOST-INSTALLER.md), [Multi-user feasibility](MULTI-USER-DESKTOPS-FEASIBILITY-2026-10-19.md), [#85](https://github.com/SteezyMode/OptiplexNow/issues/85), [#94](https://github.com/SteezyMode/OptiplexNow/issues/94), and [#98](https://github.com/SteezyMode/OptiplexNow/issues/98).
