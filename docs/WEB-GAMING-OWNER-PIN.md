# Owner-issued Web Gaming PIN — initial local-first implementation

**Status:** Draft; no live-server or new-browser E2E validation yet. **Issue:** [#59](https://github.com/SteezyMode/OptiplexNow/issues/59).

## Why the app needs this

Routine Web Gaming clients go to the existing valid public TLS site at **https://games.monumentrisk.com** and receive **a one-time access PIN from their server owner**. Ordinary clients must never access MoonlightWeb's `/admin` at loopback or use SSH. The existing admin shortcut remains available as an advanced owner action, but its localhost certificate warning is unresolved and never part of the client flow.

## Owner action, on server NOW only

When NOW runs locally on a machine with a Docker socket, **Settings → Streaming → ISSUE WEB GAMING ACCESS PIN (THIS SERVER)** appears. An explicitly authorized local operator clicks it, confirms one PIN for a new browser device, and NOW runs the upstream `moonlightweb --new-pin` command **inside the local `moonlightweb` container** over that machine's Unix Docker socket. A small six-digit result is displayed in a GUI dialog for the owner to share privately with the intended new device user. PIN is not kept in NOW config, presets, plaintext logs, URL, GitHub or remote browser. This feature does not auto-email the code.

This uses MoonlightWeb's documented **non-revoking** admin PIN-generation CLI; it does not call the session-revoking `/api/auth/regenerate`. Existing signed-in browser sessions remain valid. A prior unused access PIN may be superseded.

**Authorization boundary:** This first implementation uses the calling operator's **existing** local Docker socket authorization. No automatic `sudo`, new Docker group membership, `pkexec` privilege delegation, root TCP API, remote Docker context, SSH tunnel or external network listener is installed. A headless server or operator without authorized local Docker access cannot issue a code through this button; server installer / narrow Polkit control requires a separate security review. Membership in the local Docker group is highly privileged. NOW must not silently grant it.

The helper passes fixed Docker argv over `unix:///var/run/docker.sock` and validates that `moonlightweb` is running. Only six ASCII digits from the CLI's documented PIN output format are accepted; all other upstream responses map to fixed failure statuses in GTK. No Docker stderr is displayed. The code can fail safely if upstream changes its output format; it does not claim a PIN was issued if the format is unknown.

## Client onboarding

On a separate Linux client, **Pair Web Gaming in Browser** opens **https://games.monumentrisk.com**. The user enters the owner's PIN. On success MoonlightWeb retains its own browser session (not NOW credentials). Native Moonlight/Wolf client pairing is a separate challenge-response flow, handled by existing NOW Moonlight pairing actions.

## Manual acceptance still required

1. Verify the owner action appears **only** on the local Docker server and that an authorized server owner can issue exactly one six-digit code through the GTK window.
2. Check the generated code authorizes an unpaired browser at the existing HTTPS site, and a second use is rejected.
3. Verify existing paired MoonlightWeb devices, Wolf sessions and Caddy are unaffected; invalid/denied Docker access reports an error.
4. Verify native Wolf pairing with Moonlight independently.
5. Verify no admin TLS bypass, terminal use, SSH login, exposed admin API or direct service privilege in the **client** workflow.
6. Compare 1.14.0 upgrade, restart/reconnect, no Docker server, no GUI browser, cancellation and timeout.

**Remaining release blocker:** No complete remotely usable owner approval flow, emailed owner notification, valid-TLS advanced remote admin path, or clean-client E2E proof yet. Never represent this draft as fully shippable Linux onboarding.
