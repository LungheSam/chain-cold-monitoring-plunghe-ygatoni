"""Unit tests for the alarm engine. Demo profile: confirm 20 s, door limit 15 s, power confirm 3 s."""
import pytest

from coldchain.alarm import AlarmEngine, Debouncer
from coldchain.clock import FakeClock
from coldchain.config import load_settings
from tests.helpers import make_engine, reading, run, types


# ---------------------------------------------------------------- normal running

def test_all_normal_is_ok():
    engine, clock = make_engine()
    events = run(engine, clock, 60, temp=5.0)
    assert events == []
    assert engine.status() == "OK"
    assert engine.outputs() == {"red": "off", "green": "on", "buzzer": False}
    assert engine.snapshot()["outOfRangeSeconds"] == 0


# ---------------------------------------------------------------- temperature high / low

def test_high_alarm_only_after_confirm_delay():
    engine, clock = make_engine()
    run(engine, clock, 5, temp=5.0)
    events = run(engine, clock, 19, temp=9.0)     # 19 s out of range: not yet
    assert events == []
    assert engine.status() == "WARNING"
    events = run(engine, clock, 2, temp=9.0)      # now past 20 s
    assert types(events) == ["OUT_OF_RANGE_HIGH"]
    assert events[0]["details"]["limit"] == 8.0
    assert engine.status() == "ALARM"
    assert engine.outputs() == {"red": "blink", "green": "off", "buzzer": True}


def test_low_alarm():
    engine, clock = make_engine()
    events = run(engine, clock, 25, temp=1.0)
    assert types(events) == ["OUT_OF_RANGE_LOW"]
    assert engine.active_alarms() == {"TEMP_LOW"}


def test_timer_counts_from_leaving_range_not_from_confirmation():
    engine, clock = make_engine()
    run(engine, clock, 10, temp=5.0)
    run(engine, clock, 30, temp=9.0)  # first bad reading at t=11, last at t=40
    # Counted from the first out-of-range reading: 29 s (not 30 - 20 = 10 s)
    assert engine.snapshot()["outOfRangeSeconds"] == 29


def test_hysteresis_keeps_alarm_until_below_7_7():
    engine, clock = make_engine()
    run(engine, clock, 25, temp=9.0)
    assert engine.temp_alarm == "HIGH"

    events = run(engine, clock, 10, temp=7.9)     # in range, but not past the hysteresis
    assert events == []
    assert engine.temp_alarm == "HIGH"
    total_before = engine.snapshot()["outOfRangeSeconds"]

    events = run(engine, clock, 1, temp=7.6)
    assert types(events) == ["BACK_IN_RANGE"]
    details = events[0]["details"]
    assert details["confirmed"] is True
    assert details["maxTemp"] == 9.0 and details["minTemp"] == 7.6
    assert engine.temp_alarm is None
    assert engine.status() == "OK"
    # 7.9 C is inside 2..8 C, so those 10 s were not added (only the first second, from 9.0)
    assert engine.snapshot()["outOfRangeSeconds"] == total_before


def test_excursion_record_has_start_end_duration():
    engine, clock = make_engine()
    run(engine, clock, 5, temp=5.0)
    start_wall_ms = int((clock.time() + 1) * 1000)
    run(engine, clock, 30, temp=9.5)
    run(engine, clock, 1, temp=5.0)
    assert len(engine.excursions) == 1
    exc = engine.excursions[0]
    assert exc["start"] == start_wall_ms
    assert exc["end"] == start_wall_ms + 30_000
    assert exc["durationS"] == 30
    assert exc["outOfRangeSeconds"] == 30
    assert exc["direction"] == "HIGH"
    assert exc["maxTemp"] == 9.5


def test_short_blip_counts_but_does_not_alarm():
    engine, clock = make_engine()
    events = run(engine, clock, 10, temp=8.5)     # shorter than the 20 s confirm delay
    events += run(engine, clock, 1, temp=5.0)
    assert types(events) == ["BACK_IN_RANGE"]
    assert events[0]["details"]["confirmed"] is False
    assert engine.excursions[0]["confirmed"] is False
    assert engine.snapshot()["outOfRangeSeconds"] == 10
    assert engine.status() == "OK"


