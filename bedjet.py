from xml.dom.minidom import Attr
from bleak import BleakClient, BleakError, BleakScanner
from const import BEDJET_COMMAND_UUID, BEDJET_SUBSCRIPTION_UUID, BEDJET_COMMANDS, BEDJET_FAN_MODES
from datetime import datetime
import asyncio
import logging
import json
from enum import Enum
from helper import fan_pct_range

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter("(%(asctime)s) %(levelname)s:%(message)s",
                              "%Y-%m-%d %H:%M:%S")
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)


class Command(Enum):
    OFF = 0x01
    COOL = 0x02
    HEAT = 0x03
    TURBO = 0x04
    DRY = 0x05
    EXT_HT = 0x06
    FAN_UP = 0x10
    FAN_DOWN = 0x11
    TEMP_UP = 0x12
    TEMP_DOWN = 0x13
    M1 = 0x20
    M2 = 0x21
    M3 = 0x22


class HVACMode(Enum):
    OFF = "off"
    HEAT = "heat"
    COOL = "cool"
    DRY = "dry"
    TURBO = "heat"
    EXT_HT = "heat"

    @property
    def command(self):
        return Command[self.name].value


class PresetMode(Enum):
    OFF = "off"
    HEAT = "heat"
    COOL = "cool"
    DRY = "dry"
    TURBO = "turbo"
    EXT_HT = "ext_ht"

    @property
    def command(self):
        return Command[self.name].value


class FanMode(Enum):
    OFF = ("off", 0)
    MIN = ("min", 10)
    LOW = ("low", 25)
    MEDIUM = ("medium", 50)
    HIGH = ("high", 75)
    MAX = ("max", 100)

    @property
    def value(self):
        return self._value_[0]

    @property
    def fan_percentage(self):
        return self._value_[1]

    @staticmethod
    def lookup_by_percentage(fan_pct: int):
        if not fan_pct:
            return None

        for fm in FanMode:
            if fan_pct <= fm.fan_percentage:
                return fm

        return None

    @staticmethod
    def lookup_by_value(value: str):
        for fm in FanMode:
            if fm.value == value:
                return fm


class Attribute(Enum):
    CURRENT_TEMPERATURE = "current_temperature"
    TARGET_TEMPERATURE = "target_temperature"
    HVAC_MODE = "hvac_mode"
    PRESET_MODE = "preset_mode"
    FAN_MODE = "fan_mode"
    LAST_SEEN = "last_seen"
    AVAILABILITY = "availability"

    def state_topic(self, main_mqtt_topic: str) -> str:
        return f'{main_mqtt_topic}/{self.value}/state'

    def command_topic(self, main_mqtt_topic: str) -> str:
        return f'{main_mqtt_topic}/{self.value}/set'

    @staticmethod
    def config_topic(main_mqtt_topic: str) -> str:
        return f'{main_mqtt_topic}/config'


