#!/bin/sh
set -eu

# Railway mounts persistent volumes as root. Change only the data mount,
# then drop privileges before starting the Python application.
if [ "$(id -u)" = "0" ]; then
  chown -R 10001:10001 /data
  exec gosu 10001:10001 python -m server.app
fi

exec python -m server.app