def test_total_is_cumulative_over_excursions():
    engine, clock = make_engine()
    run(engine, clock, 30, temp=9.0)
    run(engine, clock, 5, temp=5.0)
    run(engine, clock, 40, temp=1.0)
    run(engine, clock, 5, temp=5.0)
    assert engine.snapshot()["outOfRangeSeconds"] == 70
    assert [e["direction"] for e in engine.excursions] == ["HIGH", "LOW"]
    assert sum(e["outOfRangeSeconds"] for e in engine.excursions) == 70


def test_jump_from_high_to_low_starts_new_excursion():
    engine, clock = make_engine()
    run(engine, clock, 25, temp=9.0)
    events = run(engine, clock, 25, temp=1.0)
    assert types(events) == ["BACK_IN_RANGE", "OUT_OF_RANGE_LOW"]
    assert engine.active_alarms() == {"TEMP_LOW"}


# ---------------------------------------------------------------- acknowledge

def test_acknowledge_silences_buzzer_but_red_led_stays():
    engine, clock = make_engine()
    run(engine, clock, 25, temp=9.0)
    event = engine.acknowledge(by="tester")
    assert event["type"] == "ALARM_ACKNOWLEDGED"
    assert event["details"]["alarms"] == ["TEMP_HIGH"]
    assert engine.outputs() == {"red": "blink", "green": "off", "buzzer": False}
    run(engine, clock, 10, temp=9.0)
    assert engine.outputs()["buzzer"] is False


def test_new_alarm_type_sounds_again_after_acknowledge():
    engine, clock = make_engine()
    run(engine, clock, 25, temp=9.0)
    engine.acknowledge()
    events = run(engine, clock, 17, temp=9.0, door=True)
    assert "DOOR_OPEN_TOO_LONG" in types(events)
    assert engine.outputs()["buzzer"] is True


def test_same_alarm_after_it_cleared_sounds_again():
    engine, clock = make_engine()
    run(engine, clock, 25, temp=9.0)
    engine.acknowledge()
    run(engine, clock, 2, temp=5.0)          # clears
    run(engine, clock, 25, temp=9.0)         # comes back
    assert engine.outputs()["buzzer"] is True


def test_acknowledge_without_alarm_returns_none():
    engine, clock = make_engine()
    run(engine, clock, 5)
    assert engine.acknowledge() is None


# ---------------------------------------------------------------- door

def test_door_open_too_long_then_closed():
    engine, clock = make_engine()
    events = run(engine, clock, 14, door=True)
    assert events == []
    assert engine.status() == "WARNING"
    events = run(engine, clock, 2, door=True)
    assert types(events) == ["DOOR_OPEN_TOO_LONG"]
    assert engine.status() == "ALARM"
    events = run(engine, clock, 2, door=False)        # 2 samples: debounce needs a second look
    assert types(events) == ["DOOR_CLOSED"]
    assert events[0]["details"]["alarmed"] is True
    assert events[0]["details"]["openSeconds"] == 16
    assert engine.status() == "OK"


def test_short_door_opening_gives_door_closed_only():
    engine, clock = make_engine()
    events = run(engine, clock, 5, door=True) + run(engine, clock, 2, door=False)
    assert types(events) == ["DOOR_CLOSED"]
    assert events[0]["details"]["alarmed"] is False


def test_door_flapping_glitches_are_debounced():
    """Contact bounce shorter than 50 ms must not reset the open-door timer."""
    engine, clock = make_engine()
    events = []
    for i in range(2000):                     # 20 s sampled every 10 ms
        clock.advance(0.01)
        bounce = i % 100 in (50, 51)          # a 20 ms "closed" bounce every second
        events += engine.update(reading(door=not bounce))
    assert types(events) == ["DOOR_OPEN_TOO_LONG"]   # no DOOR_CLOSED in between


def test_debouncer():
    d = Debouncer(0.05, False)
    assert d.update(True, 0.00) is False
    assert d.update(True, 0.03) is False
    assert d.update(False, 0.04) is False      # glitch, back to the stable value
    assert d.update(True, 0.10) is False
    assert d.update(True, 0.16) is True        # stable for 60 ms


