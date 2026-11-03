# Bruiser API Bay search candidate (not yet installed)

The API Bay engine makes one bounded HTTPS JSON request and prints only validated direct magnet links through qBittorrent Nova. It uses a shared parser and URL helper, with a four-second per-request timeout, 1 MiB response cap, maximum 100 results, and 40-digit hexadecimal infohash validation. No account, API key, or extra service is required.

- `bruiser_apibay.py`: provider adapter
- `_bruiser_source.py`: shared validation (underscore-prefixed helper is not a Nova search engine)
- `tools/probe_nova_sources.py`: SHA-256-pinned temporary Nova-runner test for specific episode queries
- `tools/probe_apibay_results.py`: temporary Nova test of broad search, repeated titles and invalid links

**Reference-host evidence:** API Bay returned 12 matching South Park S29E04 titles with 12 usable magnets in 0.42 seconds through the real Nova runner. TorrentClaw is **excluded**: its public unauthenticated API omitted infohash and magnet identifiers for 24 matching results. LimeTorrents is not recommended as a default because its search remained Running beyond 25 seconds. TorrentsCSV remains the existing working fallback; we have not established whether removing it would harm breadth of coverage.

The client, host broker, qBittorrent container, VPN and working existing plugins are untouched by this source-only draft. No plugin installation/activation or default-selection policy is connected yet. A separate release-gated, backup-safe provisioning path is required before promotion.

Standard-library HTTPS is routed through Nova's configured socket-level SOCKS proxy, if present. Testing within the downloader network namespace does **not** establish VPN kill-switch correctness.

Offline regression test: `python3 -m unittest discover -s tests -p 'test_bruiser_search_plugins.py'`.
