# Owner phone QR approval — Private Alpha development contract

**Status (October 25, 2026): certificate-based approval implemented in draft PR #184 and offline-tested; no listener installed on the reference OptiPlex and no physical iPhone QR approval completed. Do not release or silently deploy.**

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

The final line runs **preflight only**, verifying the locally pinned owner user and phone device IDs, Wolf's read-only certificate registry, Tailscale availability and existing owner configuration. With preflight passing, explicitly run `"$HOME/.local/lib/optiplex-now-qr-pilot/$REV/run-qr-pilot" --serve` from a foreground terminal for the phone test. Ctrl+C stops the experimental listener; no system service is created. After ensuring the listener is stopped, `python3 tools/qr_host_pilot.py --remove --revision "$REV"` removes only this version's pilot files. No live host has received this deployment yet.

The **acceptance test** must use a genuinely unapproved NOW restricted key on an owner-operated client already paired to Wolf, then confirm the phone GET/POST and owner policy/forced-command SSH binding. Verify denied access from another same-owner-account computer and a wrong phone, expired/replayed requests, and uninterrupted existing Mac mini managed Steam. A previously approved device does not exercise fresh enrollment. The launcher service being installed or returning a preflight success is **not** proof of QR working.

## Evidence and remaining gates

**Verified on actual reference machines:** Native and Flatpak Mac mini private keys both matched the same certificate; its DER fingerprint was found in the Wolf registry; the independently computed Wolf ID exactly matched the actual paired Mac mini ID. Both existing local config files are now mode 0600. The actual iPhone was identified and confirmed via Tailscale WhoIs, then its StableID was registered in an owner-local mode-0600 file. Host preflight found the existing owner-ID and phone pin files, readable Wolf TOML, cryptography and Python TOML support, port 18793 unused, **and no enrollment listener yet installed.** Do not publish phone StableID or host token paths beyond their generic filenames.

**Verified only in CI:** An isolated HTTP end-to-end regression stages a key, signs proof, denies wrong sources/phones and client self-approval, allows a pinned phone to review and grant the correct client, and denies replay. Full GitHub CI/native sanitizer jobs pass on development snapshots. Those simulations are not proof of Tailscale on iOS or physical onboarding.

**Still P0:** safe isolated host module staging (no changes to the already working Games broker), exact revision/host dependency preflight, opt-in Tailscale-only listener start/stop/rollback, iPhone Safari/QR GET and POST, clean unapproved client approval + denial, real mixed LAN/Tailscale client route selection, owner Steam continuity, and disposable clean-host test. A new user's first Wolf pairing remains a distinct onboarding requirement; the signed proof only applies once Wolf has paired its certificate. Distinguish NOW owner restricted-key access from Wolf's direct published-app permissions (issue #192).

**Fail closed:** no automatic fallback to source-IP guessing when certificate mode is enabled. If the host service isn't deployed, no QR approval is claimed. No external public domain or vendor service is introduced. Never replace existing authorized_keys, Steam homes, Wolf config or known-good pairings just to force a clean test.
