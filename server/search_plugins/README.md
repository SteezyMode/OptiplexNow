# API Bay-only Bruiser searches

**Protected baseline:** November 3, 2026 personal alpha. The existing qBittorrent
container, media, transfers, Tailscale, Gluetun and client remain intact until
the owner explicitly applies the change.

## Design

- A self-contained qBittorrent Nova plugin: `server/search_plugins/bruiser_apibay.py`.
  Single HTTPS API request, 4-second network timeout, no source pagination,
  100 maximum results, direct verified magnet links.
- A narrowly scoped reversible switch:
  `tools/manage_apibay_search.py`. It is inert by default. Inside the running
  `qbittorrent-vpn` container: no arguments shows status; `--apply` verifies
  a pinned Git source and isolated Nova run, installs through qBittorrent's
  supported WebUI Search API, validates the installed plugin and a real read-only
  search, stores the enabled-state backup, then disables only the known
  TorrentsCSV and LimeTorrents engines. `--rollback` restores those exact
  engine enable states and disables API Bay.
- Existing legacy search engines stay **installed**, not deleted. The backup
  is saved with mode 0600 at
  `/config/qBittorrent/.bruiser-search-rollback-v1.json`.
- Unexpected plugin states, incompatible source, failed verification or an
  existing rollback backup block activation; no assumptions.
- The release's owner broker still calls `plugins=enabled`, so with only
  API Bay enabled, Bruiser searches only API Bay. A separate future release
  must ensure a newly installed host has its managed plugin provisioned
  before using an explicit provider name.

## Evidence

- API Bay single-engine Nova search of `resident evil`: 100 rows in 0.69s,
  100 unique infohashes, zero webpage links and zero invalid entries.
- `south park s29e04`: 12 direct magnet results in 0.42s, whereas
  TorrentsCSV returned zero for that term.
- TorrentClaw omitted the infohash and magnet fields required by a
  free/public client. It is excluded from the proposed default.
- No assertion that all API Bay search terms will finish within one second,
  or that a VPN kill-switch is certified by these API probes.

## Validation gates

1. Exact-head GitHub unit/package/sanitizer CI passes.
2. Owner uses the no-argument read-only status and the temporary Nova proof.
3. Only then owner explicitly runs `--apply` inside `qbittorrent-vpn`.
4. Run both `south park s29e04` and `resident evil` in the real Bruiser
   Downloads interface and verify timing and results.
5. If behavior regresses, invoke the same script with `--rollback`.

The script does not download torrents, modify the torrent queue, restart the
container, change VPN credentials, install any other service, or modify host
SSH permissions. It should be packaged for operator access in a later release,
but must never run unprompted as part of a `.deb` update.

## Debian packaging checkpoint

The `.deb` carries both the single-file API Bay engine and the operator-only
management utility under `/usr/share/optiplex-now/search/`. Its installed
package smoke test checks that both files compile and that the manager's pinned
Git blob matches the packaged plugin. **Installing or updating the .deb does not
install or enable a qBittorrent plugin**, does not touch Docker and does not
change existing users' provider selections. This keeps the accepted personal
alpha baseline intact while preparing a reproducible, owner-approved host
setup integration. A managed fresh downloader installer remains a separate
milestone: the current host installer principally covers Wolf and adoption.

## Dual-source category strategy (follow-on draft)

- **All (default):** both the reviewed API Bay and Bitsearch plugins are
  explicitly selected in one qBittorrent search job. qBittorrent starts
  engines concurrently; stream results are presented incrementally.
- **PC Games:** Bitsearch only (`category=6&subCategory=1`). This source
  returned Resident Evil Requiem torrents with up to 2,871 reported seeders,
  compared with much lower counts in the reference API Bay PC Games search.
- **Movies, TV, Music, Software:** API Bay only. On API Bay the category is
  filtered from its returned `category` metadata, using proven `cat=0`
  because comma-separated API Bay categories returned no matches on the
  reference host. This means its **100-result upstream cap precedes** category
  filtering; we do not claim exhaustive category coverage.
- Bitsearch's documented unauthenticated quota is **200 requests/day/IP**;
  All and Games searches consume one request each, other categories do not.
- The host validates a strict route allowlist, never runs `plugins=enabled`,
  and deduplicates valid magnets by infohash across successive result pages.
  It never queues a torrent as part of a search.
- This routing requires both reviewed plugins installed before upgrading the
  host broker and client. The in-service API Bay-only baseline remains the
  rollback target until host acceptance.
