import pytest

from coldchain.config import load_settings


def test_lock_type_defaults_to_relay_and_accepts_servo():
    assert load_settings({})["LOCK_TYPE"] == "relay"
    s = load_settings({"LOCK_TYPE": "servo"})
    assert s["LOCK_TYPE"] == "servo" and s["SERVO_UNLOCKED_DEG"] == 90
    with pytest.raises(ValueError):
        load_settings({"LOCK_TYPE": "magnet"})


def test_reed_inverted_setting():
    assert load_settings({})["REED_INVERTED"] is False
    assert load_settings({"REED_INVERTED": "1"})["REED_INVERTED"] is True


def test_demo_profile_is_default():
    s = load_settings({})
    assert s["PROFILE"] == "demo"
    assert s["TEMP_CONFIRM_S"] == 20
    assert s["DOOR_OPEN_LIMIT_S"] == 15
    assert s["POWER_CONFIRM_S"] == 3


def test_real_profile():
    s = load_settings({"PROFILE": "real"})
    assert (s["TEMP_CONFIRM_S"], s["DOOR_OPEN_LIMIT_S"], s["POWER_CONFIRM_S"]) == (300, 120, 5)


def test_bad_profile_is_rejected():
    with pytest.raises(ValueError):
        load_settings({"PROFILE": "fast"})
