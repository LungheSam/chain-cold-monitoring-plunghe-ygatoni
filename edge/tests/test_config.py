import pytest

from coldchain.config import load_settings


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
