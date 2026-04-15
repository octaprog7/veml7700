# micropython
# MIT license
# Copyright (c) 2022 Roman Shevchik   goctaprog@gmail.com

import micropython
from micropython import const
# from collections import namedtuple
from sensor_pack_2 import bus_service
from sensor_pack_2.base_sensor import Iterator, IBaseSensorEx, DeviceEx, check_value

FMT_UINT16_LE = "H" # для правильной распаковки сырого значения в unsigned int 16 bit
# Базовая конфигурация для расчёта макс. освещённости (по таблице из AppNote)
_MAX_ILL_BASE = const(120796)   # лк при IT=25ms, gain=×1/8
_GAIN_BASE = const(0.125)        # базовый gain (×1/8)
# Базовое разрешение (наихудший случай): IT=25ms, gain=×1/8 (по таблице из AppNote)
_RESOLUTION_BASE = const(1.8432)  # [lx/ct]

class Veml7700(IBaseSensorEx, Iterator):
    """Class for work with ambient Light Sensor VEML7700.
    Please read: https://www.vishay.com/docs/84286/veml7700.pdf"""
    _IT = 12, 8, 0, 1, 2, 3     # integration time const
    ADDR_CFG_REG = const(0x00)
    #
    ADDR_HIGH_THRESHOLD_REG = const(0x01)
    ADDR_LOW_THRESHOLD_REG = const(0x02)
    ADDR_PWR_MODE_REG = const(0x03)
    ADDR_RAW_LUX_REG = const(0x04)
    ADDR_WH_CH_REG = const(0x05)
    ADDR_STATUS_REG = const(0x06)

    @staticmethod
    def _it_index_to_raw_it(it_index: int) -> int:
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
        return Veml7700._IT[it_index]

    @staticmethod
    def _raw_it_to_it(raw_it: int) -> int:
        """Метод обратный методу _it_to_raw_it"""
        return Veml7700._IT.index(raw_it)

    @staticmethod
    def _get_integration_time(it_index: int) -> int:
        """Возвращает время интегрирования, в миллисекундах, по значению индекса it_index (0..5)"""
        return 25 * 2 ** it_index

    @staticmethod
    def _raw_gain_to_gain(gain_index: int) -> float:
        """Преобразует значение индекса усиления (0..3) в коэффициент усиления"""
        _g = 1, 2, _GAIN_BASE, 0.25
        return _g[gain_index]

    @staticmethod
    def _check_index(gain_index: int, it_index: int):
        """Проверяет индексы усиления и интегрирования на правильность."""
        check_value(gain_index, range(4), f"Invalid als gain index: {gain_index}")
        check_value(it_index, range(6), f"Invalid als integration time index: {it_index}")

    @staticmethod
    def get_max_possible_illumination(gain_index: int, it_index: int) -> float:
        """Возвращает максимально возможный уровень освещенности в lux в
        зависимости от индекса усиления (gain_index 0..3) и индекса времени интегрирования it_index (0..5) """
        Veml7700._check_index(gain_index, it_index)
        #
        _gain = Veml7700._raw_gain_to_gain(gain_index)
        _g_base = _GAIN_BASE #  базовый коэффициент усиления (×1/8).
        _max_ill = _MAX_ILL_BASE   # максимум для IT=25 мс, gain=×1/8 (базовая конфигурация).
        _k = _gain / _g_base
        return (_max_ill / 2 ** it_index) / _k

    @staticmethod
    def _get_resolution(gain_index: int, it_index: int) -> float:
        """Возвращает разрешение младшего разряда в [lux] по индексу усиления (gain 0..3) и
        по индексу it_index (0..5)"""
        Veml7700._check_index(gain_index, it_index)
        #
        _gain = Veml7700._raw_gain_to_gain(gain_index)
        _g_base = _GAIN_BASE
        # разрешение датчика в [лк/отсчёт], соответствующее конфигурации:
        #   *   Время интеграции (ALS_IT):   25 мс (минимум)
        #   *   Усиление (ALS_GAIN):    х1/8 (минимальное)
        _k = _gain / _g_base
        return (_RESOLUTION_BASE / 2 ** it_index) / _k

    def __init__(self, adapter: bus_service.I2cAdapter, address: int = 0x10):
        """  """
        self._connection = DeviceEx(adapter=adapter, address=address, big_byte_order=False)
        self._buf_2 = bytearray(2)  # для _read_from_into
        #
        self._last_raw_ill =None    # хранит последнее, считанное из датчика, сырое значение освещенности
        self._als_gain_index = 0           # gain
        self._als_it_index = 0       # integration time
        self._als_pers = 0           # persistence protect number setting
        self._als_int_en = False     # interrupt enable setting
        self._als_shutdown = False   # ALS shut down setting
        self._enable_psm = False     # Enable power save mode for sensor
        self._psm = 0                # power save mode for sensor 0..3
        # включить нелинейное исправление значения освещенности (True) или выключить (False)
        self._en_non_lin_corr = True

    def _set_reg(self, addr: int, format_value: str | None, value: int | None = None) -> int:
        """Возвращает (при value is None)/устанавливает (при not value is None) содержимое регистра с адресом addr.
        разрядность регистра 16 бит!"""
        buf = self._buf_2
        _conn = self._connection
        if value is None:
            # читаю из Register устройства в буфер два байта
            if format_value is None:
                raise ValueError("При чтении из регистра не задан формат его значения!")
            _conn.read_buf_from_mem(address=addr, buf=buf, address_size=1)
            return _conn.unpack(fmt_char=format_value, source=buf)[0]
        #
        return self._connection.write_reg(reg_addr=addr, value=value, bytes_count=len(buf))

    def write_config(self, gain_index: int, it_index: int, persistence: int = 1,
                       int_en: bool = False, shutdown: bool = False):
        """Установка параметров Датчика Внешней Освещенности (ДВО - ALS).
        Setting Ambient Light Sensor (ALS) parameters.
        gain_index = 0..3; 0-gain=1, 1-gain=2, 2-gain=0.125(1/8), 3-gain=0.25(1/4).
        it_index = 0..5; 0-25 ms; 1-50 ms; 2-100 ms, 3-200 ms, 4-400 ms, 5-800 ms.
        int_en - разрешение прерываний.
        shutdown - выключить (Истина) или включить (Ложь) датчик
        persistence protect number = 0..3; 0-1, 1-2, 2-4, 3-8. Это фильтр количества срабатываний!
        """
        addr = self.ADDR_CFG_REG
        # перед любой перенастройкой, документация требует перевода датчика в режим ожидания
        _cfg = self._set_reg(addr=addr, format_value=FMT_UINT16_LE) # читаю
        self._set_reg(addr=addr, format_value=None, value=_cfg | 0x01)

        gain = check_value(gain_index, range(4), f"Invalid als gain value: {gain_index}")
        _tmp = check_value(it_index, range(6), f"Invalid als integration_time: {it_index}")
        it = Veml7700._it_index_to_raw_it(_tmp)    # integration_time

        pers = check_value(persistence, range(4), f"Invalid als persistence protect number: {persistence}")
        ie = 0
        if int_en:
            ie = 1
        sd = 0
        if shutdown:
            sd = 1
        #
        _cfg = 0
        _cfg |= sd
        _cfg |= ie << 1
        _cfg |= pers << 4
        _cfg |= it << 6
        _cfg |= gain << 11

        self._set_reg(addr=addr, format_value=None, value=_cfg)

        # save
        self._als_gain_index = gain
        self._als_it_index = it_index
        self._als_pers = pers
        self._als_int_en = int_en
        self._als_shutdown = shutdown

    def read_config(self) -> None:
        """read ALS config from register (2 byte)"""
        cfg = self._set_reg(addr=self.ADDR_CFG_REG, format_value=FMT_UINT16_LE)  # читаю
        #
        tmp = (cfg & 0b0001_1000_0000_0000) >> 11  # gain
        self._als_gain_index = tmp

        tmp = (cfg & 0b0000_0011_1100_0000) >> 6  # integration time setting
        self._als_it_index = Veml7700._raw_it_to_it(tmp)

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
        psm = check_value(psm, range(4), f"Invalid power save mode value: {psm}")
        reg_val = 0
        reg_val |= int(enable_psm)
        reg_val |= psm << 1
        self._set_reg(addr=self.ADDR_PWR_MODE_REG, format_value=None, value=reg_val)
        self._enable_psm = enable_psm
        self._psm = psm

    def get_interrupt_status(self) -> tuple:
        """Return interrupt flags while trigger occurred due to data crossing low/high threshold windows.
        tuple (low_threshold, high_threshold)."""
        irq_status = self._set_reg(addr=self.ADDR_STATUS_REG, format_value=FMT_UINT16_LE)  # читаю
        # Bit 15 defines interrupt flag while trigger occurred due to data crossing low threshold windows.
        int_th_low = bool(irq_status & 0b1000_0000_0000_0000)
        # Bit 14 defines interrupt flag while trigger occurred due to data crossing high threshold windows.
        int_th_high = bool(irq_status & 0b0100_0000_0000_0000)
        return int_th_low, int_th_high

    def get_measurement_value(self, value_index: int | None) -> int | float:
        """Возвращает освещённость в люксах или сырые данные каналов датчика.

                Метод поддерживает выбор возвращаемого значения через параметр value_index:
                  • None или 0: Рассчитанная освещённость [лк]. При включённом флаге
                    _en_non_lin_corr применяются две коррекции (согласно Vishay AppNote):
                      1. Нелинейность АЦП: полином 4-й степени для gain 1/8 или 1/4
                         при освещённости > 100 лк.
                      2. ИК-компенсация: автоматически считывается канал белого.
                    • Разрешение расчёта автоматически берётся из текущих настроек
                      _als_gain_index и _als_it_index.

                Example:
                    >>> sensor.write_config(gain_index=2, it_index=2)
                    >>> sensor.start_measurement()
                    >>> time.sleep_ms(150)
                    >>> lux = sensor.get_measurement_value()          # или value_index=0
                    >>> raw_als = sensor.get_measurement_value(1)
                    >>> raw_white = sensor.get_measurement_value(2)
                """
        raw_lux = self._set_reg(addr=self.ADDR_RAW_LUX_REG, format_value=FMT_UINT16_LE)  # читаю
        self._last_raw_ill = raw_lux
        if 1 == value_index:
            return raw_lux
        if 2 == value_index:
            return self._get_white_channel()
        #
        _t = raw_lux * Veml7700._get_resolution(self._als_gain_index, self._als_it_index)
        # блок расширенной коррекции
        if self._en_non_lin_corr:
            # 1. Нелинейная коррекция АЦП (только gain 1/8, 1/4 и >100 лк)
            if self._als_gain_index in (2, 3) and _t > 100:
                _t = 6.0135E-13 * _t ** 4 - 9.3924E-09 * _t ** 3 + 8.1488E-05 * _t ** 2 + 1.0023 * _t

            # 2. ИК-коррекция по белому каналу (WHITE/ALS > 2, источник галоген/солнце)
            # Оптимизация для MCU: white > 2 * raw_lux вместо float-деления
            if raw_lux > 0:
                wh = self._get_white_channel()
                if wh > 2 * raw_lux:
                    _t *= 0.95  # эмпирическая компенсация завышения показаний

        # без коррекции!
        return _t

    def _get_white_channel(self) -> int:
        """Return white channel output data.
        Не следует кривой V(lambda) человеческого глаза — чувствителен к ИК-излучению!
        Второй фотодиод в том же корпусе, но с широкой спектральной чувствительностью (включая ИК-диапазон 750–900 нм)!
        Назначение: для компенсации погрешности при источниках с ИК-составляющей:"""
        return self._set_reg(addr=self.ADDR_WH_CH_REG, format_value=FMT_UINT16_LE)

    def get_thresholds(self) -> tuple[int, int]:
        """Return ALS low and high threshold window setting as tuple (low_thr, high_thr)"""
        low = self._set_reg(addr=self.ADDR_LOW_THRESHOLD_REG, format_value=FMT_UINT16_LE)
        high = self._set_reg(addr=self.ADDR_HIGH_THRESHOLD_REG, format_value=FMT_UINT16_LE)
        return low, high

    def set_thresholds(self, low: int, high: int) -> None:
        """Установка порогов окна прерываний для ALS-канала.

        Пороги сравниваются с сырым значением регистра ALS (0..65535 отсчётов),
        до преобразования в люксы. Для установки порога в люксах предварительно
        пересчитайте значение через разрешение:
            counts = int(lux_threshold / resolution)

        Прерывание срабатывает, когда:
            - значение ALS выходит за окно [low, high] И
            - условие выполняется подряд `persistence` раз (настраивается в write_config)

        Статус прерывания читается методом get_interrupt_status().

        Args:
            low (int): Нижний порог окна, 0..65535 (сырые отсчёты).
            high (int): Верхний порог окна, 0..65535 (сырые отсчёты).
                       Должно быть >= low.

        Raises:
            ValueError: Если low или high вне диапазона 0..65535, или low > high.

        Note:
            Для работы прерываний необходимо:
                1. Включить ALS_INT_EN в write_config(int_en=True)
                2. Задать persistence (1/2/4/8) в write_config(persistence=...)
                3. Опросить get_interrupt_status() или подключить INT-линию (если доступна)

        Example:
            # Порог 100 лк при gain=1/4, IT=100ms (resolution=0.2304 лк/ct)
            threshold_ct = int(100 / 0.2304)  # ≈ 434
            sensor.write_config(gain_index=3, it_index=2, int_en=True, persistence=2)
            sensor.set_thresholds(low=0, high=threshold_ct)
        """
        check_value(low, range(65536), f"Invalid low threshold: {low} (0..65535)")
        check_value(high, range(65536), f"Invalid high threshold: {high} (0..65535)")
        if low > high:
            raise ValueError(f"Low threshold ({low}) must be <= high ({high})")
        self._set_reg(addr=self.ADDR_LOW_THRESHOLD_REG, format_value=None, value=low)
        self._set_reg(addr=self.ADDR_HIGH_THRESHOLD_REG, format_value=None, value=high)

    @property
    def last_raw(self)->int:
        """Возвращает последнее, считанное из датчика, сырое значение освещенности"""
        return self._last_raw_ill

    def __next__(self) -> float:
        return self.get_measurement_value(value_index=0)

    @micropython.native
    def get_conversion_cycle_time(self, offset: int = 100) -> int:
        """Return conversion cycle time in [ms].
        Without using the power-saving feature (PSM_EN = 0), the controller has to wait before reading out
        measurement results, at least for the programmed integration time. For example, for ALS_IT = 100 ms a wait time
        of ≥ 100 ms is needed. A more simple way of continuous measurements can be realized by activating the PSM feature,
        setting PSM_EN = 1."""
        base = 25 * 2 ** self._als_it_index
        if not self._enable_psm:
            return base
        # весь код ниже этой строки в этой функции под вопросом. документация на Veml7700
        # не позволяет мне понять алгоритм вычисления времени преобразования датчика при включенном режиме
        # экономии электроэнергии (power save mode)!
        return offset + base + 500 * (2 ** self._psm)

    def start_measurement(self):
        """Запускает процесс измерения освещённости.

        VEML7700 не имеет аппаратного single-shot режима. Этот метод:
        1. Если датчик в shutdown (ALS_SD=1) — выводит его в активный режим (ALS_SD=0)
        2. Ждёт ≥ 2.5 мс для стабилизации осциллятора и АЦП
        3. После этого измерения производятся непрерывно с периодом = integration_time

        После вызова метода данные доступны в регистре ALS (04h) и обновляются
        автоматически. Для чтения используйте …sensor.get_measurement_value(0)  # чтение результата

        ВНИМАНИЕ!!!
            После выхода из shutdown требуется >= 2.5 мс для стабилизации осциллятора и сигнального процессора.
            Используйте time.sleep_ms(3) или займите CPU чем-то полезным на это время!
        """
        # Если в shutdown — выходим из него
        if self._als_shutdown:
            # Перезаписываем конфиг с ALS_SD=0, сохраняя остальные параметры
            self.write_config(gain_index=self._als_gain_index, it_index=self._als_it_index,
                              persistence=self._als_pers,int_en=self._als_int_en, shutdown=False)
            self._als_shutdown = False

    def get_data_status(self, raw: bool = True):
        """
        Возвращает готовность данных.
        Для VEML7700 данные в регистре ALS всегда актуальны после завершения
        интеграции. Этот метод возвращает True, если датчик активен.
        """
        return not self._als_shutdown

    def is_single_shot_mode(self) -> bool:
        """VEML7700 не поддерживает аппаратный single-shot.
        Возвращает False всегда. Метод start_measurement() эмулирует
        "запуск" через выход из shutdown, но измерения продолжаются
        непрерывно до явного перевода в shutdown.
        """
        return False

    def is_continuously_mode(self) -> bool:
        """Возвращает Истина, когда датчик находится в режиме многократных измерений,
        производимых автоматически. Процесс запускается методом start_measurement"""
        return not self._als_shutdown

    @property
    def gain(self) -> tuple[int, float]:
        """Возвращает коэффициент усиления (raw_gain, gain)"""
        rg = self._als_gain_index
        return rg, Veml7700._raw_gain_to_gain(rg)

    @property
    def integration_time(self) -> tuple[int, int]:
        """Возвращает время интегрирования (raw_integration_time, integration_time_ms)"""
        rit = self._als_it_index
        return rit, self._get_integration_time(rit)

    @property
    def use_non_linear_correction(self) -> bool:
        """Возвращает признак использования нелинейной коррекции освещенности.
        Смотри страницу 21 документа 'Designing the VEML7700 Into an Application'"""
        return self._en_non_lin_corr

    @use_non_linear_correction.setter
    def use_non_linear_correction(self, value: bool):
        """Устанавливает признак использования нелинейной коррекции освещенности.
        Смотри страницу 21 документа 'Designing the VEML7700 Into an Application'"""
        self._en_non_lin_corr = value