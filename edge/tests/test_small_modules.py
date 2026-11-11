"""Tests for the telemetry policy, LCD text, command handler and state file."""
import json
import os

from coldchain.commands import CommandHandler
from coldchain.display import format_duration, line1, line2, PAGES
from coldchain.store import load_json, save_json_atomic
from coldchain.telemetry import TelemetryPolicy
from tests.helpers import make_engine, run


# ---------------------------------------------------------------- telemetry policy

def test_telemetry_first_message_and_period():
    p = TelemetryPolicy()
    assert p.should_send(0, 5.0, "OK")
    p.mark_sent(0, 5.0, "OK")
    assert not p.should_send(29, 5.0, "OK")
    assert p.should_send(30, 5.0, "OK")


def test_telemetry_on_temperature_change_but_not_too_often():
    p = TelemetryPolicy()
    p.mark_sent(0, 5.0, "OK")
    assert not p.should_send(2, 5.5, "OK")     # big change, but within 5 s
    assert p.should_send(5, 5.5, "OK")
    assert not p.should_send(5, 5.15, "OK")    # change of 0.15 is too small


def test_telemetry_on_status_change_immediately():
    p = TelemetryPolicy()
    p.mark_sent(0, 5.0, "OK")
    assert p.should_send(1, 5.0, "ALARM")


# ---------------------------------------------------------------- LCD

def snap(**over):
    s = {"internalTemp": 5.24, "ambientTemp": 24.1, "humidity": 61.0, "doorOpen": False,
         "doorOpenSeconds": 0, "mainsPower": True, "status": "OK", "outOfRangeSeconds": 750}
    s.update(over)
    return s


def test_lcd_lines_are_always_16_characters():
    for s in [snap(), snap(internalTemp=None, status="ALARM"), snap(internalTemp=-25.5, status="WARNING"),
              snap(ambientTemp=None, humidity=None, doorOpen=True, doorOpenSeconds=4000, mainsPower=False)]:
        assert len(line1(s)) == 16
        for page in range(len(PAGES)):
            assert len(line2(s, page, True, False)) == 16


def test_lcd_text():
    assert line1(snap()) == "IN    5.2C    OK"
    assert line1(snap(internalTemp=None, status="ALARM")).strip() == "IN   --.-C ALARM"
    assert line2(snap(), 0, True, True).strip() == "AMB 24.1C 61%RH"
    assert line2(snap(), 3, True, True).strip() == "OUT RNG 12m30s"
    assert line2(snap(), 4, True, False).strip() == "WIFI OK MQTT --"


def test_format_duration():
    assert format_duration(45) == "45s"
    assert format_duration(750) == "12m30s"
    assert format_duration(3 * 3600 + 300) == "3h05m"
    assert format_duration(150 * 3600) == "150h"


# ---------------------------------------------------------------- commands

def make_handler():
    engine, clock = make_engine()
    return CommandHandler(engine, clock), engine, clock


def cmd(clock, action, params=None, cmd_id="c1", expires_in_s=30):
    return {"id": cmd_id, "action": action, "params": params or {},
            "expiresAt": int((clock.time() + expires_in_s) * 1000)}


def test_command_acknowledge():
    h, engine, clock = make_handler()
    run(engine, clock, 25, temp=9.0)
    result, events = h.handle(cmd(clock, "acknowledgeAlarm", {"by": "samuel"}))
    assert result == {"id": "c1", "ok": True, "error": None}
    assert events[0]["type"] == "ALARM_ACKNOWLEDGED"
    assert engine.outputs()["buzzer"] is False


def test_command_expired_is_refused():
    h, engine, clock = make_handler()
    result, _ = h.handle(cmd(clock, "setThresholds", {"maxC": 9}, expires_in_s=-1))
    assert result["ok"] is False and result["error"] == "expired"
    assert engine.thresholds()["maxC"] == 8.0


def test_repeated_command_is_ignored():
    h, engine, clock = make_handler()
    first, _ = h.handle(cmd(clock, "setThresholds", {"maxC": 9}))
    second, _ = h.handle(cmd(clock, "setThresholds", {"maxC": 9}))
    assert first["ok"] is True
    assert second is None


def test_set_thresholds_command_validates():
    h, engine, clock = make_handler()
    result, _ = h.handle(cmd(clock, "setThresholds", {"minC": 10}))
    assert result["ok"] is False
    result, _ = h.handle(cmd(clock, "setThresholds", {"maxC": 9, "doorLimitS": 60}, cmd_id="c2"))
    assert result["ok"] is True
    assert engine.thresholds()["doorLimitS"] == 60


def test_unknown_and_unavailable_actions():
    h, _, clock = make_handler()
    assert h.handle(cmd(clock, "selfDestruct"))[0]["ok"] is False
    assert h.handle(cmd(clock, "unlockDoor", cmd_id="c2"))[0]["error"] == "lock not installed"
    assert h.handle({"action": "unlockDoor"})[0]["error"] == "missing id"


# ---------------------------------------------------------------- state file

def test_atomic_save_and_load(tmp_path):
    path = os.path.join(tmp_path, "sub", "state.json")
    save_json_atomic(path, {"a": 1})
    save_json_atomic(path, {"a": 2})
    assert load_json(path) == {"a": 2}
    assert not os.path.exists(path + ".tmp")


def test_missing_and_corrupt_state(tmp_path):
    path = os.path.join(tmp_path, "state.json")
    assert load_json(path) is None
    with open(path, "w") as f:
        f.write('{"a": ')                          # half-written file
    assert load_json(path) is None
    assert os.path.exists(path + ".corrupt")
    json.loads('{"ok": true}')
