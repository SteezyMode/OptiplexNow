# Owner QR approval — experimental, source-bound development pilot

**Not physically accepted end-to-end.** The live Mac mini Games workflow succeeded only AFTER the user manually corrected a wrong Wolf identity authorization. PR #184 protects future owner enrollment; it is not deployed on the running reference host.

During staging, the host saves the actual IPv4 source observed by sshd (SSH_CONNECTION) or the verified Tailnet HTTP request. A client cannot submit its own source address. Legacy source-less requests cannot be approved. Requests expire after 600 seconds; staging the same public key from a different source is denied.

The host-local approval UI no longer exposes a list of arbitrary Wolf IDs. A client is eligible only when the host sees ONE paired active Wolf UI stream whose client_ip exactly matches the staged request source. A QR phone review targets one pending request and applies the same test. The final approval independently RECHECKS the same network source and Wolf client ID before committing both restricted authorized_keys and the owner policy. Multiple sessions, unrelated Wolf apps or lobbies, missing provenance, mismatching IDs and other-source streams fail closed. No automatic permission fallback, Steam stop, unpair or Wolf restart.

**P0 remaining:** This prevents the actual accidental numeric-ID mismatch but DOES NOT cryptographically bind the staged SSH private key to a Moonlight certificate or automatically connect a Tailscale node's 100.x address to the same machine's 192.168.x streaming address. Those mixed-network requests correctly FAIL rather than guess. Implement and validate certificate possession or equivalent independently authenticated source association before claiming QR onboarding is safe across LAN/Tailnet and completely effortless. No unverified owner device should ever receive a Games/Downloads key.

The phone page requires explicit verified Tailscale owner identity, exact Host/Origin constraints, six-digit code comparison and Approve action; scanning alone grants nothing. The QR is generated locally with qrencode, the code is in a URL fragment, and the owner listener is separately opt-in over the host Tailnet IPv4 at TCP 18793. Installing a client .deb does NOT run this host service, create accounts or modify keys.

**Remaining acceptance:** green CI negatives; clean client QR and direct source match on real hardware; wrong source/identity/owner/replay; mixed LAN/Tailnet certificate-level proof; clean-host recovery/rollback. Keep the repaired Mac mini authorization intact.

## October 25 — Moonlight certificate proof prototype (source-only)

The next secure cross-network binding uses an existing owner-device identity, NOT a public website or new NOW account. Upstream Wolf retains the Moonlight client public certificate in its private host config.toml; Moonlight Qt stores the corresponding private key in the client's own QSettings. Wolf derives its numeric client ID from the certificate. Relevant upstream docs: https://games-on-whales.github.io/wolf/stable/user/configuration.html and https://github.com/moonlight-stream/moonlight-qt/blob/master/app/backend/identitymanager.cpp .

**Implemented in draft PR #184 as an offline-tested, unconnected prototype:**
- server/moonlight_cert_identity.py constructs a bounded, domain-separated request challenge over the one-time request ID, six-digit code and the exact staged restricted SSH public-key fingerprint; verifies an RSA/SHA-256 detached signature using the submitted PUBLIC certificate; checks that it is in the host-owned Wolf paired-client TOML registry and that Wolf's API still considers the intended ID paired.
- src/moonlight-identity-proof.py reads one specified Moonlight Qt QSettings identity locally (read-only) and signs the challenge using the corresponding private key. The client sends only a public certificate and signature, NEVER the private key. Ambiguous or unreadable Qt profiles fail closed.
- tests/test_moonlight_cert_identity.py exercises real generated X.509/RSA keypairs, challenge tampering, wrong/removed registry certificate, unpaired ID, invalid key material, and untrusted registry permissions. No real Wolf, SSH or network state is modified.

**Still NOT done:** A verified host inventory path to the actual running Wolf TOML file; a server-bound staging/attestation endpoint with strict same-request/source access; client identity profile discovery (Moonlight Qt AppImage and non-Qt clients differ); persisting/rechecking the verified Wolf ID in the atomic owner grant; packaging dependency review; real cross-network tests. Until each is implemented and physically verified, the existing source-address guard MUST stay fail-closed, and no QR approval may claim Moonlight certificate verification. Custom app_state_folder mappings also fail closed under the prototype. No certificate proof secret should ever be written to a log or a QR code.

