# Operations handoff — 2026-10-16

This is an operator handoff, not a deployment claim. Use alongside [server-setup.md](server-setup.md) and [next-session.md](next-session.md). This project is a **personal** Linux client for an existing home server.

## Repository and release state

- Repository: `SteezyMode/OptiplexNow`.
- `main`: released 1.11.9; does **not** contain the new Web Gaming/Admin UI.
- `feature/wolf-driver-maintenance`: draft 1.12.0 work, PR #1. The Web Gaming Admin action now calls an SSH-loopback helper; not yet validated on the live client.
- Existing server configuration and image tags can drift independently of the repository. An inventory is not a declaration of configuration compliance.
- Never publish authentication tokens, Moonlight certificates/private keys, SSH keys, VPN credentials, Compose environment files, or full client backups.

## Reference server observed on 2026-10-16

- Host: Pop!_OS 24.04, OptiPlex 7070 SFF, i7-9700, 32 GiB, NVIDIA RTX 3050 LP 6 GiB. Hardware from existing operator records; live hardware inventory was **not** repeated during this session.
- LAN SSH: `optiplex@192.168.40.212`.
- Tailscale SSH/streaming: `optiplex@100.121.156.34`. A stable MagicDNS name is preferable to embedding either IP in future releases.
- Public browser-gaming URL: `https://games.monumentrisk.com`, served separately from Tailscale by Caddy.
- Running Docker containers **observed** (not proof of pending image updates):

| Container | Image | Compose project / file |
| --- | --- | --- |
| wolf | ghcr.io/games-on-whales/wolf:stable | standalone |
| moonlightweb | ghcr.io/linckosz/moonlight-web:latest | standalone |
| slskd-vpn | slskd/slskd:0.25.1 | music-vpn / `/home/optiplex/music-vpn/compose.json` |
| qbittorrent-vpn | lscr.io/linuxserver/qbittorrent:5.1.4 | music-vpn / same file |
| music-vpn | qmcgaw/gluetun:v3.41 | music-vpn / same file |
| droppedneedle | droppedneedle/droppedneedle:latest | music-vpn / same file |
| open-webui | ghcr.io/open-webui/open-webui:main | searxng / `/home/optiplex/searxng/compose.yaml` |
| searxng | searxng/searxng:latest | searxng / same file |

- Wolf state: `/etc/wolf` bind-mounted to the container. Its NVIDIA driver volume was named `wolf-nvidia-driver-595.104.02` when inspected. **Do not** delete volumes while troubleshooting.
- MoonlightWeb state: named Docker volume `moonlightweb-test-data` mounted at `/data`. Do not delete or recreate it without a backup of its credentials and application state.
- Both Wolf and MoonlightWeb have `unless-stopped` restart policies. That is restart-on-daemon-start, **not** automatic image updating.
- Enabled systemd units observed: `caddy.service`, `docker.service`, `jellyfin.service`, `tailscaled.service`, `wolf-start.service`.
- Installed but disabled units observed: `caddy-api.service`, `tailscale-wait-online.service`.
- Other service units/scripts may exist; the list above reflects a name-filtered inspection, not an exhaustive audit.

## Authentication and remote administration

**Normal Web Gaming:** `https://games.monumentrisk.com`. MoonlightWeb 0.3.1 accepts a one-time access PIN or a reusable certificate-token file and saves a browser session if **Remember me** is enabled. The certificate-token file is a bearer credential; do not add it to the public codebase.

**Working LAN admin:** `https://192.168.40.212:8443/admin` after enrolling the browser and unlocking admin with the configured password. The public `/admin` URL instead returned the ordinary Wolf/Web Gaming UI in operator testing. Do **not** treat `games.monumentrisk.com/admin` as a working admin shortcut.

**Remote administration constraint:** MoonlightWeb v0.3.1's admin unlock checks for RFC1918/loopback/link-local addresses and does not classify Tailscale's `100.64.0.0/10` addresses as LAN. A direct `https://100.121.156.34:8443/admin` request can reach the service but is **not a verified way to unlock admin**.

**Draft 1.12.0 solution:** Settings → Web Gaming Admin starts an SSH local forward from the client to server loopback port 8443, then opens `https://127.0.0.1:<local-port>/admin`. The port is deterministic per SSH user/host, in the range 20000–39999; the bind address is loopback only. The helper reuses an existing verified SSH ControlMaster where possible. It requires reachable SSH (generally Tailscale), prior SSH key authorization, and a default browser with `xdg-open`. The first connection may need browser acceptance of MoonlightWeb's self-signed TLS certificate. **This helper is implemented in the draft branch but not yet live-tested.**

Manual fallback while abroad (run on the client after Tailscale is connected):

```sh
ssh -f -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18443:127.0.0.1:8443 optiplex@100.121.156.34
```

Then open `https://127.0.0.1:18443/admin`. This uses SSH authorization rather than making public internet visitors eligible for admin privilege.

