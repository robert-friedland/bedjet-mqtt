#!/bin/bash
# Reset BlueZ adapter cache to fix GATT service discovery corruption.
# Must be run as root (via sudoers entry).
ADAPTER_DIR=$(find /var/lib/bluetooth/ -maxdepth 1 -mindepth 1 -type d | head -1)
if [ -n "$ADAPTER_DIR" ]; then
    systemctl stop bluetooth
    rm -rf "$ADAPTER_DIR"
    systemctl start bluetooth
    sleep 5
fi
