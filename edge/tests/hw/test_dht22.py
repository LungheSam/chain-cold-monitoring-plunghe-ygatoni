"""DHT22 ambient sensor through the kernel IIO driver. Run: python -m tests.hw.test_dht22"""
import time

from tests.hw.common import banner

WIRING = """
DHT22 VCC  -> 3.3 V (pin 17)
DHT22 DATA -> GPIO 17 (pin 11), with 10 kOhm to 3.3 V (many modules have it already: VERIFY)
DHT22 GND  -> GND (pin 20)
/boot/firmware/config.txt: dtoverlay=dht11,gpiopin=17   (then reboot)
"""


def main():
    from coldchain import sysfs
    banner("DHT22 test: 10 readings, one every 3 s. Breathe on it to see humidity rise.", WIRING)
    folder = sysfs.find_dht_device()
    if folder is None:
        print("FAIL: no IIO device named dht11* in /sys/bus/iio/devices.")
        print("Check the overlay line and the reboot; then: cat /sys/bus/iio/devices/*/name")
        return
    print("Found device:", folder)
    fails = 0
    for i in range(10):
        temp, hum = sysfs.read_dht22()
        if temp is None:
            fails += 1
            print("%2d: read error (normal now and then)" % (i + 1))
        else:
            print("%2d: %.1f C  %.1f %%RH" % (i + 1, temp, hum))
        time.sleep(3)
    print("PASS" if fails <= 3 else "FAIL: %d of 10 reads failed. Check the pull-up and wire length." % fails)
    print("If values look wrong (humidity near 1 %, temperature near 0.2 C) the driver is decoding")
    print("the sensor as a DHT11: tell Claude, and we switch to a user-space library.")


if __name__ == "__main__":
    main()
