from bleak import BleakClient
from const import BEDJET_COMMAND_UUID, BEDJET_SUBSCRIPTION_UUID, BEDJET_COMMANDS, BEDJET_FAN_MODES
from datetime import datetime
import asyncio


class BedJet():
    def __init__(self, mac, mqtt_client, mqtt_topic):
        self._mac = mac

        self._current_temperature = None
        self._target_temperature = None
        self._last_seen = None
        self._hvac_mode = None
        self._preset_mode = None

        self._time = None
        self._timestring = None
        self._fan_pct = None

        self._last_seen = None
        self._is_connected = False

        self._client = BleakClient(
            mac, disconnected_callback=self.on_disconnect)
        self._mqtt_client = mqtt_client
        self._mqtt_topic = mqtt_topic

    @property
    def mac(self):
        return self._mac

    @property
    def current_temperature(self):
        return self._current_temperature

    @property
    def target_temperature(self):
        return self._target_temperature

    @property
    def time(self):
        return self._time

    @property
    def timestring(self):
        return self._timestring

    @property
    def fan_pct(self):
        return self._fan_pct

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def preset_mode(self):
        return self._preset_mode

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
    def fan_mode(self):
        fan_pct = self.fan_pct or 0

        for fan_mode, pct in BEDJET_FAN_MODES.items():
            if fan_pct <= pct:
                return fan_mode

    @property
    def last_seen(self):
        return self._last_seen

    @property
    def is_connected(self):
        return self._is_connected

    @current_temperature.setter
    def current_temperature(self, value):
        if self._current_temperature == value:
            return

        self._current_temperature = value
        asyncio.create_task(self.publish_mqtt(
            'current-temperature', self.current_temperature))

    @target_temperature.setter
    def target_temperature(self, value):
        if self._target_temperature == value:
            return

        self._target_temperature = value
        asyncio.create_task(self.publish_mqtt(
            'target-temperature', self.target_temperature))

    @time.setter
    def time(self, value):
        self._time = value

    @timestring.setter
    def timestring(self, value):
        self._timestring = value

    @fan_pct.setter
    def fan_pct(self, value):
        if self._fan_pct == value:
            return

        self._fan_pct = value
        asyncio.create_task(self.publish_mqtt(
            'fan-pct', self.fan_pct))
        asyncio.create_task(self.publish_mqtt(
            'fan-mode', self.fan_mode))

    @hvac_mode.setter
    def hvac_mode(self, value):
        if self._hvac_mode == value:
            return

        self._hvac_mode = value
        asyncio.create_task(self.publish_mqtt(
            'hvac-mode', self.hvac_mode))

    @preset_mode.setter
    def preset_mode(self, value):
        if self._preset_mode == value:
            return

        self._preset_mode = value
        asyncio.create_task(self.publish_mqtt(
            'preset-mode', self.preset_mode))

    @client.setter
    def client(self, value):
        self._client = value

    @last_seen.setter
    def last_seen(self, value):
        if self._last_seen == value:
            return

        self._last_seen = value
        asyncio.create_task(self.publish_mqtt(
            'last-seen', self.last_seen.isoformat()))

    @is_connected.setter
    def is_connected(self, value):
        if self._is_connected == value:
            return

        self._is_connected = value
        asyncio.create_task(self.publish_mqtt(
            'available', 'online' if self._is_connected else 'offline'))

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
