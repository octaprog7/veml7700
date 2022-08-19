# micropython
# MIT license
# Copyright (c) 2022 Roman Shevchik   goctaprog@gmail.com

import micropython
from sensor_pack import bus_service
from sensor_pack.base_sensor import BaseSensor, Iterator


@micropython.native
def _check_value(value: int, valid_range, error_msg: str) -> int:
    if value not in valid_range:
        raise ValueError(error_msg)
    return value


class Veml7700(BaseSensor, Iterator):
    """Class for work with ambient Light Sensor VEML7700"""
    _GAIN = 1, 2, 0.125, 0.25

    def __init__(self, adapter: bus_service.I2cAdapter, address: int = 0x10):
        """  """
        super().__init__(adapter, address)
        self.als_gain = 0       # gain
        self.als_raw_gain = 0   # raw gain
        self.als_it = 0         # integration time
        self.als_pers = 0       # persistence protect number setting
        self.als_int_en = False     # interrupt enable setting
        self.als_shutdown = False  # ALS shut down setting

    def _read_register(self, reg_addr, bytes_count=2) -> bytes:
        """считывает из регистра датчика значение.
        bytes_count - размер значения в байтах"""
        return self.adapter.read_register(self.address, reg_addr, bytes_count)

    def _write_register(self, reg_addr, value: int, bytes_count=2) -> int:
        """записывает данные value в датчик, по адресу reg_addr.
        bytes_count - кол-во записываемых данных"""
        if self.is_big_byteorder():
            byte_order = 'big'
        else:
            byte_order = 'little'
        return self.adapter.write_register(self.address, reg_addr, value, bytes_count, byte_order)

    def set_config_als(self, gain: int, integration_time: int, persistence: int,
                       interrupt_enable: bool, shutdown: bool):
        """Установка параметров Датчика Внешней Освещенности (ДВО - ALS).
        Setting Ambient Light Sensor (ALS) parameters.
        gain = 0..3; 0-gain=1, 1-gain=2, 2-gain=0.125, 3-gain=0.25.
        integration_time = 0..5; 0-25 ms; 1-50 ms; 2-100 ms, 3-200 ms, 4-400 ms, 5-800 ms
        persistence protect number = 0..3; 0-1, 1-2, 2-4, 3-8
        """
        _cfg = 0
        gain = _check_value(gain, range(4), f"Invalid als gain value: {gain}")
        _tmp = _check_value(integration_time, range(6), f"Invalid als integration_time: {integration_time}")
        _t_it = 12, 8, 0, 1, 2, 3
        it = _t_it[_tmp]    # integration_time
        pers = _check_value(persistence, range(4), f"Invalid als persistence protect number: {persistence}")
        ie = 0
        if interrupt_enable:
            ie = 1
        sd = 0
        if shutdown:
            sd = 1
        #
        _cfg |= sd
        _cfg |= ie << 1
        _cfg |= pers << 4
        _cfg |= it << 6
        _cfg |= gain << 11

        self._write_register(0x00, _cfg, 2)

        self.als_raw_gain = gain

    def get_config_als(self) -> None:
        """read ALS config from register (2 byte)"""
        reg_val = self._read_register(0x00, 2)
        cfg = self.unpack("H", reg_val)[0]  # unsigned short
        #
        tmp = (cfg & 0b0001_1000_0000_0000) >> 11  # gain
        if tmp < 2:
            self.als_gain = 1 + tmp
        else:
            self.als_gain = 0.125 * (tmp - 1)

        tmp = (cfg & 0b0000_0011_1100_0000) >> 6  # integration time setting
        if tmp not in (0, 1, 2, 3, 8, 12):
            raise ValueError("Invalid value ALS_IT from config register #0: {tmp}")
        if tmp < 4:
            self.als_it = 100 * 2 ** tmp
        else:
            if tmp == 0x08:
                self.als_it = 50
            if tmp == 12:
                self.als_it = 25

        tmp = (cfg & 0b0000_0000_0011_0000) >> 4  # persistence protect number setting
        self.als_pers = 2**tmp
        #
        self.als_int_en = (cfg & 0b0000_0000_0000_0010) >> 1
        self.als_shutdown = cfg & 0b0000_0000_0000_0001

    def set_power_save_mode(self, enable_psm: bool, psm: int) -> None:
        """Set power save mode for sensor.
        enable_psm (Power saving mode enable): False - disable, True - enable
        psm (Power saving mode; see table “Refresh time”): 0, 1, 2, 3
        """
        psm = _check_value(psm, range(4), f"Invalid power save mode value: {psm}")
        reg_val = 0
        reg_val |= int(enable_psm)
        reg_val |= psm << 1
        self._write_register(0x03, reg_val, 2)

    def get_interrupt_status(self) -> tuple:
        reg_val = self._read_register(0x06, 2)
        irq_status = self.unpack("H", reg_val)[0]  # unsigned short
        # Bit 15 defines interrupt flag while trigger occurred due to data crossing low threshold windows.
        int_th_low = bool(irq_status & 0b1000_0000_0000_0000)
        # Bit 14 defines interrupt flag while trigger occurred due to data crossing high threshold windows.
        int_th_high = bool(irq_status & 0b0100_0000_0000_0000)
        return int_th_low, int_th_high

    def get_illumination(self):
        """return illumination in lux"""
        reg_val = self._read_register(0x04, 2)
        raw = self.als_raw_gain
        return self.unpack("H", reg_val)[0] / Veml7700._GAIN[raw]

    def get_white_channel(self):
        """Return white channel output data"""
        reg_val = self._read_register(0x05, 2)
        return self.unpack("H", reg_val)[0]

    def get_id(self):
        """No ID support in sensor!"""
        return None

    def soft_reset(self):
        """Software reset."""
        return None

    def __next__(self) -> float:
        return self.get_illumination()
