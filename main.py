# micropython
# mail: goctaprog@gmail.com
# MIT license


# Please read this before use!: https://www.vishay.com/docs/84286/veml7700.pdf
from machine import I2C, Pin
import veml7700vishay
from sensor_pack.bus_service import I2cAdapter
import time

if __name__ == '__main__':
    # пожалуйста установите выводы scl и sda в конструкторе для вашей платы, иначе ничего не заработает!
    # please set scl and sda pins for your board, otherwise nothing will work!
    # https://docs.micropython.org/en/latest/library/machine.I2C.html#machine-i2c
    # i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000) № для примера
    # bus =  I2C(scl=Pin(4), sda=Pin(5), freq=100000)   # на esp8266    !
    # i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000)  # on Arduino Nano RP2040 Connect tested
    i2c = I2C(id=1, scl=Pin(7), sda=Pin(6), freq=400_000)  # on Raspberry Pi Pico
    adaptor = I2cAdapter(i2c)
    sol = veml7700vishay.Veml7700(adaptor)

    # если у вас посыпались исключения EIO, то проверьте все соединения.
    # gain = 1, integration time = 25 ms, persistence = 1, interrupt = shutdown = False
    # sol.set_config_als(0, 2, 0, False, False)
    sol.set_config_als(gain=3, integration_time=4, persistence=1, interrupt_enable=False, shutdown=False)
    # sol.set_power_save_mode(True, 2)
    sol.set_power_save_mode(enable_psm=False, psm=0)
    delay = old_lux = curr_max = 1

    for lux in sol:
        if lux != old_lux:
            curr_max = max(lux, curr_max)
            lt = time.localtime()
            wh = sol.get_white_channel()
            delay = sol.get_conversion_cycle_time()
            print(f"{lt[3:6]}\tIllum. [lux]: {lux}\traw: {sol.last_raw}\twhite ch.: {wh}\tmax: {curr_max}\tNormalized [%]:\
{100*lux/curr_max}\tdelay: {delay} [ms]")
        old_lux = lux
        time.sleep_ms(delay)
