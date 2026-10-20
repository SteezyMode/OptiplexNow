# Experimental NOW Host discovery over Tailscale

**Status:** Unreleased, opt-in proof of concept. **No account system, first-run install, streaming-control channel, Moonlight pairing integration, or production deployment is implemented.** Does not start a background daemon.

## User goal and scope

From a supported Linux NOW client, a person already signed into Tailscale should be able to **Find NOW server** and select the host without remembering an IP address. Existing manual host configuration remains fully available for compatibility. This stage deliberately stops at discovering an existing host; it does not make an unpaired client playable.

The implementation is independent of any website or product/company branding. Tailscale is the remote-access identity/connectivity layer, not a substitute for Moonlight's native per-device pairing.

## Host side — opt-in, explicit foreground test only

The package ships `/usr/bin/optiplex-now-host-agent`, a Python standard-library executable. Packaging merely copies files and **never starts or enables** a service. Running it without `--serve` checks the local Tailscale state and prints readiness, but does not open a listening socket.

On a **disposable development host only**, with Tailscale connected:

```sh
optiplex-now-host-agent --backend wolf
optiplex-now-host-agent --serve --backend wolf --name "NOW Server"
```

Choose `--backend sunshine` or `unknown` if appropriate. The backend parameter is an advisory label and does **not** inspect, start or control Wolf/Sunshine.

An explicitly started agent binds **only** to the running machine's Tailscale IPv4 address within `100.64.0.0/10`, never to LAN, `0.0.0.0`, localhost, or a website. Its single discovery endpoint is HTTP `GET /v1/discover` on **port 18791**. HTTP payloads are transported over Tailscale's encrypted peer connection; this endpoint has no standalone TLS and must never be forwarded through Caddy/WAN or made publicly routable. Before returning its bounded non-secret response, the agent asks local Tailscale `whois --json` to verify the source node and that the incoming peer address belongs to it. If WhoIs is unavailable or returns unrecognized fields it **rejects** the request. It does not perform privileged operations.

The JSON contains only a fixed protocol identifier, a deterministic *display* marker from Tailscale node identity (not a signed key), a user-supplied sanitized name, an advisory streaming backend and an explicit `pairing: not_implemented` state. No IP/peer lists, login names, passwords, access tokens, Steam details, host paths, Docker metadata, or Moonlight certificate material are returned. The marker allows the client to compare with locally observed Tailscale peer metadata; it is **not** an independent cryptographic guarantee outside that authenticated transport.

**Security limitations:** The read-only probe is accessible to any tailnet device whose connection is permitted by Tailscale policy and whose WhoIs result passes the address check. Device-specific NOW authorization, rate limits, signed persistent host keys, TLS, grants/ACL tests, secure owner-managed pairing, log/audit policy and production hardening still require design and testing. It intentionally has **no** host management, SSH, Docker socket access, Wolf management API or pairing endpoint. This is not ready to run permanently or expose to untrusted users.

## Client side — existing NOW Setup Wizard

With an opt-in test host agent already running, open NOW's **Setup Wizard → Server → FIND NOW SERVER (EXPERIMENTAL)**.

The client runs the packaged `find-now-hosts.py` helper asynchronously (no UI blocking). It reads its own Tailscale status and checks **at most 24 online tailnet IPv4 peers** using a fixed port and bounded per-peer timeouts. It does not use HTTP proxies, scan arbitrary/LAN/public ranges, sign in or enroll devices, and does not touch the server's configuration. Each discovered host must return the expected protocol format **and** an identifier matching the corresponding tailnet node identity. Unknown and offline peers are ignored.

The dialog shows a server name and backend, allows rescanning, and offers **USE THIS SERVER**, which fills the existing server-address field. The existing SSH/Moonlight/Wolf pairing steps must still be completed separately. The app never silently authorizes a remote user, copies pairing keys or changes user settings until they deliberately select the host.

The client-side scanner is also available from source:

