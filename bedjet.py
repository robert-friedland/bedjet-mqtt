import string
from bleak import BleakClient
from const import BEDJET_COMMAND_UUID, BEDJET_SUBSCRIPTION_UUID, BEDJET_COMMANDS, BEDJET_FAN_MODES
from datetime import datetime
import asyncio
from typing import TypedDict, Union


class BedJetState(TypedDict):
    current_temperature: int
    target_temperature: int
    hvac_mode: str
    preset_mode: str
    time: str
    timestring: str
    fan_pct: int
    fan_mode: str
    last_seen: datetime
    available: str


class BedJet():
    def __init__(self, mac, mqtt_client=None, mqtt_topic=None):
        self._mac = mac

        self._state: BedJetState = BedJetState()

        self.current_temperature = None
        self.target_temperature = None
        self.hvac_mode = None
        self.preset_mode = None

        self.time = None
        self.timestring = None
        self.fan_pct = None

        self.last_seen = None
        self.is_connected = False

        self._client = BleakClient(
            mac, disconnected_callback=self.on_disconnect)
        self._mqtt_client = mqtt_client
        self._mqtt_topic = mqtt_topic

    def state_attr(self, attr: str) -> Union[int, str, datetime]:
        return self.state.get(attr)

    def set_state_attr(self, attr: str, value: Union[int, str, datetime]):
        if self.state_attr(attr) == value:
            return

        self._state[attr] = value

        if self.can_publish_state():
            self.publish_state(attr)

    def publish_state(self, attr):
        topic = attr.replace('_', '-')
        state = self.state(attr)

        if isinstance(state, datetime):
            state = state.isoformat()

        asyncio.create_task(self.publish_mqtt(topic, state))

    @property
    def can_publish_state(self):
        return self.mqtt_client and self.mqtt_topic

    @property
    def mac(self):
        return self._mac

    @property
    def state(self):
        return self._state

    @property
    def current_temperature(self) -> int:
        return self.state_attr('current_temperature')

    @property
    def target_temperature(self) -> int:
        return self.state_attr('target_temperature')

    @property
    def time(self) -> str:
        return self.state_attr('time')

    @property
    def timestring(self) -> str:
        return self.state_attr('timestring')

    @property
    def fan_pct(self) -> int:
        return self.state_attr('fan_pct')

    @property
    def hvac_mode(self) -> str:
        return self.state_attr('hvac_mode')

    @property
    def preset_mode(self) -> str:
        return self.state_attr('preset_mode')

    @property
    def client(self):
        return self._client

    @property
    def mqtt_client(self):
        return self._mqtt_client

    @property
    def mqtt_topic(self):
        return self._mqtt_topic

    @property
    def fan_mode(self) -> str:
        return self.state_attr('fan_mode')

    @property
    def last_seen(self) -> datetime:
        return self.state_attr('last_seen')

    @property
    def is_connected(self):
        return self.state_attr('available') == 'online'

    @current_temperature.setter
    def current_temperature(self, value: int):
        self.set_state_attr('current_temperature', value)

    @target_temperature.setter
    def target_temperature(self, value: int):
        self.set_state_attr('target_temperature', value)

    @time.setter
    def time(self, value: str):
        self.set_state_attr('time', value)

    @timestring.setter
    def timestring(self, value: str):
        self.set_state_attr('timestring', value)

    @fan_pct.setter
    def fan_pct(self, value: int):
        self.set_state_attr('fan_pct', value)
        self.set_state_attr('fan_mode', self.determine_fan_mode(value))

    def determine_fan_mode(self, fan_pct: int) -> str:
        fan_pct = fan_pct or 0
        for fan_mode, pct in BEDJET_FAN_MODES.items():
            if fan_pct <= pct:
                return fan_mode

    @hvac_mode.setter
    def hvac_mode(self, value: str):
        self.set_state_attr('hvac_mode', value)

    @preset_mode.setter
    def preset_mode(self, value: str):
        self.set_state_attr('preset_mode', value)

    @client.setter
    def client(self, value):
        self._client = value

    @last_seen.setter
    def last_seen(self, value: datetime):
        self.set_state_attr('last_seen', value)

    @is_connected.setter
    def is_connected(self, value: bool):
        self.set_state_attr('available', 'available' if value else 'offline')

    async def connect(self):
        await self._client.connect()
        self.is_connected = True

    def on_disconnect(self, client):
        self.is_connected = False
        asyncio.create_task(self.connect())

    def handle_data(self, handle, value):
        def get_current_temperature(value):
            return round(((int(value[7]) - 0x26) + 66) - ((int(value[7]) - 0x26) / 9))

        def get_target_temperature(value):
            return round(((int(value[8]) - 0x26) + 66) - ((int(value[8]) - 0x26) / 9))

        def get_time(value):
            return (int(value[4]) * 60 * 60) + (int(value[5]) * 60) + int(value[6])

        def get_timestring(value):
            return str(int(value[4])) + ":" + str(int(value[5])) + ":" + str(int(value[6]))

        def get_fan_pct(value):
            return int(value[10]) * 5

        def get_preset_mode(value):
            if value[14] == 0x50 and value[13] == 0x14:
                return "off"
            if value[14] == 0x34:
                return "cool"
            if value[14] == 0x56:
                return "turbo"
            if value[14] == 0x50 and value[13] == 0x2d:
                return "heat"
            if value[14] == 0x3e:
                return "dry"
            if value[14] == 0x43:
                return "ext_ht"

        def get_hvac_mode(value):
            PRESET_TO_HVAC = {
                'off': 'off',
                'cool': 'cool',
                'turbo': 'heat',
                'heat': 'heat',
                'dry': 'dry',
                'ext_ht': 'heat'
            }

            return PRESET_TO_HVAC[get_preset_mode(value)]

        self.current_temperature = get_current_temperature(value)
        self.target_temperature = get_target_temperature(value)
        self.time = get_time(value)
        self.timestring = get_timestring(value)
        self.fan_pct = get_fan_pct(value)
        self.hvac_mode = get_hvac_mode(value)
        self.preset_mode = get_preset_mode(value)
        self.last_seen = datetime.now()

    async def publish_mqtt(self, attribute, value):
        payload = value.encode() if not isinstance(value, int) else value
        await self.mqtt_client.publish(f'{self.mqtt_topic}/{attribute}/state', payload=payload, qos=1, retain=True)

    async def subscribe(self):
        return await self._client.start_notify(
            BEDJET_SUBSCRIPTION_UUID, callback=self.handle_data)

    async def send_command(self, command):
        if self.is_connected:
            return await self._client.write_gatt_char(BEDJET_COMMAND_UUID, command)

    async def set_mode(self, mode):
        return await self.send_command([0x01, mode])

    async def set_time(self, minutes):
        return await self.send_command([0x02, minutes // 60, minutes % 60])

    async def set_fan_mode(self, fan_mode):
        if str(fan_mode).isnumeric():
            fan_pct = int(fan_mode)
        else:
            fan_pct = BEDJET_FAN_MODES.get(fan_mode)

        if not (fan_pct >= 0 and fan_pct <= 100):
            return

        await self.send_command([0x07, round(fan_pct/5)-1])

    async def set_temperature(self, temperature):
        temp = round(float(temperature))
        temp_byte = (int((temp - 60) / 9) + (temp - 66)) + 0x26
        await self.send_command([0x03, temp_byte])

    async def set_hvac_mode(self, hvac_mode):
        await self.set_mode(BEDJET_COMMANDS.get(hvac_mode))
        await self.set_time(600)

    async def set_preset_mode(self, preset_mode):
        await self.set_mode(BEDJET_COMMANDS.get(preset_mode))
