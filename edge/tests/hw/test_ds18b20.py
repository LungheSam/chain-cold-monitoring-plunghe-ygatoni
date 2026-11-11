"""DS18B20 internal probe. Run: python -m tests.hw.test_ds18b20"""
import time

from tests.hw.common import banner

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
        time.sleep(1)
    print("PASS" if bad == 0 else "WARNING: %d bad readings (85.0 C = power-on value, check wiring)" % bad)


if __name__ == "__main__":
    main()
