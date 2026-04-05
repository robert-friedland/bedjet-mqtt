# CLAUDE.md

## Project overview

Python service that bridges BedJet V3 devices over Bluetooth Low Energy (BLE) to MQTT for Home Assistant integration. Runs on a Raspberry Pi Zero W as a systemd service (`bedjet.service`).

## Architecture

- `app.py` — Entry point. Connects to MQTT, discovers BedJets, routes MQTT commands to BLE, runs heartbeat.
- `bedjet.py` — Core BedJet class. Manages BLE connection (via bleak), parses device state from BLE notifications, publishes state to MQTT.
- `const.py` — BLE UUIDs, command bytes, fan mode mappings.
- `config.py` — User config (git-ignored). Copy from `sample_config.py`.
- `diagnose.py` — Standalone diagnostic script for troubleshooting.
- `reset_bluetooth.sh` — Helper script for BlueZ cache recovery (requires sudoers entry).

## Runtime environment

- Raspberry Pi Zero W running Raspberry Pi OS Bullseye
- Python 3.9, bleak 1.1.1, asyncio-mqtt
- Systemd service: `sudo systemctl start/stop/restart bedjet`
- Logs: `journalctl -u bedjet -f`
- Service file: `/etc/systemd/system/bedjet.service` (User=pi, Restart=on-failure)

## Key patterns

- BLE notifications use bleak 1.1.1 callback signature: `callback(characteristic, value)` (not the old 2-arg `handle, value`)
- `on_disconnect` suppresses auto-reconnect via `_intentional_disconnect` (explicit disconnect) and `_cache_reset_in_progress` (during bluetooth reset)
- MQTT topics: `bedjet/<mac>/hvac-mode/set`, `bedjet/<mac>/target-temperature/set`, etc.
- Heartbeat: `bedjet/heartbeat` with JSON `{"ts": ..., "bedjets_connected": N}`

## Known quirks

- `bedjet.py:52` assigns `self.is_connected = BleakClient.is_connected` which goes through the setter and sets available='online' at construction. Pre-existing, harmless at runtime.
- BlueZ adapter-level GATT cache (`/var/lib/bluetooth/<adapter>/`) can corrupt, causing zero GATT services discovered. The service auto-detects and recovers by running `reset_bluetooth.sh` via sudo.
- The BedJet only exposes its custom GATT service when actively running (not in standby), but basic service discovery still works in standby.

## Testing

No test suite. Test on the Pi by running `diagnose.py` (stop the service first) or by watching logs during operation.

## Workflow — MANDATORY

**ALL changes MUST be made in a git worktree branched off the latest `main`.** Never commit directly to `main`. This is non-negotiable. When using the Agent tool, always set `isolation: "worktree"`. When working manually, create a worktree first. No exceptions.
