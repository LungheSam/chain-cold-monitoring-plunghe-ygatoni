"""DS18B20 internal probe. Run: python -m tests.hw.test_ds18b20"""
import time

from tests.hw.common import banner, lcd_show, say

WIRING = """
DS18B20 red    -> 3.3 V (pin 1)
DS18B20 black  -> GND (pin 9)
DS18B20 yellow -> GPIO 4 (pin 7), with 4.7 kOhm from GPIO 4 to 3.3 V
/boot/firmware/config.txt: dtoverlay=w1-gpio,gpiopin=4   (then reboot)
Probe wire colours: VERIFY on the probe listing (some use white for data).
"""


def main():
    from coldchain import sysfs
    banner("DS18B20 test: 10 readings, 1 per second. Hold the probe to see it rise.", WIRING)
    path = sysfs.find_ds18b20()
    if path is None:
        say("DS18B20 FAIL", "probe not found")
        print("FAIL: no 28-* device in /sys/bus/w1/devices.")
        print("Check: the overlay line, the reboot, the 4.7 kOhm pull-up, and the data wire on pin 7.")
        return
    print("Found probe:", path)
    bad = 0
    for i in range(10):
        t = sysfs.read_ds18b20()
        if t is None or t in (85.0, -127.0):
            bad += 1
        print("%2d: %s" % (i + 1, "read error" if t is None else "%.3f C" % t))
        lcd_show("DS18B20 %d/10" % (i + 1), "read error" if t is None else "%.2f C" % t)
        time.sleep(1)
    if bad == 0:
        say("DS18B20 test", "PASS")
    else:
        say("DS18B20 WARNING", "%d bad readings" % bad)
        print("85.0 C = power-on value: check the wiring")


if __name__ == "__main__":
    main()
