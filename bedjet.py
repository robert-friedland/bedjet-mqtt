import asyncio
from bleak import BleakClient
from const import BEDJET_COMMAND_UUID, BEDJET_SUBSCRIPTION_UUID, BEDJET_COMMANDS


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

        self._client = BleakClient(mac)
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
        if fan_pct <= 10:
            return 'min'
        if fan_pct <= 25:
            return 'low'
        if fan_pct <= 50:
            return 'medium'
        if fan_pct <= 75:
            return 'high'
        return 'max'

    @current_temperature.setter
    def current_temperature(self, value):
        self._current_temperature = value

    @target_temperature.setter
    def target_temperature(self, value):
        self._target_temperature = value

    @time.setter
    def time(self, value):
        self._time = value

    @timestring.setter
    def timestring(self, value):
        self._timestring = value

    @fan_pct.setter
    def fan_pct(self, value):
        self._fan_pct = value

    @hvac_mode.setter
    def hvac_mode(self, value):
        self._hvac_mode = value

    @preset_mode.setter
    def preset_mode(self, value):
        self._preset_mode = value

    @client.setter
    def client(self, value):
        self._client = value

    async def connect(self):
        return await self._client.connect()

    async def handle_data(self, handle, value):
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

            return PRESET_TO_HVAC[get_preset_mode(self, value)]

        self.current_temperature = get_current_temperature(value)
        self.target_temperature = get_target_temperature(value)
        self.time = get_time(value)
        self.timestring = get_timestring(value)
        self.fan_pct = get_fan_pct(value)
        self.hvac_mode = get_hvac_mode(value)
        self.preset_mode = get_preset_mode(value)

        await self.update_attributes()

    async def publish_mqtt(self, attribute, value):
        payload = value.encode() if not isinstance(value, int) else value
        await self.mqtt_client.publish(f'{self.mqtt_topic}/{attribute}/state', payload=payload)

    async def update_attributes(self):
        attributes = [
            {'topic': 'current-temperature', 'state': self.current_temperature},
            {'topic': 'target-temperature', 'state': self.target_temperature},
            {'topic': 'fan-pct', 'state': self.fan_pct},
            {'topic': 'fan-mode', 'state': self.fan_mode},
            {'topic': 'hvac-mode', 'state': self.hvac_mode},
            {'topic': 'preset-mode', 'state': self.preset_mode},
        ]

        for attribute in attributes:
            await self.publish_mqtt(attribute['topic'], attribute['state'])

    async def subscribe(self):
        return await self._client.start_notify(
            BEDJET_SUBSCRIPTION_UUID, callback=self.handle_data)

    async def send_command(self, command):
        return await self._client.write_gatt_char(BEDJET_COMMAND_UUID, command)

    async def set_mode(self, mode):
        return await self.send_command([0x01, mode])

    async def set_time(self, minutes):
        return await self.send_command([0x02, minutes // 60, minutes % 60])

    async def set_fan_mode(self, fan_mode):
        if str(fan_mode).isnumeric():
            fan_pct = int(fan_mode)
        elif fan_mode == 'min':
            fan_pct = 10
        elif fan_mode == 'low':
            fan_pct = 25
        elif fan_mode == 'medium':
            fan_pct = 50
        elif fan_mode == 'high':
            fan_pct = 75
        elif fan_mode == 'max':
            fan_pct = 100

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
