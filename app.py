from asyncio_mqtt import Client, MqttError
from bedjet import BedJet
from config import MQTT
import asyncio
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
                bedjet = bedjets.get(mac)

                if not bedjet:
                    continue

                if command_type == 'hvac-mode':
                    await bedjet.set_hvac_mode(command_value)

                if command_type == 'target-temperature':
                    await bedjet.set_temperature(command_value)

                if command_type == 'fan-mode':
                    await bedjet.set_fan_mode(command_value)


async def connect_bedjets():
    bedjets = {}
    bedjet_arr = await BedJet.discover()
    for bedjet in bedjet_arr:
        bedjets[bedjet.mac] = bedjet
        bedjet.mqtt_topic = f'bedjet/{bedjet.mac}'
        await bedjet.connect_and_subscribe()

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
        finally:
            await asyncio.sleep(reconnect_interval)


asyncio.run(main())
