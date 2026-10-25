# Owner QR approval — experimental, source-bound development pilot

**Not physically accepted end-to-end.** The live Mac mini Games workflow succeeded only AFTER the user manually corrected a wrong Wolf identity authorization. PR #184 protects future owner enrollment; it is not deployed on the running reference host.

During staging, the host saves the actual IPv4 source observed by sshd (SSH_CONNECTION) or the verified Tailnet HTTP request. A client cannot submit its own source address. Legacy source-less requests cannot be approved. Requests expire after 600 seconds; staging the same public key from a different source is denied.

The host-local approval UI no longer exposes a list of arbitrary Wolf IDs. A client is eligible only when the host sees ONE paired active Wolf UI stream whose client_ip exactly matches the staged request source. A QR phone review targets one pending request and applies the same test. The final approval independently RECHECKS the same network source and Wolf client ID before committing both restricted authorized_keys and the owner policy. Multiple sessions, unrelated Wolf apps or lobbies, missing provenance, mismatching IDs and other-source streams fail closed. No automatic permission fallback, Steam stop, unpair or Wolf restart.

**P0 remaining:** This prevents the actual accidental numeric-ID mismatch but DOES NOT cryptographically bind the staged SSH private key to a Moonlight certificate or automatically connect a Tailscale node's 100.x address to the same machine's 192.168.x streaming address. Those mixed-network requests correctly FAIL rather than guess. Implement and validate certificate possession or equivalent independently authenticated source association before claiming QR onboarding is safe across LAN/Tailnet and completely effortless. No unverified owner device should ever receive a Games/Downloads key.

The phone page requires explicit verified Tailscale owner identity, exact Host/Origin constraints, six-digit code comparison and Approve action; scanning alone grants nothing. The QR is generated locally with qrencode, the code is in a URL fragment, and the owner listener is separately opt-in over the host Tailnet IPv4 at TCP 18793. Installing a client .deb does NOT run this host service, create accounts or modify keys.

**Remaining acceptance:** green CI negatives; clean client QR and direct source match on real hardware; wrong source/identity/owner/replay; mixed LAN/Tailnet certificate-level proof; clean-host recovery/rollback. Keep the repaired Mac mini authorization intact.
