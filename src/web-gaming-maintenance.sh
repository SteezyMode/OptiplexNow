#!/bin/sh
# Run the packaged server-side MoonlightWeb manager via the configured SSH host.
# No credentials or Docker socket cross to the client.
set -u
host=${1:?Missing server host}
user=${2:?Missing SSH user}
echo "OptiPlex NOW — Web Gaming maintenance"
echo "Connection: $user@$host"
echo "The helper must also be installed on the server."
echo
result=0
ssh -tt -o ConnectTimeout=8 -o ConnectionAttempts=1 \
  -o ServerAliveInterval=10 -o ServerAliveCountMax=3 \
  -l "$user" "$host" \
  'sudo /usr/lib/optiplex-now/moonlightweb-maintenance menu' || result=$?
if [ "$result" -ne 0 ]; then
  echo "Maintenance did not complete (exit $result). No success was assumed."
fi
printf '\nPress Enter to close...'
read answer || true
exit "$result"
