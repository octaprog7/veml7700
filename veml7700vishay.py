# micropython
# MIT license
# Copyright (c) 2022 Roman Shevchik   goctaprog@gmail.com

from sensor_pack.base_sensor import BaseSensor, Iterator
import sys
import ustruct


class Veml7700(BaseSensor, Iterator):
    """Class for work with ambient Light Sensor BH1750"""
    def get_id(self):
        """No ID support in sensor!"""
        return None

    def soft_reset(self):
        """Software reset."""
        pass

    def __next__(self) -> int:
        pass