# ---------------------------------------------------------------- power

def test_power_flicker_shorter_than_confirm_is_ignored():
    engine, clock = make_engine()
    events = run(engine, clock, 2, mains=False) + run(engine, clock, 5, mains=True)
    assert events == []


def test_power_lost_and_restored_with_duration():
    engine, clock = make_engine()
    events = run(engine, clock, 3, mains=False)
    assert events == []                                # first LOW sample at t=1, confirmed at t=4
    events = run(engine, clock, 1, mains=False)
    assert types(events) == ["POWER_LOST"]
    assert engine.active_alarms() == {"POWER_LOST"}
    events = run(engine, clock, 60, mains=False) + run(engine, clock, 4, mains=True)
    assert types(events) == ["POWER_RESTORED"]
    assert events[0]["details"]["durationS"] == 64     # LOW from t=1 to t=65
    assert engine.status() == "OK"


def test_unit_starting_without_power_raises_power_lost():
    engine, clock = make_engine()
    assert types(run(engine, clock, 4, mains=False)) == ["POWER_LOST"]


# ---------------------------------------------------------------- sensor faults

@pytest.mark.parametrize("bad_value, reason", [(85.0, "85C"), (-127.0, "-127C"), (None, "read_error")])
def test_internal_probe_fault_is_an_alarm(bad_value, reason):
    engine, clock = make_engine()
    run(engine, clock, 5, temp=5.0)
    events = run(engine, clock, 2, temp=bad_value)
    assert events == []                       # one or two bad reads are tolerated
    events = run(engine, clock, 1, temp=bad_value)
    assert types(events) == ["SENSOR_FAULT"]
    assert events[0]["details"] == {"sensor": "ds18b20", "reason": reason}
    assert engine.status() == "ALARM"
    assert engine.snapshot()["internalTemp"] is None


def test_fault_counts_samples_not_loop_passes():
    """The same bad sample seen by 10 loop passes is still only one bad read."""
    from coldchain.alarm import Reading
    engine, clock = make_engine()
    run(engine, clock, 2, temp=5.0)
    events = []
    for i in range(20):                       # 2 s of 0.1 s loop passes, 2 new samples
        clock.advance(0.1)
        events += engine.update(Reading(85.0, 24.0, 60.0, False, True, internal_new=(i % 10 == 0)))
    assert events == []
    assert engine.internal_fault is False


def test_single_85_reading_does_not_count_as_out_of_range():
    engine, clock = make_engine()
    run(engine, clock, 5, temp=5.0)
    events = run(engine, clock, 1, temp=85.0) + run(engine, clock, 5, temp=5.0)
    assert events == []
    assert engine.snapshot()["outOfRangeSeconds"] == 0
    assert engine.excursions == []


def test_internal_probe_restored():
    engine, clock = make_engine()
    run(engine, clock, 3, temp=None)
    events = run(engine, clock, 1, temp=5.0)
    assert types(events) == ["SENSOR_RESTORED"]
    assert engine.status() == "OK"


def test_dht22_fault_after_five_failures_is_only_a_warning():
    engine, clock = make_engine()
    run(engine, clock, 2)
    events = run(engine, clock, 4, amb=None, hum=None)
    assert events == []
    assert engine.snapshot()["ambientTemp"] == 24.0     # last good value kept
    events = run(engine, clock, 1, amb=None, hum=None)
    assert types(events) == ["SENSOR_FAULT"]
    assert events[0]["details"]["sensor"] == "dht22"
    assert engine.status() == "WARNING"
    assert engine.snapshot()["ambientTemp"] is None


# ---------------------------------------------------------------- restart in the middle of an excursion

def restart(engine, clock, off_seconds, synced_after=True):
    """Save, 'reboot' for off_seconds, and build a new engine from the saved state."""
    state = engine.to_state()
    clock.advance(off_seconds)
    clock.is_synced = synced_after
    new_engine = AlarmEngine(load_settings({"PROFILE": "demo"}), clock)
    new_engine.load_state(state)
    return new_engine


