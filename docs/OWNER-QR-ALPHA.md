# Owner phone QR approval — Private Alpha development contract

**Status (October 26, 2026): pilot listener deployed manually on the real OptiPlex and Tailscale-connected iPhone GET/candidate review physically verified. Two phone approval attempts used a duplicate already-authorized restricted key and were safely denied. No new-key approval or wrong-phone physical denial completed. v1.20.0 ships this as an explicitly opt-in closed-beta pilot, NOT accepted alpha.**

## Design — no public website

NOW creates a QR locally with `qrencode`. The QR opens the OptiPlex's private Tailscale IPv4 URL on port 18793 in the phone's normal browser. The six-digit code is in the URL fragment, not sent in an HTTP GET. The encrypted transport is Tailscale, not a public website. The phone needs connected Tailscale; no NOW phone app, Moonlight, external QR provider, or Monument Risk domain is needed.

Host verifies each connection via Tailscale WhoIs. The requesting computer is permitted to stage its own restricted public key, but **only an independently pinned owner-phone StableID under the pinned owner Tailscale user ID** can open the approval page, request its certificate-verified candidate, and POST the final approval. A newly connected computer sharing the owner account cannot self-approve. The owner-phone node ID is host-private data and must never be committed to GitHub.

## Identity and approval

1. NOW stages a restricted Ed25519 **public** key, receiving a short-lived request ID, six-digit code and fingerprint. No permission is granted.
2. NOW locates its existing Moonlight Qt identity. One valid profile is accepted; multiple native/Flatpak profiles representing **the same verified certificate and matching private keys** are treated as one device. Different or invalid profiles fail closed. Mode-0644 private-key files are safely tightened to owner-only mode 0600 by the local user; symlinks, group/world-writable or foreign-owned files fail closed. Certificate and pairing bytes do not change.
3. NOW signs the request ID, code and restricted-key fingerprint using the local Moonlight RSA private key. It sends only the public certificate and detached signature to the owner host. The host checks that certificate in the real read-only Wolf registry, independently derives its Wolf client ID from the exact stored certificate bytes and confirms the ID remains paired. A configurable Wolf storage folder name is never treated as identity.
4. The host records one request-and-source-bound proof; ONLY after success does the client offer the QR. The normal QR mode does not offer a misleading client-side self-approval button.
5. The already pinned owner iPhone opens the page via Tailscale, compares the code/fingerprint, and taps Approve. The host validates its phone StableID, revalidates the signed proof under the owner policy lock, then atomically adds a *restricted forced-command* Games/Downloads key and updates the matching Wolf grant. Any mismatch fails closed.
6. Approval consumes the request and is not replayable. It does not expose generic host SSH, unpair another client, restart Wolf or modify Steam.

## Reversible reference-host deployment gate

The source-only opt-in helper `tools/qr_host_pilot.py` stages a fixed allowlist of QR enrollment modules separately from the working NOW Games broker. It **does not** install a service, bind a port, touch authorized_keys or Wolf, start Docker, or enable remote approval automatically. Use a reviewed, exact 40-hex Git commit checkout or its corresponding GitHub tarball; **never use an obsolete revision from a prior chat command**.

As the existing unprivileged host owner, from the source checkout/archive:

```sh
REV="$(git rev-parse HEAD)"  # or exact SHA used to download a GitHub commit tarball
python3 tools/qr_host_pilot.py --check --revision "$REV"
python3 tools/qr_host_pilot.py --install --revision "$REV"
"$HOME/.local/lib/optiplex-now-qr-pilot/$REV/run-qr-pilot"
```

The final line runs **preflight only**, verifying the locally pinned owner user and phone device IDs, Wolf's read-only certificate registry, Tailscale availability and existing owner configuration. With preflight passing, explicitly run `"$HOME/.local/lib/optiplex-now-qr-pilot/$REV/run-qr-pilot" --serve` from a foreground terminal for the phone test. Ctrl+C stops the experimental listener; no system service is created. After ensuring the listener is stopped, `python3 tools/qr_host_pilot.py --remove --revision "$REV"` removes only this version's pilot files. The reference OptiPlex received this isolated deployment on October 26; the foreground service may remain running. Check it before launching another instance, then Ctrl+C to stop. No user data or Steam/Wolf service was changed by installation.

The **acceptance test** must use a genuinely unapproved NOW restricted key on an owner-operated client already paired to Wolf, then confirm the phone GET/POST and owner policy/forced-command SSH binding. Verify denied access from another same-owner-account computer and a wrong phone, expired/replayed requests, and uninterrupted existing Mac mini managed Steam. A previously approved device does not exercise fresh enrollment. The launcher service being installed or returning a preflight success is **not** proof of QR working.

## Evidence and remaining gates

**Verified on actual reference machines:** Native and Flatpak Mac mini private keys matched its Wolf-paired certificate; both local configuration files were secured to mode 0600. The actual iPhone's Tailscale identity was independently verified and its StableID stored in an owner-local mode-0600 file; never publish these private values. On October 26 the OptiPlex successfully installed the isolated QR pilot and started the listener on Tailnet port 18793. The phone reached its private page, and Wolf certificate-candidate verification succeeded for a previously paired device. The phone's approval attempt was denied for an **already-authorized** restricted SSH key. A genuine new-key grant is still unverified on hardware.

**Verified only in CI:** An isolated HTTP end-to-end regression stages a key, signs proof, denies wrong sources/phones and client self-approval, allows a pinned phone to review and grant the correct client, and denies replay. Full GitHub CI/native sanitizer jobs pass on development snapshots. Those simulations are not proof of Tailscale on iOS or physical onboarding.

**Still P0:** fresh restricted device credential must complete successful iPhone confirmation POST and restricted SSH grant, with deliberately rejected wrong-phone, replay and expiry cases. The real existing-key duplicate was correctly denied twice, so these cannot count as approval success. Also pending: mixed LAN/Tailscale client routes, fresh Wolf pairing, Games single-writer/owner continuity and disposable clean-host test. Physical host staging and iPhone GET proof review have passed. A new user's first Wolf pairing remains a distinct onboarding requirement; the signed proof only applies once Wolf has paired its certificate. Distinguish NOW owner restricted-key access from Wolf's direct published-app permissions (issue #192).

**Fail closed:** no automatic fallback to source-IP guessing when certificate mode is enabled. If the host service isn't deployed, no QR approval is claimed. No external public domain or vendor service is introduced. Never replace existing authorized_keys, Steam homes, Wolf config or known-good pairings just to force a clean test.
