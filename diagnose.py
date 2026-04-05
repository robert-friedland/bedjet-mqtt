#!/usr/bin/env python3
"""
Run on the Pi to diagnose BedJet BLE or MQTT connectivity issues.

Prerequisites: pip3 install bleak asyncio-mqtt  (or aiomqtt)

IMPORTANT: Stop the bedjet service first, otherwise BLE tests give false failures.
  $ sudo systemctl stop bedjet

Then run:
  $ python3 /home/pi/bedjet-mqtt/diagnose.py

Restart service when done:
  $ sudo systemctl start bedjet
"""
import asyncio
import subprocess
import sys
import logging

try:
    from asyncio_mqtt import Client, MqttError
except ImportError:
    try:
        from aiomqtt import Client, MqttError
    except ImportError:
        print("ERROR: Install mqtt library: pip3 install asyncio-mqtt")
        sys.exit(1)

try:
    from bleak import BleakScanner, BleakClient, BleakError
except ImportError:
    print("ERROR: Install bleak: pip3 install bleak")
    sys.exit(1)

try:
    from config import MQTT
except ModuleNotFoundError:
    print("ERROR: config.py not found. Copy sample_config.py to config.py and fill in your values.")
    sys.exit(1)

try:
    from const import BEDJET_SUBSCRIPTION_UUID
except ImportError:
    BEDJET_SUBSCRIPTION_UUID = '00002000-bed0-0080-aa55-4265644a6574'

logging.basicConfig(level=logging.WARNING)

BEDJET_NAME = 'BEDJET_V3'
NOTIFICATION_WAIT_SECS = 15
BLE_CONNECT_TIMEOUT = 15.0


def check_service_running():
    """Returns True if the bedjet systemd service is active."""
    result = subprocess.run(
        ['systemctl', 'is-active', '--quiet', 'bedjet'],
        capture_output=True
    )
    return result.returncode == 0


def check_bluetooth_adapter():
    print("\n[Bluetooth Adapter]")
    result = subprocess.run(
        ['systemctl', 'is-active', '--quiet', 'bluetooth'],
        capture_output=True
    )
    if result.returncode != 0:
        print("  FAIL - bluetoothd is not running")
        print("         Fix: sudo systemctl start bluetooth")
        return False

    # Check for rfkill blocks (rfkill may not be present on minimal images)
    try:
        rfkill = subprocess.run(['rfkill', 'list', 'bluetooth'], capture_output=True, text=True)
        if 'Soft blocked: yes' in rfkill.stdout or 'Hard blocked: yes' in rfkill.stdout:
            print("  FAIL - Bluetooth is rfkill-blocked")
            print("         Fix: sudo rfkill unblock bluetooth")
            return False
    except FileNotFoundError:
        pass  # rfkill not installed, skip the block check

    print("  OK  - bluetoothd running, no rfkill blocks detected")
    return True


async def check_mqtt():
    print("\n[MQTT]")
    try:
        port = MQTT.get('port', 1883)
        async with Client(
            MQTT['host'], port=port,
            username=MQTT['username'],
            password=MQTT['password']
        ) as client:
            await client.publish('bedjet/diagnostic', payload=b'ping', qos=1)
            print(f"  OK  - Connected to {MQTT['host']}:{port} and published test message")
            return True
    except MqttError as e:
        print(f"  FAIL - {e}")
        return False
    except Exception as e:
        print(f"  FAIL - Unexpected error: {e}")
        return False


async def check_ble_scan():
    print("\n[BLE Scan]")
    try:
        devices = await BleakScanner.discover(timeout=10)
        bedjets = [d for d in devices if d.name == BEDJET_NAME]
        if not bedjets:
            all_names = sorted(set(d.name for d in devices if d.name))
            print(f"  FAIL - No BEDJET_V3 found.")
            print(f"         Visible BLE devices: {all_names or '(none)'}")
            print(f"         Note: BLE scan results can be stale — re-run if uncertain.")
            return []
        for b in bedjets:
            print(f"  OK  - Found {b.name} at {b.address}")
        return bedjets
    except Exception as e:
        print(f"  FAIL - BLE scan error: {e}")
        return []