class Availability(Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class BedJet():
    @staticmethod
    async def discover():
        devices = await BleakScanner.discover()
        bedjet_devices = [
            device for device in devices if device.name == 'BEDJET_V3']
        return [BedJet(device) for device in bedjet_devices]

    def __init__(self, device, mqtt_client=None):
        self._attributes = {}
        self.mac: str = device.address.lower()

        self.client: BleakClient = BleakClient(
            device, disconnected_callback=self.on_disconnect)
        self.mqtt_client = mqtt_client

        self.availability: Availability = Availability.OFFLINE

    def publish_config(self):
        asyncio.create_task(self.publish_mqtt(
            Attribute.config_topic(self.main_mqtt_topic), json.dumps(self.config)))

    @property
    def config(self) -> dict:
        return {
            "unique_id": self.unique_id,
            "name": self.name,
            "modes": list(set([hm.value for hm in HVACMode])),
            "preset_modes": list(set([pm.value for pm in PresetMode])),
            "fan_modes": list(set([fm.value for fm in FanMode])),
            "min_temp": 66,
            "max_temp": 109,
            "mode_command_topic": Attribute.HVAC_MODE.command_topic(self.main_mqtt_topic),
            "mode_state_topic": Attribute.HVAC_MODE.state_topic(self.main_mqtt_topic),
            "preset_mode_command_topic": Attribute.PRESET_MODE.command_topic(self.main_mqtt_topic),
            "preset_mode_state_topic": Attribute.PRESET_MODE.state_topic(self.main_mqtt_topic),
            "current_temperature_topic": Attribute.CURRENT_TEMPERATURE.state_topic(self.main_mqtt_topic),
            "temperature_command_topic": Attribute.TARGET_TEMPERATURE.command_topic(self.main_mqtt_topic),
            "temperature_state_topic": Attribute.TARGET_TEMPERATURE.state_topic(self.main_mqtt_topic),
            "fan_mode_command_topic": Attribute.FAN_MODE.command_topic(self.main_mqtt_topic),
            "fan_mode_state_topic": Attribute.FAN_MODE.state_topic(self.main_mqtt_topic),
            "availability_topic": Attribute.AVAILABILITY.state_topic(self.main_mqtt_topic)
        }

    def publish_attribute_to_mqtt(self, attr: Attribute):
        topic = attr.value
        state = self.get_attribute(attr)

        if isinstance(state, datetime):
            state = state.isoformat()

        elif isinstance(state, Enum):
            state = state.value

        asyncio.create_task(self.publish_mqtt(topic, state))

    @ property
    def name(self):
        return f'BedJet {self.mac.replace(":", "_")}'

    @ property
    def unique_id(self):
        return f'bedjet_{self.mac.replace(":", "_")}'

    @ property
    def main_mqtt_topic(self):
        return f'bedjet/climate/{self.unique_id}'

    @ property
    def current_temperature(self) -> int:
        return self.get_attribute(Attribute.CURRENT_TEMPERATURE)

    @ property
    def target_temperature(self) -> int:
        return self.get_attribute(Attribute.TARGET_TEMPERATURE)

    @ property
    def hvac_mode(self) -> HVACMode:
        return self.get_attribute(Attribute.HVAC_MODE)

    @ property
    def preset_mode(self) -> PresetMode:
        return self.get_attribute(Attribute.PRESET_MODE)

    @ property
    def fan_mode(self) -> FanMode:
        return self.get_attribute(Attribute.FAN_MODE)

    @ property
    def fan_pct(self) -> int:
        return self._fan_pct

    @ property
    def last_seen(self) -> datetime:
        return self.get_attribute(Attribute.LAST_SEEN)

    @ property
    def availability(self) -> Availability:
        return self.get_attribute(Attribute.AVAILABILITY)

    @ availability.setter
    def availability(self, value: Availability):
        self.set_attribute(Attribute.AVAILABILITY, value)

    @ property
    def mqtt_client(self):
        return self._mqtt_client

    @ property
    def should_publish_to_mqtt(self):
        return self.mqtt_client

    def get_attribute(self, attr: Attribute):
        return self._attributes.get(attr)

    def set_attribute(self, attr: Attribute, value) -> bool:
        has_changed = self.get_attribute(attr) != value
        if not has_changed:
            return

        self._attributes[attr] = value

        if self.should_publish_to_mqtt:
            self.publish_attribute_to_mqtt(attr)

    @ current_temperature.setter
    def current_temperature(self, value: int):
        self.set_attribute(Attribute.CURRENT_TEMPERATURE, value)

    @ target_temperature.setter
    def target_temperature(self, value: int):
        self.set_attribute(Attribute.TARGET_TEMPERATURE, value)

    @ fan_pct.setter
    def fan_pct(self, value: int):
        self._fan_pct = value
        self.set_attribute(Attribute.FAN_MODE, FanMode.lookup_by_percentage(
            value))

    @ hvac_mode.setter
    def hvac_mode(self, value: HVACMode):
        self.set_attribute(Attribute.HVAC_MODE, value)

    @ preset_mode.setter
    def preset_mode(self, value: PresetMode):
        self.set_attribute(Attribute.PRESET_MODE, value)

    @ mqtt_client.setter
    def mqtt_client(self, value):
        self._mqtt_client = value
        self.publish_config()
        self.publish_all_attributes()

    def publish_all_attributes(self):
        for attr in self._attributes.keys():
            self.publish_attribute_to_mqtt(attr)

    @ last_seen.setter
    def last_seen(self, value: datetime):
        self.set_attribute(Attribute.LAST_SEEN, value)

    @ availability.setter
    def availability(self, value: Availability):
        self.set_attribute(Availability, value)

    async def connect(self, max_retries=10):
        reconnect_interval = 3

        if self.client.is_connected:
            logger.info(f'Already connected to {self.mac}.')
            return

        for i in range(0, max_retries):
            try:
                logger.info(f'Attempting to connect to {self.mac}.')
                await self.client.connect()

            except BleakError as error:
                backoff_seconds = (i+1) * reconnect_interval
                logger.error(
                    f'Error "{error}". Retrying in {backoff_seconds} seconds.')

                try:
                    logger.info(f'Attempting to disconnect from {self.mac}.')
                    await self.client.disconnect()
                except BleakError as error:
                    logger.error(f'Error "{error}".')
                await asyncio.sleep(backoff_seconds)

            if self.client.is_connected:
                logger.info(f'Connected to {self.mac}.')
                return

        if not self.client.is_connected:
            logger.error(
                f'Failed to connect to {self.mac} after {max_retries} attempts.')
            raise Exception(
                f'Failed to connect to {self.mac} after {max_retries} attempts.')

    async def connect_and_subscribe(self, max_retries=10):
        await self.connect(max_retries)
        await self.subscribe(max_retries)
        self.client.set_disconnected_callback(self.on_disconnect)
        self.availability = Availability.ONLINE

    def on_disconnect(self, client):
        self.client.set_disconnected_callback(None)
        self.availability = Availability.OFFLINE
        logger.warning(f'Disconnected from {self.mac}.')
        asyncio.create_task(self.connect_and_subscribe())

    def handle_data(self, handle, value):
        def get_current_temperature(value) -> int:
            return round(((int(value[7]) - 0x26) + 66) - ((int(value[7]) - 0x26) / 9))

        def get_target_temperature(value) -> int:
            return round(((int(value[8]) - 0x26) + 66) - ((int(value[8]) - 0x26) / 9))

        def get_time(value) -> int:
            return (int(value[4]) * 60 * 60) + (int(value[5]) * 60) + int(value[6])

        def get_timestring(value) -> str:
            return str(int(value[4])) + ":" + str(int(value[5])) + ":" + str(int(value[6]))

        def get_fan_pct(value) -> int:
            return int(value[10]) * 5

        def get_preset_mode(value) -> PresetMode:
            if value[14] == 0x50 and value[13] == 0x14:
                return PresetMode.OFF
            if value[14] == 0x34:
                return PresetMode.COOL
            if value[14] == 0x56:
                return PresetMode.TURBO
            if value[14] == 0x50 and value[13] == 0x2d:
                return PresetMode.HEAT
            if value[14] == 0x3e:
                return PresetMode.DRY
            if value[14] == 0x43:
                return PresetMode.EXT_HT

        def get_hvac_mode(value) -> HVACMode:
            return HVACMode[get_preset_mode(value).name]

        self.current_temperature = get_current_temperature(value)
        self.target_temperature = get_target_temperature(value)
        self.time = get_time(value)
        self.timestring = get_timestring(value)
        self.fan_pct = get_fan_pct(value)
        self.hvac_mode = get_hvac_mode(value)
        self.preset_mode = get_preset_mode(value)
        self.last_seen = datetime.now()

    async def publish_mqtt(self, topic, payload):
        await self.mqtt_client.publish(topic, payload=payload, qos=1, retain=True)

    async def subscribe(self, max_retries=10):
        reconnect_interval = 3
        is_subscribed = False
        if not self.client.is_connected:
            await self.connect()

        for i in range(0, max_retries):
            try:
                logger.info(
                    f'Attempting to subscribe to notifications from {self.mac} on {BEDJET_SUBSCRIPTION_UUID}.')
                await self._client.start_notify(
                    BEDJET_SUBSCRIPTION_UUID, callback=self.handle_data)
                is_subscribed = True
                logger.info(
                    f'Subscribed to {self.mac} on {BEDJET_SUBSCRIPTION_UUID}.')
                break
            except BleakError as error:
                backoff_seconds = (i+1) * reconnect_interval
                logger.error(
                    f'Error "{error}". Retrying in {backoff_seconds} seconds.')

                await asyncio.sleep(backoff_seconds)

        if not is_subscribed:
            logger.error(
                f'Failed to subscribe to {self.mac} on {BEDJET_SUBSCRIPTION_UUID} after {max_retries} attempts.')
            raise Exception(
                f'Failed to subscribe to {self.mac} on {BEDJET_SUBSCRIPTION_UUID} after {max_retries} attempts.')

    async def send_command(self, command):
        if self.is_connected:
            return await self._client.write_gatt_char(BEDJET_COMMAND_UUID, command)

    async def set_mode(self, mode):
        return await self.send_command([0x01, mode.command])

    async def set_time(self, minutes):
        return await self.send_command([0x02, minutes // 60, minutes % 60])

    async def set_fan_mode(self, fan_mode: str):
        if str(fan_mode).isnumeric():
            fan_pct = int(fan_mode)

        else:
            fan_pct = FanMode[fan_mode].fan_percentage

        if not (fan_pct >= 0 and fan_pct <= 100):
            return

        await self.send_command([0x07, round(fan_pct/5)-1])

    async def set_temperature(self, temperature):
        temp = round(float(temperature))
        temp_byte = (int((temp - 60) / 9) + (temp - 66)) + 0x26
        await self.send_command([0x03, temp_byte])

    async def set_hvac_mode(self, hvac_mode: HVACMode):
        await self.set_mode(hvac_mode)
        await self.set_time(600)

    async def set_preset_mode(self, preset_mode: PresetMode):
        await self.set_mode(preset_mode)
        await self.set_time(600)
