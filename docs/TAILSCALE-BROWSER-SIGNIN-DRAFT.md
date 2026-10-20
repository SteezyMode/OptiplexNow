# Tailscale browser sign-in helper (draft)

The NOW Setup Wizard first checks whether Tailscale is already connected. If so, it **never triggers another login**.

On explicit **Connect Tailscale** click when sign-in is required, the experimental Linux client helper uses the installed Polkit agent (`pkexec`) to authorize Tailscale's official CLI `up --json`, reads consecutive **multiline** JSON documents from `tailscale up --json` (including its `AuthURL` followed by a completion-state object), validates authorization URLs against `https://login.tailscale.com/a/`, and opens only that URL in the *unprivileged user's own browser*. Neither the URL nor credentials are saved or logged.

The helper must be tested on a **fresh disposable Linux client** with a graphical Polkit agent. Polkit availability, local privilege prompts, JSON output compatibility, browser focus, cancellation behavior, long-running CLI process lifetime, and Tailscale status refresh must be verified manually. This change is not evidence that the entire login flow works on all distributions. The existing terminal fallback remains.

**No server/Tailscale-network changes, privileged port, or custom provider tokens are needed.** Do not use Tailscale admin API or ship a reusable tailnet enrollment key as a shortcut.

Known limitation: the client presently displays an informational status when the helper starts but doesn't yet provide a confirmed, inline wizard completion indicator. The user can navigate and return to the Tailscale wizard page to refresh the read-only state. A subsequent review should replace this with a clean in-window pending/confirmed/error indicator after the browser-auth path is tested.

**Gate G0 parser regression (2026-10-20):** A draft originally parsed JSON one physical line at a time, although upstream Tailscale's `--json` output is pretty-printed across multiple lines. This has been corrected with a bounded incremental decoder and mock subprocess/browser tests. The package smoke test now verifies the login helpers are actually installed. Source/CI tests do **not** prove the graphical Polkit prompt, default-browser opening, or eventual Tailscale enrollment on a fresh client; these remain blocked behind G2/G5 acceptance. See the frozen [Linux client v1.0 contract](CLIENT-INSTALLER-MVP.md) in draft #49.
