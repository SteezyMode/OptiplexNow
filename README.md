# Bruiser (currently packaged as OptiPlex NOW)

*Bruiser is the chosen working product name. Repository, Debian package and binary retain the legacy OptiPlex NOW names until a coordinated, compatibility-safe rebrand. Not affiliated with Dell.*

**Play games, watch Jellyfin, manage VPN-isolated downloads, and play music from your own Linux server.** One desktop client; the server and its content remain yours.

## Download Bruiser — Active Private Alpha

**[Download current owner-tested Private Alpha (.deb)](https://github.com/SteezyMode/OptiplexNow/releases/latest/download/OptiPlex-Now_amd64.deb)**

For 64-bit Linux Mint, Ubuntu and Pop!_OS. Download the file, double-click it, and install with your normal package installer. No compiling or GitHub Actions required.

[Release details and checksum](https://github.com/SteezyMode/OptiplexNow/releases/latest)

**Status: ACTIVE, owner-validated private alpha.** The owner reports working daily household use on the reference OptiPlex, Linux Mint MacBook and Pop!_OS Mac mini. **v1.21.16 is the frozen functional baseline.** The formal Private Alpha 1 exit criteria are still open: supported fresh host/client installation, security/failure testing and independent reproducibility have not been accepted. This download currently targets owner-approved devices accessing an **already configured** Linux server, not new consumers or a general-purpose host installer.

## What it does

- **Games:** Launch the owner's Steam streaming session through Wolf and Moonlight, while the server remains usable.
- **Videos:** Open the server's existing Jellyfin media library.
- **Downloads:** Search API Bay and Bitsearch concurrently (All or a category), browse progressive deduplicated magnet results, choose an approved media folder, and manage transfers. Only qBittorrent traffic goes through the dedicated Gluetun VPN; the existing host needs both reviewed engines enabled.
- **Music (optional):** Browse, shuffle, play, like and playlist-manage an already configured DroppedNeedle library. Approved devices use per-client Music access; installing the .deb does not provision a new Music server.
- **Status:** Check connection and VPN health. Advanced VueTorrent remains available under Downloads.

## Connect to an existing server

1. Install the .deb and sign in to Tailscale on an owner-approved device.
2. Open NOW and use **Settings → Setup Wizard** to find the host.
3. Complete host approval and Moonlight pairing as required.
4. Open **Games**, **Videos**, **Downloads**, or the optional **Music** tab.

**Important:** Wolf pairing and NOW owner permission are separate. Do not pair an untrusted person to a Wolf catalog exposing your Steam account. The new native Transfers controls require matching, owner-authorized modules on the host; the client installer does **not** update your server, VPN or containers. Fresh-client authorization and the newest Downloads controls still require real-device acceptance testing. This is an alpha, not a guarantee of a fully automatic setup.

## Project status

**Current phase: make the working v1.21.16 household software shippable.** Freeze new feature expansion and Downloads UI redesign; prioritize graphical zero-prerequisite host setup, internal account/credential provisioning, fresh device approvals, security/recovery checks, and disposable clean-host tests. Extract risky monolithic UI/service code **incrementally where it blocks reliable changes**, with regression tests—no rewrite. Optional Music works on the owner's configured server; SubHub/subtitle localization is independent and not an alpha exit gate.

- [Product roadmap](docs/PRODUCT.md) — scope and delivery order
- [Current status](docs/CURRENT-STATUS.md) — implemented versus physically verified
- [Private Alpha acceptance criteria](docs/PRIVATE-ALPHA.md) — what still must pass
- [Development instructions](AGENTS.md) — contributor and coding-agent rules

Older installers remain in [GitHub Releases](https://github.com/SteezyMode/OptiplexNow/releases) for rollback. They are not alternate products or recommended downloads.

The current client is **Linux x86-64 only**. Windows support and new-host installation are future work.
