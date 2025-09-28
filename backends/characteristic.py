from aioble.client import ClientCharacteristic

# copied from aioble/client.py
_FLAG_READ = const(0x0002)
_FLAG_WRITE_NO_RESPONSE = const(0x0004)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)
_FLAG_INDICATE = const(0x0020)


class BleakGATTCharacteristic(object):
    def __init__(self, char: ClientCharacteristic):
        self._char = char
        self.handle = char._value_handle
        # translate to bleak properties
        self.properties = set()
        if char.properties & _FLAG_READ:
            self.properties.add('read')
        if char.properties & _FLAG_NOTIFY:
            self.properties.add('notify')
        if char.properties & _FLAG_WRITE_NO_RESPONSE:
            self.properties.add('write-without-response')
        elif char.properties & _FLAG_WRITE:
            self.properties.add('write')
        # todo _FLAG_INDICATE etc..

    def __getattr__(self, item):
        return getattr(self._char, item)
