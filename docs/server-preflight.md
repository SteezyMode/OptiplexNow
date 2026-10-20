# Local server preflight (prototype)

**Status:** Unreleased development implementation; NOT shipped in a tagged NOW release. **No fresh-host installer exists.**

This helper is the first read-only component of the proposed server onboarding work. It examines **the Linux computer where it runs**, not the remote host already selected in NOW's client. It is not a remote checker and does not validate an end-to-end game stream.

## Usage on a disposable development host

From source:

```sh
python3 server/server-preflight.py
python3 server/server-preflight.py --json
python3 -m unittest discover -s tests -v
```

After installing a development package built from this branch:

```sh
optiplex-now-preflight
optiplex-now-preflight --json
```

No sudo is needed, and running these commands must not install, alter or restart services. The tool does not connect to a NOW account or website, start Tailscale enrollment, pair a Moonlight client or access remote devices.

## Checks and limitations

| Observation | Method | Important limitation |
| --- | --- | --- |
| OS and architecture | Read /etc/os-release and machine architecture | Ubuntu/Pop!_OS 24.04 on amd64 is an **initial proposed test scope**, not a certification |
| RAM and disk | /proc/meminfo; free space in user's home filesystem | Not the selected game/project storage location; no disk stress test |
| GPU and NVIDIA driver | Read-only lspci and nvidia-smi queries | GPU vendor detection can be unavailable; an installed NVIDIA driver **does not prove** NVENC, codec support, hardware stream success or GPU/container compatibility |
| Tailscale | tailscale status --json, using only BackendState | Never exports peers, addresses, account names, tailnet name or keys; “connected” does not establish ACL access or client reachability |
| Docker | docker info, docker ps | Inaccessible daemon = **unavailable**, not empty; detection only covers running containers, not all installed images/Compose stacks |
| Wolf | Running Docker container/image hints and wolf-start.service | Does not verify Wolf configuration, API version, actual desktop sessions or persistent storage |
| Sunshine | sunshine executable, user/system sunshine.service | Flatpak or custom units may be missed; state is an observation only |
| Network ports | ss -H -ltnu, allowlisted Moonlight-related numbers | Does not identify owning process or prove an actual collision, and is not a complete backend-specific port audit |

The JSON schema version is currently `1`. `streaming_ready` always says `not_tested`. The tool does not output raw command results or stderr. Names, IP addresses, SSH users, network details and Docker container configuration should never be added to exported reports by default. Be careful when adding future host diagnostics; sanitized summaries are intentional.

Every external invocation is from a fixed read-only allowlist with a three-second deadline and without `shell=True`. Tests inject synthetic responses and confirm that sensitive Tailscale addresses/peers and port bind addresses are not emitted.

## Setup Wizard GUI (development)

The native GTK setup wizard now offers **CHECK THIS COMPUTER (READ-ONLY)** on the Server page. It opens an asynchronous local report window, shows progress, allows **CHECK AGAIN**, and can be closed without keeping the wizard blocked. Checks come from the packaged `/usr/lib/optiplex-now/server-preflight` helper run through the fixed `/usr/bin/python3` interpreter, without a shell and without arguments from server settings. The helper has a 40-second overall GUI timeout; its individual allowlisted commands have 3-second limits. The dialog neither runs a privileged installer nor reads the configured remote server. A missing helper or failed run yields a plain error and does not assume a successful connection.

The GUI smoke test covers dialog opening, recheck and safe early closing on isolated Xvfb. CI packages the checker, compiles the main GTK application and runs the smoke test. It does **not** confirm actual client input, Moonlight playback or the appearance on all themes/desktop sizes. The manual on-device UI and compatibility check are still required before release.

## Follow-on steps before calling this user-ready

1. Run and compare the report on a **disposable** Ubuntu/Pop!_OS 24.04 NVIDIA host, including a host with Docker permissions denied.
2. Improve evidence for encoder, audio/input and streaming ports using read-only mechanisms. Record confidence (`unknown` versus absent) rather than treating missing tools as negative evidence.
3. Validate the new responsive GTK report on a clean supported computer, including small-screen layout and close/retry behavior; improve accessibility and presentation from observations.
4. Implement a separate, least-privilege and explicitly authorized installer only after preflight correctness and rollback tests. Never share a general privileged Docker or Wolf control socket with the NOW web client.
5. Obtain a genuine picture/audio/control reconnect test from Moonlight on another machine before changing `streaming_ready` semantics.

This milestone must not modify the primary OptiPlex reference server, current Wolf sessions, Tailscale, Caddy, Docker volumes or streaming ports. No automated production install, release, or web registration is approved here.

Related: [Current status](CURRENT-STATUS.md), [server-setup reference](server-setup.md), [upstream-first server strategy](UPSTREAM-FIRST-WOLF-INTEGRATION.md).
