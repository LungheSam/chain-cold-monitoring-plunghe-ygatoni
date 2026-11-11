"""Tests for the sysfs sensor readers, using fake /sys folders."""
from coldchain import sysfs


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_ds18b20_reading(tmp_path):
    write(tmp_path / "28-0123456789ab" / "temperature", "5187\n")
    write(tmp_path / "w1_bus_master1" / "temperature_not_a_probe", "x")
    assert sysfs.read_ds18b20(str(tmp_path)) == 5.187


def test_ds18b20_negative_and_85(tmp_path):
    write(tmp_path / "28-aa" / "temperature", "-1250")
    assert sysfs.read_ds18b20(str(tmp_path)) == -1.25
    write(tmp_path / "28-aa" / "temperature", "85000")
    assert sysfs.read_ds18b20(str(tmp_path)) == 85.0   # the engine treats this as a fault


def test_ds18b20_missing_or_garbage(tmp_path):
    assert sysfs.read_ds18b20(str(tmp_path)) is None
    write(tmp_path / "28-aa" / "temperature", "")
    assert sysfs.read_ds18b20(str(tmp_path)) is None


def make_dht(tmp_path, temp="24100", hum="61200", name="dht11@11"):
    dev = tmp_path / "iio_device0"      # on the Pi: iio:device0 (":" is not allowed on Windows)
    write(dev / "name", name + "\n")
    write(dev / "in_temp_input", temp)
    write(dev / "in_humidityrelative_input", hum)


def test_dht22_reading(tmp_path):
    make_dht(tmp_path)
    assert sysfs.read_dht22(str(tmp_path)) == (24.1, 61.2)


def test_dht22_out_of_range_values_are_rejected(tmp_path):
    make_dht(tmp_path, hum="250000")
    assert sysfs.read_dht22(str(tmp_path)) == (None, None)


def test_dht22_other_iio_device_is_ignored(tmp_path):
    make_dht(tmp_path, name="some_adc")
    assert sysfs.read_dht22(str(tmp_path)) == (None, None)
