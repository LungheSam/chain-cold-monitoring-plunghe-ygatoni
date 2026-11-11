"""16x2 LCD with PCF8574 backpack. Run: python -m tests.hw.test_lcd [address, default 27]"""
import sys
import time

from tests.hw.common import banner

WIRING = """
Backpack GND -> GND, VCC -> 5 V
SDA -> level shifter -> GPIO 2 (pin 3); SCL -> level shifter -> GPIO 3 (pin 5)
(BSS138 module: LV = 3.3 V, HV = 5 V, see docs/wiring.md)
Enable I2C: sudo raspi-config nonint do_i2c 0   then   i2cdetect -y 1   should show 27 (or 3f)
If the screen is lit but blank: turn the contrast potentiometer on the backpack.
"""


def main():
    address = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x27
    banner("LCD test at address 0x%02x: text and a counter for 10 s." % address, WIRING)
    from RPLCD.i2c import CharLCD
    try:
        lcd = CharLCD("PCF8574", address, port=1, cols=16, rows=2, charmap="A00")
    except OSError as e:
        print("FAIL: no answer at 0x%02x (%s). Run i2cdetect -y 1 to find the address." % (address, e))
        return
    lcd.clear()
    lcd.write_string("Cold chain LCD")
    for i in range(10):
        lcd.cursor_pos = (1, 0)
        lcd.write_string("count %2d        " % i)
        time.sleep(1)
    lcd.clear()
    lcd.write_string("LCD test done")
    print("PASS if you saw the text and the counter.")


if __name__ == "__main__":
    main()
