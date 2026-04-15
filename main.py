# micropython
# mail: goctaprog@gmail.com
# MIT license


# Please read this before use!: https://www.vishay.com/docs/84286/veml7700.pdf
from micropython import const
from machine import I2C, Pin
from veml7700vishay import Veml7700
from sensor_pack_2.bus_service import I2cAdapter
import time

ID_I2C = const(1)
SDA_PIN_N = const(6)
SCL_PIN_N = const(7)
FREQ_I2C = const(400_000)

if __name__ == '__main__':
    # пожалуйста установите выводы scl и sda в конструкторе для вашей платы, иначе ничего не заработает!
    # please set scl and sda pins for your board, otherwise nothing will work!
    # https://docs.micropython.org/en/latest/library/machine.I2C.html#machine-i2c
    # i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000) № для примера
    # bus =  I2C(scl=Pin(4), sda=Pin(5), freq=100000)   # на esp8266    !
    # i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000)  # on Arduino Nano RP2040 Connect tested
    i2c = I2C(id=ID_I2C, scl=Pin(SCL_PIN_N), sda=Pin(SDA_PIN_N), freq=FREQ_I2C)  # on Raspberry Pi Pico
    adaptor = I2cAdapter(i2c)
    sol = Veml7700(adaptor)

    # если у вас посыпались исключения EIO, то проверьте все соединения.
    # gain = 1, integration time = 25 ms, persistence = 1, interrupt = shutdown = False
    # sol.set_config_als(0, 2, 0, False, False)
    sol.write_config(gain_index=3, it_index=4, persistence=1, int_en=False, shutdown=False)
    # sol.set_power_save_mode(True, 2)
    sol.set_power_save_mode(enable_psm=False, psm=0)
    delay = old_lux = curr_max = 1
    mpi = Veml7700.get_max_possible_illumination(sol.gain[0], sol.integration_time[0])
    print(f"Наибольшая освещенность при текущих настройках [lux]: {mpi}")
    # вычислен для начальной(!) конфигурации
    wt = sol.get_conversion_cycle_time()
    print(f"Режим нелинейного исправления используется?: {sol.use_non_linear_correction}")
    cnt = 0
    for lux in sol:
        # Переключаем режим коррекции каждые 30 измерений (для проверки)
        sol.use_non_linear_correction = 0 == (cnt // 30) % 2
        if lux != old_lux:
            curr_max = max(lux, curr_max)
            wh = sol.get_measurement_value(2)
            #
            print(f"lux: {lux} raw: {sol.last_raw} white ch.: {wh} max: {curr_max} Normalized [%]: {100*lux/curr_max} Use non lin corr: {sol.use_non_linear_correction}")
        old_lux = lux
        if lux > 0.95 * mpi:
            print("Текущая освещенность превысила максимальную, при данных настройках!"
                  " Нужно перенастроить датчик! Предел почти достигнут!")
        time.sleep_ms(wt)
        cnt += 1
