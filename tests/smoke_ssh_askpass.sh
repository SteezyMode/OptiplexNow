#!/usr/bin/env bash
set -euo pipefail

# Starts packaged askpass without SSH or a server. Verifies a real native
# dialog appears and that cancelling the process never prints a password.
askpass="${NOW_ASKPASS:-/usr/lib/optiplex-now/now-ssh-askpass}"
test -x "$askpass"

for kind in password host; do
  if [[ "$kind" == host ]]; then
    prompt="The authenticity of host 'test.example' can't be established. ED25519 key fingerprint is SHA256:TEST. Are you sure you want to continue connecting (yes/no/[fingerprint])?"
    title="Verify SSH Host Key"
  else
    prompt="testuser@test.example's password:"
    title="Authorize SSH Access"
  fi
  temp="$(mktemp -d -t now-ssh-askpass.XXXXXX)"
  NOW_TEST_ASKPASS="$askpass" NOW_TEST_PROMPT="$prompt" NOW_TEST_TITLE="$title" NOW_TEST_TMP="$temp" \
  xvfb-run -a -s "-screen 0 1024x768x24" dbus-run-session -- bash -c '
    set -euo pipefail
    "$NOW_TEST_ASKPASS" "$NOW_TEST_PROMPT" >"$NOW_TEST_TMP/reply" 2>"$NOW_TEST_TMP/error" &
    child=$!
    trap "kill $child 2>/dev/null || true; wait $child 2>/dev/null || true" EXIT
    appeared=0
    for attempt in {1..50}; do
      if xwininfo -name "$NOW_TEST_TITLE" >/dev/null 2>&1; then
        appeared=1
        break
      fi
      if ! kill -0 "$child" 2>/dev/null; then break; fi
      sleep .1
    done
    [[ "$appeared" -eq 1 ]] || {
      echo "GTK SSH askpass dialog did not appear: $NOW_TEST_TITLE" >&2
      cat "$NOW_TEST_TMP/error" >&2
      exit 1
    }
    [[ ! -s "$NOW_TEST_TMP/reply" ]] || {
      echo "SSH askpass emitted credentials without consent" >&2
      exit 1
    }
  '
  rm -rf -- "$temp"
  echo "Graphical SSH askpass '$kind' prompt launched and revealed no credentials."
done
