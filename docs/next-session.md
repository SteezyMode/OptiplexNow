# Next session

Project: personal OptiPlex Now Linux launcher + home server. Start with [operations-handoff.md](operations-handoff.md) for the as-observed 2026-10-16 service inventory, authentication, backup scope, recovery procedures, and outstanding tests. Also see [server-setup.md](server-setup.md).

Repository: `SteezyMode/OptiplexNow`. `main` is released 1.11.9. Draft PR #1 / `feature/wolf-driver-maintenance` is an unreleased 1.12.0 candidate. It includes Wolf driver maintenance (not live-tested), Web Gaming and Web Gaming Admin, and an SSH loopback admin helper (not live-tested). Do not assume the package was installed on any client or server.

Immediate steps:
1. Check CI package and unit tests on the draft branch, including `tests/test_web_admin.py`.
2. Test Settings → Web Gaming Admin on a Linux client over Tailscale **from outside the LAN**. It should use an SSH loopback tunnel; MoonlightWeb 0.3.1 will not unlock admin over a direct Tailscale `100.x.x.x` address.
3. Verify the web admin shortcut uses the current configured server host, not `games.monumentrisk.com/admin`, and that old tunnels are not confused with changed server identities.
4. Verify the build on the actual MacBook/mac mini and test rollback before merging/releasing.
5. Add private MoonlightWeb token to **versioned encrypted** client backup and implement browser reauthentication after expiry; neither is currently implemented.
6. Create and test a read-only, secret-free server configuration drift monitor. Do not auto-push snapshots containing credentials to GitHub.
7. Later: stable server discovery, fresh-server provisioning, modular service installation, recovery checks.

Production safety: preserve Docker volumes, `/etc/wolf`, music stack and browser auth state. Never commit token files, SSH/Moonlight keys, `.onb` backups, VPN env files or passwords. Give one Linux command at a time when troubleshooting.
