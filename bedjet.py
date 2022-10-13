import asyncio
from bleak import BleakClient
from const import BEDJET_COMMAND_UUID, BEDJET_SUBSCRIPTION_UUID, BEDJET_COMMANDS


class BedJet():
    def __init__(self, mac):
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

    def handle_data(self, handle, value):
        self.current_temperature = round(
            ((int(value[7]) - 0x26) + 66) - ((int(value[7]) - 0x26) / 9))
        self.target_temperature = round(
            ((int(value[8]) - 0x26) + 66) - ((int(value[8]) - 0x26) / 9))
        self.time = (int(value[4]) * 60 * 60) + \
            (int(value[5]) * 60) + int(value[6])
        self.timestring = str(int(value[4])) + ":" + \
            str(int(value[5])) + ":" + str(int(value[6]))
        self.fan_pct = int(value[10]) * 5
        if value[14] == 0x50 and value[13] == 0x14:
            self.hvac_mode = "off"
            self.preset_mode = "off"
        if value[14] == 0x34:
            self.hvac_mode = "cool"
            self.preset_mode = "cool"
        if value[14] == 0x56:
            self.hvac_mode = "heat"
            self.preset_mode = "turbo"
        if value[14] == 0x50 and value[13] == 0x2d:
            self.hvac_mode = "heat"
            self.preset_mode = "heat"
        if value[14] == 0x3e:
            self.hvac_mode = "dry"
            self.preset_mode = "dry"
        if value[14] == 0x43:
            self.hvac_mode = "heat"
            self.preset_mode = "ext_ht"

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
        elif fan_mode == 'FAN_MIN':
            fan_pct = 10
        elif fan_mode == 'FAN_LOW':
            fan_pct = 25
        elif fan_mode == 'FAN_MEDIUM':
            fan_pct = 50
        elif fan_mode == 'FAN_HIGH':
            fan_pct = 75
        elif fan_mode == 'FAN_MAX':
            fan_pct = 100

        if not (fan_pct >= 0 and fan_pct <= 100):
            return

        await self.send_command([0x07, round(fan_pct/5)-1])

    async def set_temperature(self, temperature):
        temp = int(temperature)
        temp_byte = (int((temp - 60) / 9) + (temp - 66)) + 0x26
        await self.send_command([0x03, temp_byte])

    async def set_hvac_mode(self, hvac_mode):
        await self.set_mode(BEDJET_COMMANDS.get(hvac_mode))
        await self.set_time(600)

    async def set_preset_mode(self, preset_mode):
        await self.set_mode(BEDJET_COMMANDS.get(preset_mode))
