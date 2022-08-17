# micropython
# MIT license
# Copyright (c) 2022 Roman Shevchik   goctaprog@gmail.com
from sensor_pack import bus_service


class BaseSensor:
    """Base sensor class"""

    def __init__(self, adapter: bus_service.BusAdapter, address: int, big_byte_order: bool):
        """Базовый класс Датчик. если big_byte_order равен True -> порядок байтов в регистрах «big»
        (Порядок от старшего к младшему), в противном случае порядок байтов в регистрах "little"
        (Порядок от младшего к старшему)

        Base sensor class. if big_byte_order is True -> register values byteorder is 'big'
        else register values byteorder is 'little' """
        self.adapter = adapter
        self.address = address
        self.byte_order = big_byte_order

    def get_id(self):
        raise NotImplementedError

    def soft_reset(self):
        raise NotImplementedError

    def get_byte_order(self) -> str:
        """Return byte order as string"""
        if self.byte_order:
            return "big"
        return "little"


class Iterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise NotImplementedError
