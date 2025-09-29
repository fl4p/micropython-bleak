import asyncio

import aioble
from aioble import DeviceDisconnectedError
from aioble.client import ClientService, ClientCharacteristic
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.uuids import normalize_uuid_str

Char = BleakGATTCharacteristic


class BleakScanner():
    @staticmethod
    async def find_device_by_name(dev_name) -> BLEDevice | None:
        async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
            async for result in scanner:
                if result.name():
                    print('found ble device', result.device.addr, result.name())
                if result.name() == dev_name:
                    return BLEDevice(result)
        print('ble device not found', dev_name)


class Service():
    # todo change class name to Bleak...
    def __init__(self, service: ClientService, chars: list[Char]):
        self._service = service
        self.characteristics = chars

    def __getattr__(self, item):
        return getattr(self._service, item)


class ServiceCollection():
    def __init__(self, services: list[Service]):
        self.services = services

    def __iter__(self):
        return iter(self.services)

    def __getitem__(self, item):
        return self.services[item]

    def __len__(self):
        return len(self.services)

    def __contains__(self, item):
        return item in self.services

    def get_characteristic(self, uuid):
        uuid = normalize_uuid_str(uuid) if isinstance(uuid, str) else uuid
        for s in self.services:
            for c in s.characteristics:
                if c._char.uuid == uuid or c.handle == uuid:
                    return c


class BleakClient(object):

    def __init__(self, device: BLEDevice, disconnected_callback=None, services=None, **kwargs):
        self.device: BLEDevice = device
        self.callbacks = {}
        self.disconnected_callback = disconnected_callback
        self._services = None
        self._notify_task: asyncio.Task = None

    async def _discover_services(self):
        services = []
        service: ClientService
        # cannot use nested loops here (ValueError: Discovery in progress)
        async for service in self.device.aioble_connection.services():
            services.append(service)

        self._services = []
        print(' ')
        for service in services:
            print('discovered service', service.uuid)
            char: ClientCharacteristic
            chars: list[Char] = []
            async for char in service.characteristics():
                c = Char(char)
                print('   > char ', char.uuid, c.properties)
                chars.append(c)
            print(' ')
            self._services.append(Service(service, chars))

        return self._services

    @property
    def services(self):
        assert self._services is not None, "services not discovered"
        return ServiceCollection(self._services)

    async def get_services(self):
        if self._services is None:
            await self._discover_services()
        return self._services

    async def connect(self, timeout=10):
        print('connecting ble device', self.device.address)
        conn = await self.device.scan_result.device.connect(
            timeout_ms=timeout * 1000,
            scan_duration_ms=timeout * 1000)
        if self._services is None:
            await self._discover_services()
        assert self.is_connected
        print('connected', conn)

    async def disconnect(self):
        if self.device.aioble_connection:
            await self.device.aioble_connection.disconnect()
        print('disconnected')

    @property
    def is_connected(self):
        return (self.device.aioble_connection is not None) and self.device.aioble_connection.is_connected()

    async def start_notify(self, char, callback):
        # print('start notify', char, callback)
        # https://github.com/micropython/micropython-lib/blob/bdc4706cc700ae1c0a4520e252897bb0e03c327b/micropython/bluetooth/aioble/README.md#subscribe-to-a-characteristic-client
        char_ = self.services.get_characteristic(char)._char
        await char_.subscribe(notify=True)
        self.callbacks[char] = callback, char_

        if self._notify_task is None:
            self._notify_task = asyncio.create_task(self.notify_loop())

    async def notify_loop(self):
        char: ClientCharacteristic
        # print('notify loop running..')
        while self.is_connected and len(self.callbacks) > 0:
            for uuid, (cb, char) in self.callbacks.items():
                try:
                    data = await char.notified(2000)
                    # print('got notified data', uuid,len(data), data, cb)
                    # print('got notified data', uuid, len(data))
                    cb(char, data)
                except asyncio.TimeoutError:
                    pass
                except DeviceDisconnectedError:
                    break
        self.callbacks.clear()
        print('notify loop ended.')

    async def stop_notify(self, char):
        self.callbacks.pop(char, None)
        if not self.callbacks and self._notify_task:
            await asyncio.sleep(2200)  # gracefully let it complete
            if not self._notify_task.done():
                self._notify_task.cancel()
            self._notify_task = None

    async def write_gatt_char(self, _char, data, response):
        # print('ble write gatt char', _char, data, 'resp' if response else 'no-resp')  # TODO
        await self.services.get_characteristic(_char)._char.write(data, response)
        # https://docs.micropython.org/en/latest/library/bluetooth.html#bluetooth.BLE.gattc_write
