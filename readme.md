# VEML7700
Micropython module for VEML7700, high accuracy ambient light sensor from Vishay Semiconductors.

Just connect your VEML7700 board to Arduino, ESP or any other board with MicroPython firmware.

Supply voltage VEML7700 3.3 or 5.0 volts! Use four wires to connect (I2C).
1. +VCC (Supply voltage)
2. GND
3. SDA
4. SCL

Upload micropython firmware to the NANO(ESP, etc) board, and then *.py files: main.py, veml7700vishay.py,
and sensor_pack folder. 
Then open main.py in your IDE and run it.