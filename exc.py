class BleakError(Exception):
    pass


class BleakDeviceNotFoundError(BleakError):
    pass


class BleakDBusError(BleakError):
    pass
