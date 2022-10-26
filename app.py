from asyncio_mqtt import Client, MqttError
from bedjet import BedJet, Attribute, HVACMode, PresetMode, FanMode
from config import MQTT
import asyncio
import logging


async def run(bedjets):
    async with Client(
        MQTT['host'],
        username=MQTT['username'],
        password=MQTT['password']
    ) as client:
        for main_mqtt_topic, bedjet in bedjets.items():
            bedjet.mqtt_client = client

        async with client.filtered_messages(f'homeassistant/climate/+/+/set') as messages:
            await client.subscribe(f'homeassistant/#')
            async for message in messages:
                splittopic = message.topic.split('/')
                attribute_name = splittopic[len(splittopic) - 1]
                attribute = Attribute(attribute_name)
                command_value = message.payload.decode()

                mqtt_topic = '/'.join(splittopic[:2])
                logging.info(mqtt_topic)
                bedjet = bedjets.get(mqtt_topic)

                if not bedjet:
                    continue

                if attribute == Attribute.HVAC_MODE:
                    await bedjet.set_hvac_mode(HVACMode(command_value))

                if attribute == Attribute.PRESET_MODE:
                    await bedjet.set_preset_mode(PresetMode(command_value))

                if attribute == Attribute.TARGET_TEMPERATURE:
                    await bedjet.set_temperature(command_value)

                if attribute == Attribute.FAN_MODE:
                    await bedjet.set_temperature(command_value)


async def connect_bedjets():
    bedjets = {}
    bedjet_arr = await BedJet.discover()
    for bedjet in bedjet_arr:
        bedjets[bedjet.main_mqtt_topic] = bedjet
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
