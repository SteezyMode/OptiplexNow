# NOW owner-first onboarding — no server screen after provisioning

**Status: security-focused development branch only.** [Draft #62](https://github.com/SteezyMode/OptiplexNow/pull/62), [Client install plan #48](https://github.com/SteezyMode/OptiplexNow/issues/48), [pairing defect #59](https://github.com/SteezyMode/OptiplexNow/issues/59).

## Product requirement

**An owner can set up their first laptop from the laptop.** No returning to the server, no Docker terminal, no SSH session, no localhost admin page, no certificate bypass. The server remains running in the background and authorizes a device only after checking its identity.

NOW is a single product with **Client** and eventual **Server** installer roles. The host software must be installed/provisioned *once* before a bare machine can accept pairing requests. That initial privileged installation can be initiated in a guided, authenticated remote installer if the owner has existing management authorization; it cannot be performed on a completely unconfigured machine without any pre-existing way to access it. **After NOW Server is provisioned, ordinary client enrollment never needs local host interaction.**

### Owner's first client

1. NOW Server is installed as a service via approved server setup; its owner account is registered from an explicitly chosen **local Tailscale server identity**, or from an installer-managed mode-0600 pinned owner ID file. Tagged/sharee/server-without-owner nodes fail closed.
2. Owner installs NOW Client on another Linux desktop and signs into the *same authorized tailnet account*.
3. Owner selects that server in the existing NOW GUI, then chooses **Request Gaming Access to Server**.
4. NOW Server binds the pending request to the actual Tailscale WhoIs device/account identity.
5. Owner opens **Pending Device Approvals (Remote Owner)** in NOW on **that laptop or a different signed-in owner device**. The broker verifies each request against the pinned owner account. No SSH, screen, email delivery dependency or personal server password.
6. Approve. The server records a non-replayable authorization. The selected Wolf/native Moonlight or MoonlightWeb adapter still needs to implement the *actual upstream pairing* and verify streaming success; approval alone is not pairing.

### Additional family or guest client

Same device request, but its Tailscale user is **not the owner**, so only an owner device can view/approve it. Client-provided headers, email address, device claims, request ID, or membership in the tailnet never grant owner status.

### Email approval notifications — next separately gated work

The desired UX is an email to the **verified, installer-registered server owner**: *A device wants to connect to your NOW server. Open NOW to approve or deny.* The email should link to an owner inbox view rather than carrying bearer credentials or making the PIN itself the authorization. The owner can approve on their own phone once a securely authenticated phone owner view is implemented.

An email feature needs an opt-in outbound mail provider, owner email verification/recovery, throttling, expiring requests, and replay prevention. It **must not** use a guessed client-supplied recipient, plaintext PINs, broad MoonlightWeb admin access, OAuth token copying, email link that grants authority before identity check, or an unprotected public endpoint. Email failure does not block already authenticated owners from approving directly inside NOW.

## Code implemented in this draft

- `server/now_pairing_owner_identity.py`: fail-closed, private local owner file and explicit server-side owner derivation using local `tailscale status --json`. No client can register themselves as owner.
- `server/now_pairing_broker.py`: opt-in owner endpoints bound to tailnet address; WhoIs exact user ID, literal Host header, custom non-secret desktop header, no cross-site Origin, bounded requests. GET only pending list; POST only approve/deny a specific short-lived request.
- `src/now-owner-approvals.py`: client-only direct tailnet IP request / list / approve / deny; timeouts, bounded response validation, no external HTTP proxy/browser/SSH/TLS exemption.
- Existing GTK **Settings** gets **Request Gaming Access to Server** and **Pending Device Approvals (Remote Owner)** buttons with explicit pending/approved/error feedback.
- Debian packaging includes the helper plus disabled-by-default pairing broker modules; **does not install or enable a daemon or connect to Docker/Wolf**.

## Security and current acceptance limits

- Only explicit server-role activation passes `--owner-from-local-tailnet` or `--owner-id-file`. Without either, remote approvals are disabled. Tailscale ACLs must still restrict access to the host; identity is independently checked per request.
- No routine client is required to SSH or stand at the server. Admin permissions to install NOW Server **initially** are still necessary somewhere and must be handled by the eventual installer UI.
- No additional public web address is created; `games.monumentrisk.com`, Caddy, Wolf and MoonlightWeb are unchanged.
- "Owner approved" always means **permission granted** and never automatically means Wolf paired or MoonlightWeb access PIN issued.
- Email sending, phone/browser owner interface, backend-specific pairing adapter, service installation/upgrade/rollback, owner recovery and real clean-client streaming tests **are not complete**.
- Never release this as a turnkey server/client installation until those gates and security review are satisfied.
