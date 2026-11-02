# Bruiser development account ledger — NO CREDENTIAL VALUES

Updated 2026-11-02. This is a source and project-history inventory, NOT a verified live host audit. Keep usernames, account email addresses, passwords, tokens, cookies, recovery codes and backup passphrases in a separate local encrypted password manager, NOT in this public repository or ChatGPT.

| Service | Type | Known status / next check | Private vault entry | Required on new servers? |
| --- | --- | --- | --- | --- |
| AirVPN | External paid VPN subscription | Existing VPN download service; **owner says renewal is needed**; verify subscription expiry on official AirVPN site | Bruiser Dev / AirVPN — account, expiry, subscription recovery, receipts | Only if VPN downloads enabled |
| Tailscale | External identity/device enrollment | Existing home/client Tailnet in use; recovery unknown | Bruiser Dev / Tailscale | Only for remote networking requiring it |
| Steam | External games account | Existing Steam streaming used; recovery unknown | Bruiser Dev / Steam | Only for Steam gaming |
| Soulseek | External network login for music acquisition | slskd working, provider account details unverified | Bruiser Dev / Soulseek | Only if the music provider needs one |
| Jellyfin | Host-local accounts and device sessions | Media works, owner recovery not yet verified | Bruiser Dev / Jellyfin owner recovery | **No external signup**; auto-create internally |
| DroppedNeedle | Host-local owner + per-client grants | Music service works; owner forgot login; recover once on host | Bruiser Dev / Music owner recovery | **No external signup**; auto-create internally |
| qBittorrent / VueTorrent | Host-local WebUI auth | Previously operational; VueTorrent is just a UI | Bruiser Dev / Downloader owner recovery | **No**; provision internally |
| Gluetun | Host-only VPN routing | Working VPN path reported; NO Gluetun account exists | VPN provider entry only | **No** |
| slskd | Host-only service/API key | Music acquisition working; service secrets only on host | Server-owned secret/restore plan | **No** |
| Wolf / Moonlight | Host pairing and device identity | Clients paired; NOW approvals are separate | Pairing/revoke runbook, not a shared password | **No** |
| NOW owner bridge | Per-device approval/key | Identity hardening #191/#192 pending | Owner recovery and device-revoke runbook | **No** |
| Caddy/TLS | Host-only certificate and key | Reverse proxy in use; backup must be protected | Host deployment recovery | **No** |
| OpenSubtitles/Subbuzz | Optional external provider | Connected email history contains registration/reset mail; current account not verified | Bruiser Dev / OpenSubtitles if used | Optional |
| SubHub/Sublarr | Host-local worker/API token | Optional subtitle pipeline previously used | Host-only recovery material | No |
| Ollama / Studio | Local AI runtime | Local models reportedly used; external AI optional | Only if external API provider configured | No |
| GitHub/CI | Developer-only external identity | Development repository used | Bruiser Dev / GitHub and 2FA recovery | No for customers |
| Backup/recovery | Encryption passphrase | Client encrypted backup; music server legacy backup plaintext issue open | Bruiser Dev / Backup recovery, backed up off-host | No |

## Owner recovery order

1. Create a Bruiser Development group in KeePassXC, Bitwarden, or another trusted encrypted vault and store only actual human recovery accounts. Back up the encrypted vault away from the host.
2. **AirVPN first:** identify existing VPN-provider account and renew subscription; record new expiry. Reuse existing account rather than changing a working Gluetun deployment.
3. Check Tailscale and Steam using existing browser/session/recovery screens. Check Soulseek and OpenSubtitles only if configured. Do not assume Gmail contains every login.
4. Verify local Jellyfin and DroppedNeedle owner recovery using their normal administration/recovery flows, without exposing passwords or deleting the databases.
5. Update only status markers in this public ledger. Never commit credentials or screenshots of secret values.

## Product P0

For new server owners: zero knowledge of Jellyfin, DroppedNeedle, Gluetun, qBittorrent, VueTorrent, slskd, Docker or Wolf required. Bruiser provisions internal accounts and stores host-only secrets. Genuine external signups are feature-gated, guided and optional where possible. New approved clients reconnect using revocable per-device grants in OS keyrings, not shared master passwords. Full acceptance: #98, #247, #246, #191/#192.

This ledger **does not** contain or verify the user's passwords. The local encrypted vault is the source of truth for credential values.