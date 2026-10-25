# Owner phone QR approval — signed Moonlight identity pilot

**Status: opt-in PR #184 development code, not installed or physically accepted on the working OptiPlex.**

## Does this need a website?

No. NOW generates the QR locally. The code opens a private HTTP page on the owner's OptiPlex Tailscale IPv4 address at TCP 18793. Tailscale encrypts the transport. The owner phone must be connected to the same Tailnet; its ordinary camera and browser are sufficient. No product domain, cloud account, Internet-accessible service, or third-party QR generator is required.

## Which device may approve?

Host Tailscale WhoIs verifies both the pre-pinned owner's numeric Tailscale user ID and the independently pre-pinned trusted phone StableID. A computer signed into that same owner account can stage its own request but cannot approve itself. Owner-phone identity must be registered securely on the host first; a fresh-host graphical phone-pinning UI remains unimplemented. Remote approval refuses to start without --approver-node-id-file when explicitly enabled.

## Which computer is being approved?

1. The NOW client stages its own restricted Ed25519 public key. Host creates a short-lived request ID and a six-digit code; no permissions are granted.
2. Client locates exactly one pre-existing Moonlight Qt QSettings identity. Ambiguous native/Flatpak/AppImage profiles cause refusal, never a guess. The client signs a challenge containing the exact request ID, code and staged key fingerprint with its local Moonlight RSA private key; it sends only the public certificate and detached signature.
3. Host independently verifies the signature and that same certificate in the read-only, trusted Wolf paired-client TOML and Wolf paired API. Real Wolf client ID is derived by Wolf's 64-bit libstdc++ hash of stored certificate bytes; custom app_state_folder never determines identity. Unsupported Wolf build/hash or inaccessible registry fails closed.
4. The host stores one short-lived signed proof linked to the source that staged the Ed25519 key. NOW displays the QR only after proof acknowledgement.
5. The verified owner phone loads the QR page; host checks the pre-pinned phone StableID. Owner compares six-digit code and key fingerprint then explicitly taps Approve. Host rechecks the certificate proof under the owner policy lock before atomically granting restricted Games/Downloads access. No numeric Wolf ID selector.
6. Wrong phone, missing proof, changed certificate, ID mismatch, expired request, altered code, wrong staging node or unpaired Wolf certificate cause a denial. No unrelated Wolf/Steam containers, paired clients or owner keys are changed.

Certificate verification permits NOW staging over Tailscale while Moonlight uses LAN; no LAN-to-Tailnet identity guessing. The old exact-source fallback remains separately scoped for legacy owner testing; enabling certificate mode requires proof and cannot downgrade to the fallback. Installing NOW client .deb does not start the host listener.

## Host setup and physical acceptance

Dev listener flags: --serve --enable-remote-approval --owner-id-file PRIVATE_OWNER_ID --approver-node-id-file PRIVATE_PHONE_STABLE_ID --wolf-config TRUSTED_WOLF_CONFIG_TOML. The pinned ID files must be owner-owned mode 0600. Wolf config is host-owned and read-only. Client package now explicitly depends on python3-cryptography.

Outstanding blockers: verify true reference-host Wolf TOML and client Moonlight Qt file/profile; actual phone identity pinning, QR and wrong-phone tests; installer/host service integration, reboot/reconnect, clean LAN/Tailscale acceptance. These gates prevent calling the feature released or fully verified.
