import asyncio
from bleak import BleakScanner
import logging

logging.getLogger().setLevel(logging.INFO)


async def main():
    devices = await BleakScanner.discover()
    logging.info(devices)

asyncio.run(main())
