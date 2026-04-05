#!/bin/bash
# Auto-update bedjet-mqtt from main and restart service if changed.
# Intended to run via cron on the Pi.

set -e
PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR" || exit 1

# Prevent concurrent runs
exec 200>/tmp/bedjet-update.lock
flock -n 200 || { echo "$(date): already running"; exit 0; }

git fetch origin main || { echo "$(date): fetch failed"; exit 1; }

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): Updating from $LOCAL to $REMOTE"
    git reset --hard origin/main
    sudo systemctl restart bedjet
    sleep 5
    if ! systemctl is-active --quiet bedjet; then
        echo "$(date): WARNING — service failed to start after update"
    else
        echo "$(date): Service restarted successfully"
    fi
else
    echo "$(date): Already up to date"
fi
