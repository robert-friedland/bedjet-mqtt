# bedjet-mqtt

Bridges a BedJet V3 over Bluetooth Low Energy to MQTT for Home Assistant.

## Setup

### Prerequisites

```bash
pip3 install bleak asyncio-mqtt
```

### Configuration

Copy `sample_config.py` to `config.py` and fill in your MQTT broker details and BedJet MAC address(es).

### Sudoers entry for automatic Bluetooth recovery

The service can automatically detect and recover from BlueZ GATT cache corruption (a known issue on Raspberry Pi). This requires passwordless sudo access to the `reset_bluetooth.sh` helper script:

```bash
chmod +x /home/pi/bedjet-mqtt/reset_bluetooth.sh
sudo bash -c 'echo "pi ALL=(root) NOPASSWD: /home/pi/bedjet-mqtt/reset_bluetooth.sh" > /etc/sudoers.d/bedjet-bluetooth-reset'
sudo chmod 440 /etc/sudoers.d/bedjet-bluetooth-reset
```

### Systemd service

```bash
sudo cp bedjet.service /etc/systemd/system/  # or create manually
sudo systemctl daemon-reload
sudo systemctl enable bedjet
sudo systemctl start bedjet
```

### MQTT Heartbeat

The service publishes to `bedjet/heartbeat` every 30 seconds with:

```json
{"ts": "2026-04-05T15:30:00+00:00", "bedjets_connected": 1}
```

Home Assistant sensor config:

```yaml
sensor:
    - name: "BedJet Pi Heartbeat"
      state_topic: "bedjet/heartbeat"
      value_template: "{{ value_json.ts }}"
      device_class: timestamp

    - name: "BedJet Pi BLE Connections"
      state_topic: "bedjet/heartbeat"
      value_template: "{{ value_json.bedjets_connected }}"
```

### Auto-update (optional)

`update.sh` can automatically pull the latest code from main and restart the service. Set it up with cron:

1. Allow passwordless sudo for service restart:

```bash
sudo bash -c 'echo "pi ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart bedjet" > /etc/sudoers.d/bedjet-update'
sudo chmod 440 /etc/sudoers.d/bedjet-update
```

2. Ensure git can pull without a password prompt (SSH key with no passphrase).

3. Add a cron job (checks every 15 minutes):

```bash
crontab -e
# Add:
*/15 * * * * /home/pi/bedjet-mqtt/update.sh >> /var/log/bedjet-update.log 2>&1
```

## Diagnostics

Run `diagnose.py` on the Pi to independently test MQTT and BLE connectivity:

```bash
sudo systemctl stop bedjet
python3 diagnose.py
sudo systemctl restart bedjet
```
