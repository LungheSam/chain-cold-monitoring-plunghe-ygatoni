"""Reading the sensors from Linux sysfs files. No GPIO library needed, so this is testable on a laptop
with fake folders (the base paths are parameters).

DS18B20 (1-Wire, dtoverlay=w1-gpio,gpiopin=4):
    /sys/bus/w1/devices/28-xxxxxxxxxxxx/temperature   -> "5187" (milli-degrees C)
DHT22 (kernel IIO driver, dtoverlay=dht11,gpiopin=17; the dht11 driver also reads the DHT22):
    /sys/bus/iio/devices/iio:deviceN/name                       -> "dht11@11" or similar (VERIFY)
    /sys/bus/iio/devices/iio:deviceN/in_temp_input              -> "24100" (milli-degrees C)
    /sys/bus/iio/devices/iio:deviceN/in_humidityrelative_input  -> "61200" (milli-percent)
The DHT driver often fails with EIO (timing on a busy Linux system). That is normal; the alarm
engine only declares a fault after 5 failures in a row.
"""
import glob
import os

W1_BASE = "/sys/bus/w1/devices"
IIO_BASE = "/sys/bus/iio/devices"


def find_ds18b20(base=W1_BASE):
    """Path of the first DS18B20 'temperature' file, or None. DS18B20 IDs start with 28-."""
    paths = sorted(glob.glob(os.path.join(base, "28-*", "temperature")))
    return paths[0] if paths else None


def read_ds18b20(base=W1_BASE):
    """Temperature in C, or None if the probe is missing or the read fails (CRC error, I/O error)."""
    path = find_ds18b20(base)
    if path is None:
        return None
    try:
        with open(path) as f:
            text = f.read().strip()
        return int(text) / 1000.0
    except (OSError, ValueError):
        return None


def find_dht_device(base=IIO_BASE):
    """Folder of the IIO device made by the dht11 overlay, or None.
    Checks the 'name' file of every IIO device (on the Pi the folders are called iio:deviceN)."""
    for folder in sorted(glob.glob(os.path.join(base, "*"))):
        try:
            with open(os.path.join(folder, "name")) as f:
                if f.read().strip().startswith("dht11"):
                    return folder
        except OSError:
            pass
    return None


def read_dht22(base=IIO_BASE, retries=2):
    """(temperature C, humidity %) or (None, None). Retries a failed read a couple of times."""
    folder = find_dht_device(base)
    if folder is None:
        return None, None
    for _ in range(retries + 1):
        try:
            with open(os.path.join(folder, "in_temp_input")) as f:
                temp = int(f.read().strip()) / 1000.0
            with open(os.path.join(folder, "in_humidityrelative_input")) as f:
                humidity = int(f.read().strip()) / 1000.0
        except (OSError, ValueError):
            continue
        if -40 <= temp <= 80 and 0 <= humidity <= 100:   # DHT22 datasheet range
            return temp, humidity
    return None, None


def wifi_up(interface="wlan0"):
    """True if the Wi-Fi interface is connected (operstate 'up')."""
    try:
        with open("/sys/class/net/%s/operstate" % interface) as f:
            return f.read().strip() == "up"
    except OSError:
        return False


def boot_id():
    """Changes at every boot. time.monotonic() is only comparable within one boot."""
    try:
        with open("/proc/sys/kernel/random/boot_id") as f:
            return f.read().strip()
    except OSError:
        return "no-boot-id-%d" % os.getpid()   # laptops: one "boot" per program run
