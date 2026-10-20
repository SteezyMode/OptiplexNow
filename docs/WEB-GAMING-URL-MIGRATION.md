# Web Gaming URL migration / legacy presets

**Scope:** OptiPlex NOW client only. No changes to Wolf, Caddy, MoonlightWeb or the server.

## User-visible change

Older NOW versions had a fixed developer-specific Web Gaming address in client source. This address was **never persisted in existing config.ini**, so a new build cannot infer an individual user's intended Web Gaming URL from the old configuration. An automatic migration would incorrectly send unrelated users to the developer's server. Do **not** guess the URL from Tailscale membership or promote a magic hostname to an account identity.

- **Existing install:** Your stored server, SSH settings, videos/music URLs, tray selections, Moonlight identity, and .onb client backup format are retained. If you previously used the fixed Web Gaming shortcut, open **Settings → Web Gaming URL (optional)** and enter the correct reachable HTTP(S) base URL once. Your old shortcut will not silently redirect to the developer's server; it prompts you to configure it.
- **New install:** Web Gaming URL is blank until the chosen server actually supplies a compatible web gaming gateway. It is optional and does not block native Moonlight streaming.
- **.onp presets:** New exports use **v3**, carrying the optional URL. Legacy **v1/v2 imports continue to work**. An old preset explicitly clears the previous host's Web Gaming URL to avoid routing a newly selected host to the previously configured service. Invalid/potentially credential-bearing URLs are rejected; unknown secret keys are rejected.
- **.onb backups:** Preserve existing encryption format and contents. config.ini already travels inside the encrypted backup, and includes the new non-secret URL after it is explicitly configured. Restore only to a trusted computer as before.

## Checks before release

- Unit tests cover v3 round-trip, old v1/v2 import, v2 rejection of new keys, refusal of query-token URLs, no change on invalid import, and unchanged private-path restrictions.
- The entire NOW native GTK package, preset helper, encrypted backup helper and setup wizard must pass CI; confirm one real upgrade with a copy of older config and preferences.
- A live browser streaming regression is separate: Web Gaming requires a reachable supported **server-side** gateway but never a public internet domain; native Moonlight works independently.