```sh
python3 src/find-now-hosts.py --json
```

It emits a sanitized array of confirmed NOW nodes. Existing legacy `find-servers.py` and manual host entry are retained unchanged.

## Contract and identity verification (development)

The host's `tailscale whois --json <peer-ip>` response contains a `Node.Addresses` collection of **assigned node addresses**; `Node.AllowedIPs` can also include subnet routing. The experimental host now requires the **exact /32 IPv4 assignment** matching the source. It never substitutes a broad AllowedIPs route as proof of a unique client identity. This fail-closed interpretation may require adapting to actual daemon-version fields during isolated two-device testing; it should not be weakened into broad route acceptance.

CI now includes an **actual localhost HTTP exchange** between the agent's real request handler and the discovery scanner's real protocol parser, with injected synthetic Tailscale WhoIs responses and a temporary loopback-only test listener. It checks discovery success, denied identity, mismatched host identity, and rejection of control/POST requests. A simulated tailnet transport proves the JSON and HTTP components work together; **it does not prove Tailscale's real routing, its grant rules, OS firewalls, WhoIs response compatibility, or practical Moonlight connectivity**.

### Live two-device acceptance checklist (not performed)

On disposable computers only, after explicitly enrolling them in a separate test tailnet and authorizing the necessary TCP 18791 connectivity:

1. On host, run `optiplex-now-host-agent --backend sunshine` in check-only mode; confirm no port is opened or service enabled.
2. Start the agent in foreground only with `optiplex-now-host-agent --serve --backend sunshine`; verify it binds to **only the intended Tailscale IP and TCP 18791**.
3. On the second device, use **Setup Wizard → Server → FIND NOW SERVER (EXPERIMENTAL)**; confirm that the returned label and host identity match the test host, and that selecting it fills only the host field.
4. Check the same steps with a second online but unrelated Tailscale peer and a denied grant; they must not be presented as NOW hosts.
5. Interrupt/reconnect Tailscale, restart the host agent, and revoke peer access; verify the host disappears and appears again as appropriate, without changing other server settings.
6. Verify an ordinary Moonlight/Sunshine pairing and reconnect separately. Host discovery is not permission to initiate streaming.
7. Stop the foreground agent and verify the listener disappears; confirm no automatic service was enabled and no persistent server data changed.

**Block release** if any of the real Tailscale WhoIs fields, node IDs, identity-match rules, or client access checks differ from the synthetic fixtures. Do not experiment by exposing the production Wolf, SSH, Docker socket or Caddy services.

## Validation and rollout gates

Mock/unit tests cover IPv4 binding restrictions, no implicit service startup, WhoIs allow/deny, read-only HTTP endpoints, peer filtering, response-marker mismatch and malicious JSON, plus isolated GTK opening/closing. Debian installed-package acceptance checks the two CLI entry points without starting host services. CI **does not** verify actual cross-device streaming or Tailscale interoperability.

Before any user-facing or release claim, test this on a **disposable, supported pair of Linux machines** with a real Tailscale tailnet. Validate differing Tailscale daemon versions, shared-node invitations, WhoIs shape, port grants, disabled daemon, peer key rotation, denied policies, normal and malicious network access, re-scans, and custom server labels. The primary OptiPlex, Wolf desktops, MoonlightWeb, Caddy and Studio must remain untouched.

Next milestone: introduce a separately reviewed, least-privilege NOW server manager with owner-approved device authorization and Moonlight pairing integration, and a signed device/server identity independent of Tailscale node re-enrollment. No version or API may be assumed supported until tested against pinned actual Wolf/Sunshine/Moonlight builds.

References: [Tailscale CLI (whois)](https://tailscale.com/kb/1080/cli), [Tailscale identity](https://tailscale.com/docs/concepts/tailscale-identity), [tailnet policy](https://tailscale.com/kb/1337/policy-syntax), [proposed onboarding architecture](UPSTREAM-FIRST-WOLF-INTEGRATION.md).
