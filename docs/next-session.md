# Next session

Project: personal OptiPlex Now Linux launcher + home server. Start with [operations-handoff.md](operations-handoff.md) for the as-observed 2026-10-16 service inventory, authentication, backup scope, recovery procedures, and outstanding tests, and [application-design.md](application-design.md) for the core/optional service boundary and Studio proposal. Also see [server-setup.md](server-setup.md).

Repository: `SteezyMode/OptiplexNow`. `main` is released 1.11.9. Draft PR #1 / `feature/wolf-driver-maintenance` is an unreleased 1.12.0 candidate. It includes Wolf driver maintenance (not live-tested), Web Gaming and Web Gaming Admin, an SSH loopback admin helper (not packaged-client-tested), and an optional Bruiser AI shortcut/configuration. The eight primary dashboard actions are unchanged; AI is in Additional Services. The owner reports Bruiser operational; only Open WebUI and SearXNG containers were observed. Do not assume the package was installed on any client or server.

Immediate steps:
1. Check CI package and unit tests on the draft branch, including `tests/test_web_admin.py` and `tests/test_optional_services.py`. The manual SSH-loopback admin path was reported working on the MacBook.
2. Test Settings → Web Gaming Admin on a Linux client over Tailscale **from outside the LAN**. It should use an SSH loopback tunnel; MoonlightWeb 0.3.1 will not unlock admin over a direct Tailscale `100.x.x.x` address.
3. Verify the web admin shortcut uses the current configured server host, not `games.monumentrisk.com/admin`, and that old tunnels are not confused with changed server identities.
4. Verify the build on the actual MacBook/mac mini and test rollback before merging/releasing.
5. Add private MoonlightWeb token to **versioned encrypted** client backup and implement browser reauthentication after expiry; neither is currently implemented.
6. Test Bruiser URL from default SERVER:3000, the optional ai_url override, and Settings → Bruiser AI Admin (/admin/settings) with an authorized admin user. Confirm Ollama and SearXNG separately if troubleshooting AI. Create and test a read-only, secret-free server drift monitor; never auto-push credentials to GitHub.
7. Later: stable server discovery, fresh-server provisioning, modular service installation, recovery checks. Studio MIDI sequencer/synth with centrally stored cross-client save slots is only a proposal; do not confuse it with shipped features.

Production safety: preserve Docker volumes, `/etc/wolf`, music stack and browser auth state. Never commit token files, SSH/Moonlight keys, `.onb` backups, VPN env files or passwords. Give one Linux command at a time when troubleshooting.
