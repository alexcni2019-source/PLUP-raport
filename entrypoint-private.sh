#!/bin/sh
set -eu
umask 077

# Railway mounts the persistent volume as root. Drop privileges immediately.
if [ "$(id -u)" = "0" ]; then
  chown -R 10001:10001 /data
  exec gosu 10001:10001 /app/entrypoint-private.sh
fi

: "${PLUP_PASSWORD:?Set PLUP_PASSWORD in the host's secret variables.}"
: "${PLUP_SESSION_SECRET:?Set PLUP_SESSION_SECRET in the host's secret variables.}"

socket=/tmp/plup-tailscaled.sock
tailscaled --tun=userspace-networking --statedir=/data --state=/data/tailscale.state --socket="$socket" &
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

# A one-off key is needed only when the persistent node has not joined yet.
if tailscale --socket="$socket" status --json | python -c 'import json,sys; sys.exit(json.load(sys.stdin).get("BackendState") != "Running")'; then
  unset TS_AUTHKEY
else
  : "${TS_AUTHKEY:?Set TS_AUTHKEY in the host's secret variables for the first login.}"
  # Read the key from a short-lived file rather than exposing it in argv.
  keyfile=$(mktemp)
  trap 'rm -f "$keyfile"; cleanup' EXIT INT TERM
  printf '%s' "$TS_AUTHKEY" > "$keyfile"
  unset TS_AUTHKEY
  tailscale --socket="$socket" up --auth-key="file:$keyfile" --hostname=plup-raport --accept-dns=false
  rm -f "$keyfile"
  trap cleanup EXIT INT TERM
fi

# Serve is tailnet-only. Railway may assign a port other than the Dockerfile default.
# The proxy must target the exact port read by server.app from PORT.
tailscale --socket="$socket" serve --bg --https=443 "${PORT:-8000}"
python -m server.app &
app_pid=$!
wait "$app_pid"
