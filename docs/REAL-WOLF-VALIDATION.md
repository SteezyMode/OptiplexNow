# Real Wolf compatibility gate

**Purpose:** determine what has actually been exercised against upstream Wolf,
rather than confusing mocked request tests with a running daemon or gameplay.
This is the next part of [#154](https://github.com/SteezyMode/OptiplexNow/issues/154).

## Evidence levels

1. **Offline simulation (passed):** tests in `tests/test_wolf_socket_protocol.py`
   use a fake AF_UNIX HTTP server, not Wolf.
2. **Real daemon read-only GET (passed in PR #167):**
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

In PR #167, GitHub Actions [run 39757678257](https://github.com/SteezyMode/OptiplexNow/actions/runs/39757678257)
booted an isolated **actual** Wolf daemon and our adapter received valid
read-only GET responses: **2 apps, 1 profile, 0 paired clients, 0 sessions,
0 lobbies**. The exact upstream image digest was
`sha256:b0ef253739f9bd49b71eba7e150c955fd05990c0d409e666d89236995351551a`,
now pinned in the compatibility workflow. The image's own Docker volume at `/run/user/wolf/` had to be
handled explicitly, without allowing arbitrary external data volumes.
Prior CI failures were fixture assertion, cleanup and mount-path normalization
errors, **not** evidence of defects in Wolf. The complete fixes are in
[ENGINEERING-TRAIL.md](ENGINEERING-TRAIL.md).

[PR #168 actual Wolf run 39761010450](https://github.com/SteezyMode/OptiplexNow/actions/runs/39761010450)
subsequently confirmed live Create/Join **schema** compatibility with the pinned
Wolf image and returned `success: true` for **one real disposable Create
POST** with a harmless `process` runner (`sleep 10`). There were no
clients, Moonlight sessions, GPU video, Steam data, or Join POSTs.
A real **Steam** Create+Join and physical client stream **have not been
performed**. All code paths manipulating the owner's real Steam workspace
remain unconnected to the reference host.

## Read-only disposable-container probe

`server/probe_real_wolf.py --container now-wolf-compat-EXAMPLE` only uses the
five Wolf `GET` inventory endpoints. It refuses the production `wolf` name,
requires a special test label and a single scratch `/etc/wolf` bind mount,
plus only image-declared fresh anonymous Docker volumes,
rejects host networking and privileged containers, and never issues a POST.
It reports counts only; actual sessions may contain AES keys and must not be
logged, printed or uploaded.

The automated runner creates a unique container named
`now-wolf-compat-<GitHub run ID>`, tags it
`io.optiplex-now.compat-disposable=true`, and binds a new scratch directory
under the runner temporary path. It pulls the upstream digest-pinned test image
and records the resolved **content digest** in the run log and summary. The
workflow now uses the previously verified immutable digest instead of a mutable
tag. Changing that digest requires a new recorded real-daemon compatibility run.

**Do not execute this workflow against the production OptiPlex.** It is a
GitHub-hosted disposable attempt and does not use the user's host. If the
non-GPU container cannot boot, capture that as a hardware dependency, not a
Wolf application defect. The read-only probe cannot prove profile switching,
Steam data continuity, client isolation or successful Wolf Create/Join.

## Disposable real Wolf lobby schema and process-Create test (PR #168)

The pinned CI workflow now checks Wolf's live `GET /api/v1/openapi-schema`
against NOW's required lobby fields, tagged Docker runner and string-valued
Join session ID. Earlier tests exposed that NOW's mock Steam runner lacked
three Wolf-required fields: `mounts`, `devices`, `ports`. The current
planner validates these before permitting a lobby plan.

Only if the daemon is running with empty clients/sessions/lobbies and its
pinned image, scratch-only state and isolation are independently confirmed,
the workflow attempts ONE disposable `CreateLobby` POST using a `process`
runner with `sleep 10`. A Create result is reported separately from
schema compatibility. No real Steam runner is used, and no Join is attempted
without an authentic Moonlight session. A blocked result is not mislabeled
as a passing stream. GitHub's temporary container cleanup discards the
entire test state.

**Do not confuse this with gameplay acceptance.** Physical GPU hardware,
Moonlight pairing, Wolf UI session, real owner Steam Create+Join, safe
session handoff, bypass denial and final fresh-client acceptance remain
unverified and outside this CI environment. See #154 and ENGINEERING-TRAIL.

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
