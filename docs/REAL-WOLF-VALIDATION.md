# Real Wolf compatibility gate

**Purpose:** determine what has actually been exercised against upstream Wolf,
rather than confusing mocked request tests with a running daemon or gameplay.
This is the next part of [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## Evidence levels

1. **Offline simulation (passed):** tests in `tests/test_wolf_socket_protocol.py`
   use a fake AF_UNIX HTTP server, not Wolf.
2. **Real daemon read-only GET (attempted in PR #167):**
   `.github/workflows/wolf-real-compat.yml` pulls upstream Wolf into an isolated
   ephemeral GitHub Actions container. It deliberately gives Wolf no GPU,
   input devices, host networking, host filesystem mounts (except a new empty
   Wolf-only scratch directory), or Docker socket. A missing API is an explicit
   **blocked** result, not proof of API incompatibility. Record the image digest
   and the actual job outcome. The workflow job itself may complete successfully
   after reporting BLOCKED; read the step summary.
3. **Real Wolf Create/Join with a real Moonlight session (NOT RUN):** requires a
   separately controlled GPU-equipped **disposable** physical/test host with the
   official Wolf prerequisites and a deliberately disposable user/profile.
4. **NOW real-device, fresh-owner Games (NOT RUN):** requires authenticated
   host broker, direct-upstream denial, persistent Steam workspace, session
   conflict/recovery and a genuinely clean client, with gameplay/input/audio.
   None of the previous levels establish this milestone.

## Verified upstream daemon result (October 22, 2026)

In PR #167, GitHub Actions [run 39757247197](https://github.com/SteezyMode/OptiplexNow/actions/runs/39757247197)
booted an isolated **actual** Wolf daemon and our adapter received valid
read-only GET responses: **2 apps, 1 profile, 0 paired clients, 0 sessions,
0 lobbies**. The image's own Docker volume at `/run/user/wolf/` had to be
handled explicitly, without allowing arbitrary external data volumes.
Prior CI failures were fixture assertion, cleanup and mount-path normalization
errors, **not** evidence of defects in Wolf. The complete fixes are in
[ENGINEERING-TRAIL.md](ENGINEERING-TRAIL.md).

The first actual POST to create/join a persistent Steam lobby **has not
been made**. All code paths that would manipulate a Steam workspace remain
unconnected to the owner reference host. The validated GET contract is the
narrowest meaningful real-Wolf compatibility milestone so far.

## Read-only disposable-container probe

`server/probe_real_wolf.py --container now-wolf-compat-EXAMPLE` only uses the
five Wolf `GET` inventory endpoints. It refuses the production `wolf` name,
requires a special test label and a single scratch `/etc/wolf` bind mount,
rejects host networking and privileged containers, and never issues a POST.
It reports counts only; actual sessions may contain AES keys and must not be
logged, printed or uploaded.

The automated runner creates a unique container named
`now-wolf-compat-<GitHub run ID>`, tags it
`io.optiplex-now.compat-disposable=true`, and binds a new scratch directory
under the runner temporary path. It pulls the upstream `:stable` test image
and records the resulting **content digest** in its summary. The tag is
mutable, so the recorded digest is the evidence anchor, not the tag name.

**Do not execute this workflow against the production OptiPlex.** It is a
GitHub-hosted disposable attempt and does not use the user's host. If the
non-GPU container cannot boot, capture that as a hardware dependency, not a
Wolf application defect. The read-only probe cannot prove profile switching,
Steam data continuity, client isolation or successful Wolf Create/Join.

## Independent GPU host acceptance (future)

Use a **second disposable host**, not the personal OptiPlex that holds the
owner's Steam login, Jellyfin media and shared Wolf configuration. Record the
exact Wolf image digest, kernel, GPU and driver, host OS, Docker version,
NOW commit and adapter/source version before starting.

- Provision Wolf according to the upstream official quickstart, with all
  required input, GPU and Docker runtime devices, but separate scratch
  `/etc/wolf` and Steam state. Do not copy real login credentials,
  encryption keys, media mounts, private DNS, existing client certificates
  or active host services.
- Confirm the daemon's actual API via its private Unix socket and compare
  profiles, apps, clients, sessions and lobbies with the assumptions in
  `src/owner_lobby.py`. Confirm the actual `client_id` vs
  `WOLF_SESSION_ID` relationship. Redact all raw JSON before commit/logging.
- Pair a new disposable Moonlight client, start disposable Wolf UI, create a
  **new disposable Steam/lobby workspace**, and verify the actual two POST
  API responses. Check both successful join and deliberate interrupted
  create/join. No automatic retries after uncertain results.
- Test simultaneous and stale sessions, disconnection/reconnection, reboot
  and idempotent lease recovery before enabling automatic client launches.
- Verify unapproved/revoked clients cannot reach the owner Steam workspace
  through direct Wolf apps or Wolf UI. A private lobby PIN is insufficient
  evidence. Only then consider integration into NOW Games.
- Record what failed, complete reproduction steps and recovery in
  [ENGINEERING-TRAIL.md](ENGINEERING-TRAIL.md) and issue #154, including
  whether hardware/environment or software actually caused the failure.

The currently published release and the reference host's existing shortcuts
are unchanged. A CI status of success for an **attempted** daemon boot is not
real Wolf gameplay acceptance.

**Upstream prerequisites:** [Wolf quickstart](https://games-on-whales.github.io/wolf/stable/user/quickstart.html)
and [Wolf API](https://games-on-whales.github.io/wolf/stable/dev/api.html).
