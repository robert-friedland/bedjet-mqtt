from binascii import hexlify
from asyncio_mqtt import Client, MqttError
from bedjet import BedJet, BEDJET_COMMANDS
import sys
from config import MQTT, MAC_ADDRESSES
import asyncio


async def test():
    bedjets = {}
    for mac in MAC_ADDRESSES:
        bedjet = BedJet(mac)
        bedjets[mac] = bedjet
        await bedjet.connect()
        await bedjet.subscribe()

    async with Client(
        MQTT['host'],
        username=MQTT['username'],
        password=MQTT['password']
    ) as client:
        async with client.filtered_messages('bedjet/#') as messages:
            await client.subscribe('bedjet/#')
            async for message in messages:
                print(message)
                splittopic = message.topic.split('/')
                mac = splittopic[1]
                command_type = splittopic[2]
                command_value = message.payload
                bedjet = bedjets[mac]

                if command_type == 'setmode':
                    await bedjet.set_mode(BEDJET_COMMANDS.get(command_value))

                if command_type == 'set_temp':
                    await bedjet.set_temp(command_value)

                if command_type == 'set_fan':
                    await bedjet.set_fan_mode(command_value)

# client = mqtt.Client()
# client.username_pw_set(username=MQTT['user'], password=MQTT['password'])
# client.connect(MQTT['host'], MQTT['port'], 60)
# client.subscribe("bedjet/#")


# async def on_message(client, userdata, message):
#     print(message)
#     splittopic = message.topic.split('/')
#     mac = splittopic[1]
#     command_type = splittopic[2]
#     command_value = message.payload

#     bedjet = bedjets[mac]

#     if command_type == 'setmode':
#         await bedjet.set_mode(BEDJET_COMMANDS.get(command_value))

#     if command_type == 'set_temp':
#         await bedjet.set_temp(command_value)

#     if command_type == 'set_fan':
#         await bedjet.set_fan_mode(command_value)


# client.on_message = on_message


async def main():
    reconnect_interval = 3
    while True:
        try:
            await test()
        except MqttError as error:
            print(
                f'Error "{error}". Reconnecting in {reconnect_interval} seconds.')
        finally:
            await asyncio.sleep(reconnect_interval)

    # try:
    #     for mac, bedjet in bedjets.items():
    #         await bedjet.connect()
    #         await bedjet.subscribe()
    #     print('running')
    #     client.loop_forever()
    # except KeyboardInterrupt:
    #     sys.exit(0)

asyncio.run(main())
