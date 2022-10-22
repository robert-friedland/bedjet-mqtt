import asyncio
from bleak import BleakScanner
import logging

logging.getLogger().setLevel(logging.INFO)


async def main():
    stop_event = asyncio.Event()

    # TODO: add something that calls stop_event.set()

    def callback(device, advertising_data):
        # TODO: do something with incoming data
        logging.info(device)
        logging.info(advertising_data)

    async with BleakScanner(callback) as scanner:
        # Important! Wait for an event to trigger stop, otherwise scanner
        # will stop immediately.
        await stop_event.wait()

    # scanner stops when block exits

asyncio.run(main())
