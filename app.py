from asyncio_mqtt import Client, MqttError
from bedjet import BedJet
import sys
from config import MQTT, MAC_ADDRESSES
import asyncio
from bleak import BleakError
import logging


async def run(bedjets):
    async with Client(
        MQTT['host'],
        username=MQTT['username'],
        password=MQTT['password']
    ) as client:
        for mac, bedjet in bedjets.items():
            bedjet.mqtt_client = client

        async with client.filtered_messages('bedjet/+/+/set') as messages:
            await client.subscribe('bedjet/#')
            async for message in messages:
                splittopic = message.topic.split('/')
                mac = splittopic[1]
                command_type = splittopic[2]
                command_value = message.payload.decode()
                bedjet = bedjets[mac]

                if command_type == 'hvac-mode':
                    await bedjet.set_hvac_mode(command_value)

                if command_type == 'target-temperature':
                    await bedjet.set_temperature(command_value)

                if command_type == 'fan-mode':
                    await bedjet.set_fan_mode(command_value)


async def connect_bedjets():
    bedjets = {}
    reconnect_interval = 3
    for mac in MAC_ADDRESSES:
        bedjet = BedJet(mac, mqtt_topic=f'bedjet/{mac}')
        bedjets[mac] = bedjet

        while True:
            try:
                await bedjet.connect()
                break
            except BleakError as error:
                logging.error(
                    f'Error "{error}". Retrying in {reconnect_interval} seconds.')
            finally:
                await asyncio.sleep(reconnect_interval)

        await bedjet.subscribe()

    return bedjets


async def main():
    reconnect_interval = 3
    bedjets = await connect_bedjets()
    while True:
        try:
            await run(bedjets)
        except MqttError as error:
            logging.error(
                f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
        except KeyboardInterrupt:
            sys.exit(0)
        finally:
            await asyncio.sleep(reconnect_interval)


asyncio.run(main())
