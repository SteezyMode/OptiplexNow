# Persistent remote development sessions (tmux)

Status: operator workflow; documentation only. Last updated 2026-10-18.

## Why
When developing OptiPlex NOW remotely over Tailscale SSH (including from an iPhone over cellular), start interactive long-running work **inside a named tmux session on the OptiPlex host**. This keeps a terminal, active Codex CLI, build, or maintenance job connected to its server-side PTY if the MacBook closes, the iPhone locks, or an SSH connection drops. No VPN, GPU, Wolf desktop, Jellyfin, or application services need restarting.

This is primarily a **developer/operator practice**, not an end-user launcher feature. Do not wrap routine short one-off SSH commands in tmux.

## Requirements
- `tmux` installed on the **host**: `sudo apt install -y tmux` (installed interactively on 2026-10-18; no guarantee on other hosts).
- SSH access to `optiplex@100.121.156.34` through Tailscale or appropriate LAN address.
- The OptiPlex must remain powered on; network access must be restored to reattach.

## Typical workflow — one step at a time
On the host, after SSH login:

```bash
tmux new-session -A -s now-dev
```

`-A` attaches to the existing session or creates it. **Do not launch a second Codex process merely because the SSH connection dropped.** First reattach and inspect what was already running.

Inside the session, `cd` into the intended project and start the existing project-scoped launcher or regular build commands. E.g. for Studio: `~/.local/bin/studio-codex-art` from the Art Director, or the approved Threshold project-scoped Codex invocation from the Threshold repository. For NOW: use the existing repository's development commands; do not run unreviewed build or release scripts automatically.

Detach without ending processes: press `Ctrl+B`, release both keys, then press `D`. You can also simply disconnect SSH; tmux normally remains alive.

After reconnecting:

```bash
tmux ls
tmux attach -t now-dev
```

To inspect the current pane or stop a process, reattach before acting. Use `Ctrl+C` only if you intend to interrupt that foreground task. Closing the terminal **inside** the last tmux window can end that session. Avoid `tmux kill-server` during active projects.

From a MacBook with working SSH and Tailscale, you can explicitly attach in one command:

```bash
ssh -t optiplex@100.121.156.34 'tmux new-session -A -s now-dev'
```

## Naming convention
- `threshold`: Threshold Godot gameplay / integration work
- `studio-art`: Art Director reference and character production
- `now-dev`: OptiPlex NOW app and launcher development
- `server-maint`: deliberate server maintenance, only when needed

Keep sessions project-scoped. Avoid launching resource-heavy Blender jobs concurrently without checking existing work.

## What tmux does NOT do
- **It does not survive a host reboot, power loss, user session shutdown, or tmux server crash.**
- It does not automatically resume a Codex process terminated before tmux was used. Saved Codex conversations can often be resumed separately using `codex resume`.
- It does not guarantee an external Codex/API connection will survive a transient outage; reconnect and inspect the running task.
- It does not make a process restart-safe, preserve unsaved editor buffers, provide backups, or increase Codex usage limits.
- It does not make a Wolf GUI session persistent or repair the broken Wolf desktop AI Workspace shortcut.

## Recovering from an abrupt client shutdown
1. Reconnect by Tailscale SSH.
2. Run `tmux ls` and reattach an existing named session if present.
3. Check whether the specific Codex or build process is still alive **before** starting a replacement.
4. If no old tmux session exists, inspect generated artifacts and use project-appropriate Codex conversation resume. Keep work versioned and leave existing services untouched.

OptiPlex NOW context: the OptiPlex NOW repository and its maintenance scripts. Documented as a reusable operator practice; no host/container/service configuration changed by this document.
