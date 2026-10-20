# NOW pairing authorization core (development)

**Status: implemented pairing state machine plus local-owner-only Unix control socket. NOT a working Moonlight pairing feature.** No network pairing route, owner service deployment, or client pairing is implemented.

## Purpose

Separate the owner's decision to trust a new client from Tailscale discovery and from the host-specific pairing API. **Discovering a NOW host, having an authenticated tailnet connection, or knowing a request ID never approves streaming.**

`server/now_pairing_requests.py` is a small Python standard-library component with no listeners, files, databases, subprocesses, web credentials, installer hooks, GUI dependencies, or references to Wolf/Sunshine internals. It currently **is not imported by the active host discovery agent** and cannot change any host service or give a client remote access.

## Trusted flow (future transport integration)

1. **Identity:** the host verifies the actual network connection through Tailscale WhoIs. Only trusted server-side verification code may create a `PeerIdentity` from stable, verified device and user IDs. **Never construct it from user-supplied JSON, headers, display names, or client-provided IDs.** Exact tested WhoIs fields and access policy must be established on an isolated real tailnet before networking this module.
2. **Request:** the verified device asks to pair with either `sunshine` or `wolf`. `PairingRequests.request(peer, backend)` gives it an opaque random request ID and records one outstanding request per device. It is *pending*, not approved.
3. **Owner review:** a separately authenticated and **local-owner-only** interface calls `owner_pending()` and `owner_decide(id, approve=True|False)`. There is **no owner approval route in the current HTTP host agent**; the existing experimental agent continues rejecting POST. The owner UI must show the request's device and backend and resist spoofed names. Owner approval must never be a client-driven request that merely sets an `approved` flag.
4. **Backend handoff:** after actual owner authorization, the internal trusted backend adapter checks verified peer identity and selected backend then calls `take_grant_for_adapter(peer, id, backend)` *inside the host process*. A grant can be consumed **once** only. It is an internal data object, not a reusable credential or endpoint. The adapter then performs whatever *independently authenticated and tested* Moonlight pairing operation the pinned Sunshine/Wolf version requires.
5. **Client:** status polling is limited to the same verified device. `approved` means the owner gave permission, **not** that Moonlight pairing succeeded. The client still needs native Moonlight pairing credentials and a confirmed video/audio/control session.

## Fail-closed behavior

- Denied, expired, nonexistent, malformed or other-device requests cannot authorize anything.
- A request is bound to an exact verified device **and account** and a single selected streaming backend; switching backend requires a new approved request after expiration/cancellation.
- Requests expire automatically after 180 seconds by default (maximum configurable TTL: 600 seconds). Expiry invalidates grants, even after owner approval.
- Requests use cryptographically random opaque IDs and are not saved to disk; restarting the future broker clears all approvals.
- Duplicate submissions by the same peer do not multiply pending approvals or extend expiration. An explicit denial cannot be immediately bypassed by re-requesting during the TTL.
- Bounded queue (default 16, max 64). Internal lock ensures concurrent attempts cannot consume a grant more than once.
- No support for service restarts, Docker privileges, SSH, port opening, PIN injection, certificate transfer, or cryptographic secret storage.

## Local owner approval socket (development milestone)

`server/now_pairing_owner.py` now provides a **local-only Unix-domain socket** adapter for the same in-memory `PairingRequests` instance. This is an importable host-side component, **not** a launched daemon, published web endpoint, or part of the running discovery agent.

The future trusted host broker will create a directory owned by the owner user with exact mode `0700`, construct `OwnerControl(directory, pairing_requests)`, and manage its lifecycle. The socket is `owner.sock`, restricted to mode `0600`. Requests are authenticated against **Linux `SO_PEERCRED`**, not a client-provided owner name or header. Only processes running as the socket server's actual Unix UID can request pending reviews or submit an approval/denial. A missing, shared, foreign-owned, or symlinked directory is rejected; an existing socket/file is never overwritten. The server removes only its own socket after shutdown.

The protocol is deliberately tiny and bounded: **`list`**, **`approve`**, and **`deny`**. Only `list` discloses pending device/account identifiers and backend. The local owner control does **not** expose `request`, `take_grant_for_adapter`, service operations, PIN exchange, or anything to Tailscale clients. The request queue is still populated exclusively by future trusted, verified in-process calls; currently no active host service populates it, so this is infrastructure for future integration.

The module contains an optional CLI interface for future local operators, not an installer or permanently enabled service:

```sh
python3 server/now_pairing_owner.py --socket-dir /path/to/pre-created-private-dir list
python3 server/now_pairing_owner.py --socket-dir /path/to/pre-created-private-dir approve REQUEST_ID
python3 server/now_pairing_owner.py --socket-dir /path/to/pre-created-private-dir deny REQUEST_ID
```

These commands cannot do anything unless a separate, explicitly started trusted process is already hosting the Unix socket. They do not install packages or make network requests. **Do not create or launch the owner service on the primary production OptiPlex yet.**

**Limitations:** Linux UID identity establishes a boundary against **other Unix users**, not malicious programs already running as the owner. We have not implemented an independent owner UI login, Polkit flow, verified Tailscale request source, native Moonlight pairing, or audit/persistence. This local socket is not the credential/authorization scheme for remote NOW clients. Production adoption needs real-device tests and an explicit owner-session threat model.

### Isolation tests

`tests/test_now_pairing_owner.py` uses real Unix socket connections within disposable `0700` temporary directories, while keeping all tailnet/streaming components mocked or absent. It checks owner listing, approve/deny, one-time internal grants, peer UID denial, protocol operation allowlist, socket and directory permissions, stale-path refusal, malformed/oversized commands, concurrent owner decisions, and CLI fail-closed behavior.

## Non-negotiable integration boundaries

- Keep **discovery** on the existing read-only NOW Host Agent and do not add a public/unauthenticated pairing approval endpoint.
- Design a separate authenticated *local owner* control surface before exposing any remote pairing-request API.
- Authenticate each request's current Tailscale node identity and account; do not treat a node-derived display marker or HTTP request ID as proof.
- Never put native Moonlight host passwords, PINs, private keys, streaming certificates or Tailscale keys into a website, sync registry, URL or logs.
- Verify actual Sunshine and Wolf pairing APIs and their device-isolation behavior on pinned versions before implementing the backend adapter; mock tests alone are not certification.
- Keep the production OptiPlex and its current Wolf sessions, Tailscale, Caddy, and Studio untouched until an isolated hardware acceptance plan is approved.

## Testing

Run the existing test suite (which discovers `test_now_pairing_requests.py` automatically):

```sh
python3 -m unittest discover -s tests -v
```

Tests cover rejection by default, exact peer/account/backend binding, owner approval and denial, wrong-client status isolation, duplicate requests, TTL expiry, bounded queue, simultaneous consumption, restart behavior, malformed input and ID collision.

**Next incremental milestone:** integrate the verified WhoIs identity adapter with the request-only side of a separate pairing broker, then implement owner approval through an authenticated local UI/socket. Only after that, add host-specific Moonlight pairing adapters and test against real clients. Do not conflate owner consent with successful native pairing.