def test_total_survives_restart():
    engine, clock = make_engine()
    run(engine, clock, 30, temp=9.0)
    run(engine, clock, 2, temp=5.0)
    engine = restart(engine, clock, 60)
    run(engine, clock, 5, temp=5.0)
    assert engine.snapshot()["outOfRangeSeconds"] == 30
    assert len(engine.excursions) == 1


def test_restart_during_confirmed_excursion_keeps_alarm_and_adds_offline_gap():
    engine, clock = make_engine()
    run(engine, clock, 30, temp=9.0)                    # alarm, 29 s counted
    assert engine.temp_alarm == "HIGH"
    engine = restart(engine, clock, 120)                # off for 2 minutes
    assert engine.temp_alarm == "HIGH"                  # no new 20 s wait
    events = run(engine, clock, 10, temp=9.0)
    assert "OUT_OF_RANGE_HIGH" not in types(events)     # not announced twice
    # 29 measured before + 120 off + 9 measured after
    assert engine.snapshot()["outOfRangeSeconds"] == 29 + 120 + 9
    run(engine, clock, 1, temp=5.0)
    exc = engine.excursions[-1]
    assert exc["offlineGapS"] == 120
    assert exc["durationS"] == 30 + 120 + 10
    assert exc["offlineGapUnknown"] is False


def test_restart_gap_added_only_once_clock_syncs():
    engine, clock = make_engine()
    run(engine, clock, 30, temp=9.0)
    engine = restart(engine, clock, 120, synced_after=False)
    run(engine, clock, 10, temp=9.0)
    assert engine.snapshot()["outOfRangeSeconds"] == 29 + 9     # gap not known yet
    clock.is_synced = True                                      # NTP syncs
    run(engine, clock, 1, temp=9.0)
    assert engine.snapshot()["outOfRangeSeconds"] == 29 + 9 + 120 + 1


def test_restart_back_in_range_does_not_add_gap():
    engine, clock = make_engine()
    run(engine, clock, 30, temp=9.0)
    engine = restart(engine, clock, 120)
    events = run(engine, clock, 1, temp=5.0)
    assert types(events) == ["BACK_IN_RANGE"]
    assert engine.snapshot()["outOfRangeSeconds"] == 29
    assert engine.excursions[-1]["offlineGapS"] == 0


def test_restart_when_save_was_unsynced_marks_gap_unknown():
    engine, clock = make_engine(synced=False)
    run(engine, clock, 30, temp=9.0)
    engine = restart(engine, clock, 120, synced_after=True)
    run(engine, clock, 5, temp=9.0)
    run(engine, clock, 1, temp=5.0)
    exc = engine.excursions[-1]
    assert exc["offlineGapS"] == 0
    assert exc["offlineGapUnknown"] is True


def test_state_is_json_serialisable():
    import json
    engine, clock = make_engine()
    run(engine, clock, 30, temp=9.0)
    json.dumps(engine.to_state())


# ---------------------------------------------------------------- thresholds

def test_set_thresholds_changes_the_limit():
    engine, clock = make_engine()
    engine.set_thresholds(maxC=10.0)
    assert run(engine, clock, 30, temp=9.0) == []


@pytest.mark.parametrize("kwargs", [
    {"minC": 9.0},                 # min above max
    {"minC": 5.0, "maxC": 5.5},    # closer than 2 x hysteresis
    {"confirmDelayS": -1},
    {"doorLimitS": 0},
    {"maxC": 50},
])
def test_bad_thresholds_are_rejected(kwargs):
    engine, _ = make_engine()
    with pytest.raises(ValueError):
        engine.set_thresholds(**kwargs)
    assert engine.thresholds()["maxC"] == 8.0


def test_real_profile_waits_five_minutes():
    clock = FakeClock()
    engine = AlarmEngine(load_settings({"PROFILE": "real"}), clock)
    assert run(engine, clock, 299, temp=9.0) == []
    assert types(run(engine, clock, 2, temp=9.0)) == ["OUT_OF_RANGE_HIGH"]


def test_events_have_id_timestamp_and_sync_flag():
    engine, clock = make_engine()
    event = run(engine, clock, 4, mains=False)[0]
    assert set(event) == {"id", "ts", "type", "details", "timeSynced"}
    assert event["ts"] == int(clock.time() * 1000)
    assert event["timeSynced"] is True
