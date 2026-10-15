#!/bin/bash
# Invoked only after the launcher's confirmation; never changes SSH trust policy.
set -u
host=${1:?Missing host}
user=${2:?Missing SSH user}
printf 'Restarting streaming on %s…\n' "$host"
ssh -t -o ConnectTimeout=8 -o ConnectionAttempts=1 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -l "$user" "$host" '
  if ! sudo /usr/local/sbin/wolf-prepare-devices; then
    echo "Device preparation failed. Wolf was not restarted."; exit 1
  fi
  if ! sudo docker restart --timeout 20 wolf; then
    echo "Wolf restart failed."; exit 1
  fi
  sleep 2
  running=$(sudo docker inspect --format "{{.State.Running}}" wolf) || exit 1
  if [ "$running" != true ]; then
    echo "Wolf did not stay running."; exit 1
  fi
  echo "Wolf is running. Try reconnecting with Moonlight."
'
result=$?
if [ "$result" -ne 0 ]; then
  printf '\nRestart was not confirmed successful (exit %s). Check the message above.\n' "$result"
fi
read -r -p 'Press Enter to close…' || true
exit "$result"
