import asyncio
from bleak import BleakScanner
import logging

logging.getLogger().setLevel(logging.INFO)


async def main():
    devices = await BleakScanner.discover()
    for device in devices:
        logging.info(f'{device.address}: {device.name}')
        logging.info(device.details)

asyncio.run(main())