**Manual SSH admin verification (2026-10-16):** The owner confirmed that the SSH local-forward test opened the admin page. This verifies the direct loopback path on the tested MacBook; it does **not** prove that the packaged shortcut works or that the same procedure has been tested from outside the home LAN.

**Native Moonlight:** It has a separate client certificate and Wolf pairing flow. The MoonlightWeb `.txt` token is unrelated and cannot replace native pairing. A client's first pairing to a new Wolf instance may still be required.

## Optional Bruiser AI

The owner confirms **Bruiser AI is operational** on the reference OptiPlex. Prior setup: Open WebUI `SERVER:3000`, host Ollama `:11434`, Docker SearXNG `:8080`. Container health was observed on 2026-10-16; port exposure and active model were not rechecked. Draft 1.12.0 derives the default Bruiser URL from the configured server host as `http://SERVER:3000`, with an optional `ai_url` override; Settings → Bruiser AI Admin opens Open WebUI `/admin/settings` and requires the existing admin login. This does not bypass authorization or maintain the AI containers. Validate LAN/Tailscale browser access on the actual client before release. A possible Studio synth/step sequencer with shared save slots is a **design proposal only**, documented in [application-design.md](application-design.md).

## Client identity backup

- **Preset `.onp`:** server settings only; no SSH keys or Moonlight pairing. Draft 1.12.0 writes a v2 preset that includes the optional `ai_url`; old v1 presets remain importable. Existing 1.11.9 clients may reject the newer preset key.
- **Full `.onb`:** encrypted snapshot of five predefined locations: launcher config, SSH Ed25519 private/public keys, native/AppImage Moonlight config, and Flatpak Moonlight config (when present).
- **Not presently included in `.onb`:** MoonlightWeb certificate-token file, browser cookies, Tailscale account enrollment, the entire server stack, or media and game files.
- Local token destination discussed: `~/.config/optiplex-desk/moonlightweb-certificate.txt` (permissions `0600`); actual placement has not been re-verified by remote inspection.
- A secret backup passphrase was shared in chat during setup. Rotate it before long-term storage. Never commit/upload decrypted backup contents.
- Restoring an `.onb` **overwrites** supported local SSH/Moonlight config. Use only on trusted devices, with recovery copies of any existing keys.

## Known-good behavior versus unverified work

Observed: Wolf and MoonlightWeb containers running; website PIN and file authentication worked; direct LAN admin worked; desktop launcher can start native Moonlight streams; Compose service locations identified.

Not yet end-to-end verified: public-domain gaming from a cellular network with Tailscale off; remote SSH-loopback admin from outside home; draft 1.12.0 package build on client; auto login to MoonlightWeb after browser cookie expiration; importing MoonlightWeb token from an encrypted backup; new server installation; GitHub synchronization of service drift.

Do not claim that any of these are automatic today.

## Recovery checks (read-only first)

Run one command at a time on the reference client:

```sh
ssh optiplex@100.121.156.34 'docker ps --format "{{.Names}} | {{.Image}} | {{.Status}}"'
```

```sh
ssh optiplex@100.121.156.34 'systemctl is-active wolf-start docker caddy jellyfin tailscaled'
```

If login fails: check Tailscale or LAN routing before changing Wolf. If Web Gaming fails while native Moonlight works: check Caddy and MoonlightWeb health. If native Moonlight fails while website works: inspect Wolf logs/pairing and GPU availability; do not delete Wolf or MoonlightWeb volumes as a first attempt.

## Next work in priority order

1. **Prove packaged SSH admin helper on MacBook:** manual SSH-loopback admin worked. Install the draft client with rollback available; test Settings → Web Gaming Admin, tunnel reuse and remote unlock over Tailscale **from outside the LAN** before marking ready.
2. **Preserve MoonlightWeb token in encrypted client backup:** use a new versioned record/compatibility strategy. Import once on trusted hardware. Preserve existing `.onb` restore behavior and test corrupted/old backups.
3. **Automatic Web Gaming login:** requires a deliberate browser integration; `browser=auto` only preserves browser sessions, it does **not** automatically submit a certificate after expiry. Do not pass the token in URLs or copy it into public JS.
4. **Read-only server drift monitor:** inventory container image IDs, names, health, Compose labels and selected systemd states; compare snapshots locally. Redact env, configs, volume contents, cookies and network secrets. Add alert/review before any GitHub PR. No automatic repo writes are deployed.
5. **Server replacement:** replace hard-coded server coordinates with a stable authenticated discovery endpoint/manifest; separately confirm SSH, Tailscale, DNS, Wolf pairing, Caddy, volumes and backups. No working fresh-server installer yet.
6. **Release gate:** GitHub CI build + unit tests, live smoke tests (LAN and away), tested rollback path, then human-reviewed merge and release. Do not silently change the working production client.

Operator preference: one Linux terminal command at a time; concise technical notes; preserve currently working services.