async def check_ble_connection(device):
    print(f"\n[BLE Connect + Notifications] ({device.address})")
    print(f"  NOTE: Ensure the BedJet is powered on and actively running (not standby).")
    received = []

    def on_notify(characteristic, value):
        received.append(value)

    try:
        async with BleakClient(device, timeout=BLE_CONNECT_TIMEOUT) as client:
            print(f"  OK  - Connected")
            await client.start_notify(BEDJET_SUBSCRIPTION_UUID, on_notify)
            print(f"  OK  - Subscribed to notifications, waiting {NOTIFICATION_WAIT_SECS}s...")
            await asyncio.sleep(NOTIFICATION_WAIT_SECS)
            if received:
                print(f"  OK  - Received {len(received)} notification(s). Last: {received[-1].hex()}")
                return True
            else:
                print(f"  FAIL - No notifications received in {NOTIFICATION_WAIT_SECS}s")
                return False
    except BleakError as e:
        print(f"  FAIL - {e}")
        return False
    except Exception as e:
        print(f"  FAIL - Unexpected error: {e}")
        return False


async def main():
    print("=" * 55)
    print("BedJet Diagnostic")
    print("=" * 55)

    print("\nRecent service errors:")
    print("  $ journalctl -u bedjet --since '1 hour ago' | grep -i 'error\\|fail\\|warn'")

    service_running = check_service_running()
    print()
    if service_running:
        print("WARNING: bedjet service is running!")
        print("  BLE tests will give FALSE failures while the service is active.")
        print("  Stop it first:  sudo systemctl stop bedjet")
        print("  Then re-run this script.")
        print()
        print("Continuing with MQTT test only...")
        mqtt_ok = await check_mqtt()
        bt_ok = bedjets = ble_ok = None
    else:
        print("bedjet service is stopped. (Good — no BLE conflicts.)")
        mqtt_ok = await check_mqtt()
        bt_ok = check_bluetooth_adapter()
        if bt_ok:
            bedjets = await check_ble_scan()
            ble_ok = False
            if bedjets:
                ble_ok = await check_ble_connection(bedjets[0])
        else:
            bedjets = ble_ok = None

    print("\n" + "=" * 55)
    print("Summary")
    print("=" * 55)
    if service_running:
        print("  (Partial results — stop bedjet service to run BLE tests)")
    print(f"  MQTT:              {'OK' if mqtt_ok else 'FAIL'}")
    if bt_ok is not None:
        print(f"  BT adapter:        {'OK' if bt_ok else 'FAIL'}")
    if bedjets is not None:
        print(f"  BLE scan:          {'OK - found BedJet' if bedjets else 'FAIL - not found'}")
    if ble_ok is not None:
        print(f"  BLE notifications: {'OK' if ble_ok else 'FAIL'}")

    print()
    if service_running:
        print("-> Stop the service and re-run:")
        print("   sudo systemctl stop bedjet && python3 diagnose.py")
    elif not bt_ok:
        print("-> Bluetooth adapter is the problem.")
        print("   sudo systemctl restart bluetooth")
        print("   sudo rfkill unblock bluetooth")
    elif not mqtt_ok:
        print("-> MQTT is the problem. Check broker host/port/credentials in config.py.")
    elif not bedjets:
        print("-> BedJet not visible over BLE. Is it powered on?")
        print("   sudo systemctl restart bluetooth")
        print("   Re-run this script. If still not found, try rebooting the Pi.")
    elif not ble_ok:
        print("-> BedJet found but BLE notifications failed.")
        print("   sudo systemctl restart bluetooth")
        print("   Re-run. If still failing, reboot the Pi.")
    elif mqtt_ok and ble_ok:
        print("-> Both MQTT and BLE work independently.")
        print("   The issue was app.py running with a dead BLE connection.")
        print("   Restart the service:")
        print("   sudo systemctl restart bedjet")
        print()
        print("   Watch logs to confirm recovery:")
        print("   journalctl -u bedjet -f")


if __name__ == '__main__':
    asyncio.run(main())
