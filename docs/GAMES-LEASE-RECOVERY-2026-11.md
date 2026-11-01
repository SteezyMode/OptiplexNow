# Games: abandoned owner Steam session recovery

## Failure mode (reference OptiPlex, 2026-11-02)

An interrupted Wolf Create/Join can legitimately leave a durable owner Steam
lease in `creating`, `created`, or `uncertain`. This is intentional:
a timed-out Create may have succeeded, so retrying or blindly stopping the
lobby risks duplicate launches or interfering with an active session.

Reference-host symptom: Games said access was unverified or Steam in use, yet
restricted owner `status` returned `success: true, status: in_use,
same_device: true`. Native `reconcile` returned `denied`, because the
existing code only archived `joined` leases. The owner inspected the host:
lease v2/uncertain, Wolf lobbies = 0, sessions = 0, and Steam writers absent.
The operator-only checked archival recovered successfully without resetting
SSH authorization, Moonlight pairing, Wolf configuration, or Steam data.

## Recovery design

**Never disable durable blockers or automatically retry uncertain Create.**
Instead, the existing restricted `reconcile` command may archive a lease
only under the same verified, unrevoked owner device and matching workspace,
with host Games control enabled:

- `joined`: preserve existing eligibility for zero Wolf lobbies, zero
  Steam writers, and at most this exact owner's Wolf UI session.
- `creating`, `created`, `uncertain`: require **zero Wolf lobbies and
  zero sessions**, **no Steam writers**, then query Wolf again before
  archiving. If any query fails, any activity exists, identity or workspace
  differs, a grant is revoked, or the result changes, keep the lease.
- Old v1 leases still need separate local operator review. No blind recovery.
- Always atomically archive the original complete private lease under the
  owner-only state lock. Do not delete it, expose the PIN, restart Wolf, or
  send a Stop/Create POST.
- The owner app's next explicit Games launch already performs exactly one
  `reconcile` if status is `in_use`. After this change, it recovers an
  idle abandoned transaction and proceeds to the normal Wolf UI/Moonlight
  connection flow without a terminal.
- Games Settings also provides **Recover Idle Games Session**: a visible,
  asynchronous, one-click request using the enrolled restricted owner key.
  It never requests ordinary administrator SSH. If recovery cannot be
  proven safe, it displays refusal and retains the session.

**Not a complete concurrency lock:** independent privileged Wolf UI users
could race between reads. The existing restriction on external Wolf Steam
admission remains required; the host rechecks runtime before archival.

## Deployment and acceptance

The new recovery logic requires the updated **host broker package** and
the UI button requires the updated **client package**. Merely restarting
Wolf or changing the client package does not update an older host broker.
Use `owner-host-upgrade.py --check` to inspect existing packaged broker;
on an `up_to_date` host, do not rerun migration. Updating the official
`.deb` on the host updates the already adopted broker's code.

Offline tests cover authorized abandoned-state recovery and original
evidence archival, refusal with live lobbies/sessions/writers, changes
between runtime checks, foreign/revoked/unapproved devices, and unchanged
confirmed-joined recovery. Native UI wiring is tested. A live
interrupted-Create reproduction should use disposable state, never the
working reference game session.

## When recovery refuses

Do not clear the lease manually or repeatedly restart Wolf. Read-only checks
should inspect the lease's version and state (never print its PIN), Wolf
lobby/session counts, and the host Steam writer census. If the state is
ambiguous or Wolf remains active, require supervised operator review.
