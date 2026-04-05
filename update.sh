#!/bin/bash
# Auto-update bedjet-mqtt from main and restart service if changed.
# Intended to run via cron on the Pi.

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR" || exit 1

git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): Updating from $LOCAL to $REMOTE"
    git reset --hard origin/main
    sudo systemctl restart bedjet
    echo "$(date): Service restarted"
else
    echo "$(date): Already up to date"
fi
