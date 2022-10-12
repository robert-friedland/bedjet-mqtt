from binascii import hexlify
import paho.mqtt.client as mqtt
from bedjet import BedJet, BEDJET_COMMANDS
import sys
from config import MQTT, MAC_ADDRESSES
import asyncio

client = mqtt.Client()
client.username_pw_set(username=MQTT['user'], password=MQTT['password'])
client.connect(MQTT['host'], MQTT['port'], 60)
client.subscribe("bedjet/#")

bedjets = {}
for mac in MAC_ADDRESSES:
    bedjet = BedJet(mac)
    bedjets[mac] = bedjet


def on_message(client, userdata, message):
    print(message)
    splittopic = message.topic.split('/')
    mac = splittopic[1]
    command_type = splittopic[2]
    command_value = message.payload

    bedjet = bedjets[mac]

    if command_type == 'setmode':
        bedjet.set_mode(BEDJET_COMMANDS(command_value))

    if command_type == 'set_temp':
        bedjet.set_temp(command_value)

    if command_type == 'set_fan':
        bedjet.set_fan_mode(command_value)


client.on_message = on_message


async def main():
    try:
        for mac, bedjet in bedjets.items():
            await bedjet.connect()
            await bedjet.subscribe()
        print('running')
        client.loop_forever()
    except KeyboardInterrupt:
        sys.exit(0)

asyncio.run(main())
