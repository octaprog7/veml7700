# micropython
# MIT license
# Copyright (c) 2022 Roman Shevchik   goctaprog@gmail.com

from sensor_pack import bus_service
from sensor_pack.base_sensor import BaseSensor, Iterator
import sys
import ustruct


class Veml7700(BaseSensor, Iterator):
    """Class for work with ambient Light Sensor VEML7700"""

    def __init__(self, adapter: bus_service.I2cAdapter, address: int = 0x10):
        """  """
        super().__init__(adapter, address)
        # self.adapter = adapter

    def get_id(self):
        """No ID support in sensor!"""
        return None

    def soft_reset(self):
        """Software reset."""
        pass

    def __next__(self) -> int:
        pass



