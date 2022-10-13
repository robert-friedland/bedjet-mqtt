from binascii import hexlify
from asyncio_mqtt import Client, MqttError
from bedjet import BedJet, BEDJET_COMMANDS
import sys
from config import MQTT, MAC_ADDRESSES
import asyncio


async def run():
    async with Client(
        MQTT['host'],
        username=MQTT['username'],
        password=MQTT['password']
    ) as client:
        bedjets = {}
        for mac in MAC_ADDRESSES:
            bedjet = BedJet(mac, client, f'bedjet/{mac}')
            bedjets[mac] = bedjet
            await bedjet.connect()
            await bedjet.subscribe()

        async with client.filtered_messages('bedjet/+/+/set') as messages:
            await client.subscribe('bedjet/#')
            async for message in messages:
                splittopic = message.topic.split('/')
                mac = splittopic[1]
                command_type = splittopic[2]
                command_value = message.payload.decode()
                bedjet = bedjets[mac]

                if command_type == 'hvac-mode':
                    await bedjet.set_mode(BEDJET_COMMANDS.get(command_value))

                if command_type == 'target-temperature':
                    await bedjet.set_temperature(command_value)

                if command_type == 'fan-mode':
                    await bedjet.set_fan_mode(command_value)


async def main():
    reconnect_interval = 3
    while True:
        try:
            await run()
        except MqttError as error:
            print(
                f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
        except KeyboardInterrupt:
            sys.exit(0)
        finally:
            await asyncio.sleep(reconnect_interval)

asyncio.run(main())
