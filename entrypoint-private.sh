#!/bin/sh
set -eu
umask 077

# Railway mounts the persistent volume as root. Drop privileges immediately.
if [ "$(id -u)" = "0" ]; then
  chown -R 10001:10001 /data
  exec gosu 10001:10001 /app/entrypoint-private.sh
fi

: "${TS_AUTHKEY:?Set TS_AUTHKEY in the host's secret variables.}"
: "${PLUP_PASSWORD:?Set PLUP_PASSWORD in the host's secret variables.}"
: "${PLUP_SESSION_SECRET:?Set PLUP_SESSION_SECRET in the host's secret variables.}"

socket=/tmp/plup-tailscaled.sock
tailscaled --tun=userspace-networking --state=/data/tailscale.state --socket="$socket" &
ts_pid=$!
app_pid=
cleanup() {
  trap - EXIT INT TERM
  if [ -n "$app_pid" ]; then kill "$app_pid" 2>/dev/null || :; fi
  kill "$ts_pid" 2>/dev/null || :
  if [ -n "$app_pid" ]; then wait "$app_pid" 2>/dev/null || :; fi
  wait "$ts_pid" 2>/dev/null || :
}
trap cleanup EXIT INT TERM

ready=0
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if tailscale --socket="$socket" status --json >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then echo 'Tailscale daemon failed to start.' >&2; exit 1; fi

# The auth key is read from a short-lived file, so it is not exposed in argv.
keyfile=$(mktemp)
trap 'rm -f "$keyfile"; cleanup' EXIT INT TERM
printf '%s' "$TS_AUTHKEY" > "$keyfile"
unset TS_AUTHKEY
tailscale --socket="$socket" up --auth-key="file:$keyfile" --hostname=plup-raport --accept-dns=false
rm -f "$keyfile"
trap cleanup EXIT INT TERM

# Serve is tailnet-only. Never run "tailscale funnel" for this application.
tailscale --socket="$socket" serve --bg --https=443 8000
python -m server.app &
app_pid=$!
wait "$app_pid"
