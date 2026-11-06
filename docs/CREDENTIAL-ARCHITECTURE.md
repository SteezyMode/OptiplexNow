# Bruiser/NOW credentials: inventory and unified sign-in plan

State: **source-level inventory, not a completed live-secret audit**. Related issue: #247.

## Decision

Consolidate the **login experience**, not all secret material. Each approved NOW device should authenticate once, then be granted narrow, revocable access to the services it needs. VPN provider secrets, service admin passwords, daemon API keys, server encryption keys and recovery material stay **off clients**. Store per-device client tokens in the OS Secret Service (GNOME Keyring/libsecret or KWallet). Do not build a generic password-manager vault into Bruiser.

One owner-only **Accounts & Connections** view should show Connected / Needs setup / Expired / Revoke / Reconnect and guided recovery, while Games, Video, Music and Downloads work without daily logins. This is delegated service authorization, not magical universal SSO: separate providers have distinct access controls.

## Known credential categories

The following is a **catalog of kinds of credentials**, NOT proof of real accounts or their present validity on the host.

| Area | Human/recovery access | Host/service-only credential | Approved client's credential |
| --- | --- | --- | --- |
| Tailscale | Tailnet provider login | Tailnet-managed node identity | Distinct authorized device identity |
| NOW owner broker | Owner/approval | Host approval registry and policy | Independently signed, approved NOW device key |
| Wolf/Moonlight | Owner-mediated pairing | Wolf pairing/session registry | Own Moonlight pairing certificate, NOT equivalent to NOW owner approval |
| Steam | Steam login and 2FA recovery | Host Steam workspace session | Authorized game stream, no Steam password shared |
| Jellyfin | Owner/admin recovery and user accounts | Jellyfin account/session database and optional plugin tokens | Scoped per-device/user session, not administrator password |
| qBittorrent/VueTorrent | qBittorrent WebUI recovery | Host download broker/service login | NOW downloads entitlement, no portable admin password; VueTorrent is a UI to qBittorrent |
| Gluetun | VPN provider account/recovery | Provider password/token or WireGuard key (depending on configuration) | Nothing; only host uses the VPN tunnel |
| slskd | Soulseek account/recovery | slskd API key/session and Soulseek credentials | Nothing; DroppedNeedle drives acquisition server-side |
| DroppedNeedle | Human owner login/recovery | Encryption key, service state and app-password registry | Revocable music user grant after actual NOW approval |
| Caddy/TLS | DNS/ACME recovery if applicable | TLS private key and cert state | Trusted HTTPS endpoint, never private key |
| OpenSubtitles/Subbuzz | Optional subtitle provider account | Jellyfin plugin token | No provider login |
| SubHub/Sublarr | Optional operator access | Host worker API token/restricted access | No subtitle worker admin key |
| Ollama/Studio | Optional external AI provider | Host-only API keys if configured | No provider master key; local Ollama need not use one |
| GitHub/development | Developer account/recovery | CI publishing secrets and SSH keys | No developer credentials in published client |
| NOW backups | Owner backup passphrase/recovery | Encrypted backup material | Only explicitly exported, encrypted client backup |

VueTorrent does not add a second qBittorrent identity to maintain. OpenSubsonic is DroppedNeedle's **internal playback/library protocol**, not a UI login feature. Slskd and Gluetun should not be directly authenticated from every laptop. The active NOW owner boundary still has outstanding #191/#192; being on Tailscale or Wolf-paired is not enough to authorize a host-issued token.

## High-priority source finding: unencrypted music profile backup

The main-branch source file src/server-profile.py exports a portable plaintext tar.gz snapshot, including DroppedNeedle account database/config, slskd and qBittorrent state, service env files, and full Docker inspect JSON written into containers.json. Docker inspect may contain environment-variable values, host mount paths and other sensitive metadata. The script explicitly says the archive is **not encrypted**. Restrictive permissions on its temporary file are not equivalent to encryption.

This is distinct from src/backup.c, which implements authenticated encryption for NOW **client** backups. Protecting one does not protect the other.

Before the music profile exporter is considered a secure disaster-recovery feature:
- Introduce authenticated encryption and a verified owner recovery/decryption path, including recovery if the original server is destroyed.
- Minimize the manifest and **remove raw Docker inspect JSON** from the archive; retain only allowlisted restoration facts.
- Use mode 0600 staging, integrity checking, atomic output, non-destructive restore and a tested backup-to-restore rehearsal.
- Treat any previous plaintext exports as sensitive. Never paste, upload to issue trackers, or sync them casually.
- Preserve existing user media and backups. Do not silently overwrite files, rotate active keys or stop host services for this audit.

## Safe read-only inventory tool

From a cloned repository, the owner can run on the host:

    python3 tools/credential_inventory.py --host-check

For machine-readable metadata:

    python3 tools/credential_inventory.py --host-check --json

The optional host probe calls **only** the Docker running-container-name listing, classifies service-family presence and discards raw names. It never invokes Docker inspect, reads environment variables, account databases, login material, keyrings, or private files; it never writes a report file. Docker not accessible is reported as unknown, not falsely absent.

The catalog is not a credential backup and does not locate or recover passwords. The host may have other apps and accounts not identified in repo source; a complete operational inventory requires owner-reviewed runtime evidence.

## Sequence

1. **Enumerate non-secret metadata**: installed account/service type, purpose, scope, current owner, expiration/revocation policy, whether a duplicate login can be removed. Never copy actual values into ChatGPT, Git, logs or a general CSV.
2. **Close serious backup/exposure gaps** with a reversible encrypted-export migration and tested restore. Check CI, logs and generated presets for secret leakage by rule, not by dumping their contents.
3. **Finish device authorization** (#191/#192) before privileged host credential issuance. Separate games pairing from NOW service approval.
4. **Implement a narrow host secret broker**, not a generic GET /secrets API. The broker performs explicit delegated operations (issue/revoke one scoped client token) with audit entries lacking secret values.
5. **Use OS keyrings on clients** to remember their OWN per-device grants; revocation on host/provider must work even if a laptop is stolen and never comes online again.
6. **Owner Accounts & Connections view**: service health and recover/rotate links only. Physically test new devices, reboots, expired login, revoked clients, restore, permissions and host loss.

No live passwords were read, no runtime server credentials were inspected, and no credential migration or client-wide SSO has been implemented by this document.
