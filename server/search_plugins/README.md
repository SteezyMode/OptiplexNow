# Bruiser search-provider candidates (not yet installed)

These are small, independent Python/qBittorrent Nova search engines, designed
for **fast public metadata lookup**, not managing downloads. They are not
installed by the `.deb` and are not enabled on any host by this directory.

- `bruiser_apibay.py`: one API Bay JSON request, up to 100 entries.
- `bruiser_torrentclaw.py`: one unauthenticated TorrentClaw request, up to 50
  content groups / 100 torrents. No API key or account.
- `_bruiser_source.py`: shared bounds, query decoding, magnet normalization,
  payload validation and short HTTP timeout. The leading underscore keeps it
  hidden from Nova's engine-discovery scan.

Both use standard Python TLS-verified HTTP. The upstream Nova runner installs
qBittorrent's optional SOCKS proxy at the socket layer before engine execution,
which the standard-library HTTP client respects. They must nevertheless be
validated through the user's actual downloader VPN network namespace before
installation. This does **not** establish VPN kill-switch correctness.

Tests run offline: `python3 -m unittest discover -s tests -p 'test_bruiser_search_plugins.py'`.

The separate `tools/probe_nova_sources.py` can run a transient, SHA-256-pinned
Nova test against the live indexes **without installing any plugin**. It copies
the existing `nova2.py`, `helpers.py`, and `novaprinter.py` only into a private
temporary directory, tests both engines there, and removes it. It never calls
the qBittorrent Web API, modifies a download, or changes registered plugins.

No install/update path is connected yet. Future deployment must explicitly
verify the provider outputs, own only its three plugin files, stage a backup,
be repeatable and rollback-safe, and avoid changing existing search engines.
