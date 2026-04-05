#!/usr/bin/env python3
"""List all BLE services and characteristics on the BedJet."""
import asyncio
from bleak import BleakClient, BleakScanner

BEDJET_NAME = 'BEDJET_V3'


async def main():
    devices = await BleakScanner.discover(timeout=10)
    bedjet = next((d for d in devices if d.name == BEDJET_NAME), None)
    if not bedjet:
        print('BedJet not found')
        return

    print(f'Found {bedjet.name} at {bedjet.address}')
    async with BleakClient(bedjet, timeout=15) as client:
        for service in client.services:
            print(f'\nService: {service.uuid}')
            for char in service.characteristics:
                print(f'  Char: {char.uuid}  props={char.properties}')


if __name__ == '__main__':
    asyncio.run(main())
