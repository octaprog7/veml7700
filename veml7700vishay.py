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
    """Class for work with ambient Light Sensor VEML7700.
    Please read: https://www.vishay.com/docs/84286/veml7700.pdf"""
    _IT = 12, 8, 0, 1, 2, 3     # integration time const

    @staticmethod
    def _it_to_raw_it(it: int) -> int:
        """Возвращает сырое значение времени интегрирования (для битового поля в регистре),
        соответствующее it - integration_time.
        Спасибо вам, разработчики, за дополнительные трудности!
        it                  return_value    integration_time_ms
        0                   12              25
        1                   8               50
        2                   0               100
        3                   1               200
        4                   2               400
        5                   3               800
        """
        return Veml7700._IT[it]

    @staticmethod
    def _raw_it_to_it(raw_it: int) -> int:
        """Метод обратный методу _it_to_raw_it"""
        return Veml7700._IT.index(raw_it)

    @staticmethod
    def _get_integration_time(raw_it: int) -> int:
        """Возвращает время интегрирования, в миллисекундах, по сырому значению raw_it (0..5)"""
        return 25 * 2 ** raw_it

    @staticmethod
    def _raw_gain_to_gain(raw_gain: int) -> float:
        """Преобразует сырое значение усиления (0..3) в коэффициент усиления"""
        _g = 1, 2, 0.125, 0.25
        return _g[raw_gain]

    @staticmethod
    def _check_gain(_gain: float) -> float:
        """Проверяет коэффициент усиления на правильность"""
        _gains = 0.125, 0.25, 1, 2
        if not _gain in _gains:
            raise ValueError(f"Invalid _gain value: {_gain}")
        return _gain

    @staticmethod
    def _check_raw(raw_gain: int, raw_it: int):
        _check_value(raw_gain, range(4), f"Invalid als gain value: {raw_gain}")
        _check_value(raw_it, range(6), f"Invalid als raw integration_time: {raw_it}")

    @staticmethod
    def get_max_possible_illumination(raw_gain: int, raw_it: int) -> float:
        """Возвращает максимально возможный уровень освещенности в lux в
        зависимости от сырого значения усиления (raw_gain 0..3) и времени интегрирования (сырое значение 0..5) """
        Veml7700._check_raw(raw_gain, raw_it)
        #
        _gain = Veml7700._raw_gain_to_gain(raw_gain)
        _g_base = 0.125
        _max_ill = 120796
        _k = _gain / _g_base
        return (_max_ill / 2 ** raw_it) / _k

    @staticmethod
    def _get_resolution(raw_gain: int, raw_it: int) -> float:
        """Возвращает разрешение младшего разряда в [lux] по сырому значению усиления (gain 0..3) и
        по it_raw (сырые значения) 0..5"""
        Veml7700._check_raw(raw_gain, raw_it)
        #
        _gain = Veml7700._raw_gain_to_gain(raw_gain)
        _g_base = 0.125
        _max_res = 1.8432
        _k = _gain / _g_base
        return (_max_res / 2 ** raw_it) / _k

    def __init__(self, adapter: bus_service.I2cAdapter, address: int = 0x10):
        """  """
        super().__init__(adapter, address, False)
        self._last_raw_ill =None    # хранит последнее, считанное из датчика, сырое значение освещенности
        self._als_gain = 0           # gain
        self._als_it = 0             # integration time
        self._als_pers = 0           # persistence protect number setting
        self._als_int_en = False     # interrupt enable setting
        self._als_shutdown = False   # ALS shut down setting
        self._enable_psm = False     # Enable power save mode for sensor
        self._psm = 0                # power save mode for sensor 0..3

    def _read_register(self, reg_addr, bytes_count=2) -> bytes:
        """считывает из регистра датчика значение.
        bytes_count - размер значения в байтах"""
        return self.adapter.read_register(self.address, reg_addr, bytes_count)

    def _write_register(self, reg_addr, value: int, bytes_count=2) -> int:
        """записывает данные value в датчик, по адресу reg_addr.
        bytes_count - кол-во записываемых данных"""
        byte_order = self._get_byteorder_as_str()[0]
        return self.adapter.write_register(self.address, reg_addr, value, bytes_count, byte_order)

    def set_config_als(self, gain: int, integration_time: int, persistence: int = 1,
                       interrupt_enable: bool = False, shutdown: bool = False):
        """Установка параметров Датчика Внешней Освещенности (ДВО - ALS).
        Setting Ambient Light Sensor (ALS) parameters.
        gain = 0..3; 0-gain=1, 1-gain=2, 2-gain=0.125(1/8), 3-gain=0.25(1/4).
        integration_time = 0..5; 0-25 ms; 1-50 ms; 2-100 ms, 3-200 ms, 4-400 ms, 5-800 ms
        persistence protect number = 0..3; 0-1, 1-2, 2-4, 3-8
        """
        _cfg = 0
        # перед любой перенастройкой, документация требует перевода датчика в режим ожидания
        _bts = self._read_register(0x00, 2) # читаю
        _cfg = self.unpack("H", _bts)[0]
        self._write_register(0x00, _cfg | 0x01, 2)  # записываю

        _cfg = 0
        gain = _check_value(gain, range(4), f"Invalid als gain value: {gain}")
        _tmp = _check_value(integration_time, range(6), f"Invalid als integration_time: {integration_time}")
        it = Veml7700._it_to_raw_it(_tmp)    # integration_time

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
        # save
        self._als_gain = gain
        self._als_it = integration_time
        self._als_pers = pers
        self._als_int_en = interrupt_enable
        self._als_shutdown = shutdown

    def get_config_als(self) -> None:
        """read ALS config from register (2 byte)"""
        reg_val = self._read_register(0x00, 2)
        cfg = self.unpack("H", reg_val)[0]  # unsigned short
        #
        tmp = (cfg & 0b0001_1000_0000_0000) >> 11  # gain
        self._als_gain = tmp

        tmp = (cfg & 0b0000_0011_1100_0000) >> 6  # integration time setting
        self._als_it = Veml7700._raw_it_to_it(tmp)

        tmp = (cfg & 0b0000_0000_0011_0000) >> 4  # persistence protect number setting
        self._als_pers = tmp     # 2 ** tmp
        #
        self._als_int_en = bool(cfg & 0b0000_0000_0000_0010)
        self._als_shutdown = bool(cfg & 0b0000_0000_0000_0001)

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
        self._enable_psm = enable_psm
        self._psm = psm

    def get_interrupt_status(self) -> tuple:
        """Return interrupt flags while trigger occurred due to data crossing low/high threshold windows.
        tuple (low_threshold, high_threshold)."""
        reg_val = self._read_register(0x06, 2)
        irq_status = self.unpack("H", reg_val)[0]  # unsigned short
        # Bit 15 defines interrupt flag while trigger occurred due to data crossing low threshold windows.
        int_th_low = bool(irq_status & 0b1000_0000_0000_0000)
        # Bit 14 defines interrupt flag while trigger occurred due to data crossing high threshold windows.
        int_th_high = bool(irq_status & 0b0100_0000_0000_0000)
        return int_th_low, int_th_high

    def get_illumination(self, raw = False) -> [int, float]:
        """return illumination in lux"""
        reg_val = self._read_register(0x04, 2)
        raw_lux = self.unpack("H", reg_val)[0]
        self._last_raw_ill = raw_lux
        if raw:
            return raw_lux
        return raw_lux * Veml7700._get_resolution(self._als_gain, self._als_it)

    def get_white_channel(self):
        """Return white channel output data"""
        reg_val = self._read_register(0x05, 2)
        return self.unpack("H", reg_val)[0]

    def get_high_threshold(self) -> int:
        """Return ALS high threshold window setting"""
        reg_val = self._read_register(0x01, 2)
        return self.unpack("H", reg_val)[0]

    def get_low_threshold(self) -> int:
        """Return ALS low threshold window setting"""
        reg_val = self._read_register(0x02, 2)
        return self.unpack("H", reg_val)[0]

    def get_id(self):
        """No ID support in sensor!"""
        return None

    def soft_reset(self):
        """Software reset."""
        return None

    @property
    def last_raw(self)->int:
        """Возвращает последнее, считанное из датчика, сырое значение освещенности"""
        return self._last_raw_ill

    def __next__(self) -> float:
        return self.get_illumination(raw=False)

    @micropython.native
    # def get_conversion_cycle_time(integration_time: int, power_save_enable: bool, power_save_mode: int) -> int:
    def get_conversion_cycle_time(self, offset: int = 100) -> int:
        """Return conversion cycle time in [ms].
        Without using the power-saving feature (PSM_EN = 0), the controller has to wait before reading out
        measurement results, at least for the programmed integration time. For example, for ALS_IT = 100 ms a wait time
        of ≥ 100 ms is needed. A more simple way of continuous measurements can be realized by activating the PSM feature,
        setting PSM_EN = 1."""
        base = 25 * 2 ** self._als_it
        if not self._enable_psm:
            return base
        # весь код ниже этой строки в этой функции под вопросом. документация на Veml7700
        # не позволяет мне понять алгоритм вычисления времени преобразования датчика при включенном режиме
        # экономии электроэнергии (power save mode)!
        return offset + base + 500 * (2 ** self._psm)

    @property
    def gain(self) -> tuple[int, float]:
        """Возвращает коэффициент усиления (raw_gain, gain)"""
        rg = self._als_gain
        return rg, Veml7700._raw_gain_to_gain(rg)

    @property
    def integration_time(self) -> tuple[int, int]:
        """Возвращает время интегрирования (raw_integration_time, integration_time_ms)"""
        rit = self._als_it
        return rit, self._get_integration_time(rit)