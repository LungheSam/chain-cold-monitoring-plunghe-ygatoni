"""Keypad PINs, the lock pulse timer, lockout, '#' acknowledge, and the QR unlock command."""
import json

import pytest

from coldchain.access import LOCK_REST_S, LOCKOUT_S, AccessController, LockControl
from coldchain.clock import FakeClock
from coldchain.config import load_settings
from coldchain.mock import MockKeypad, MockLcd, MockOutputs, MockSensors
from coldchain.node import Node
from coldchain.outbox import Outbox
from coldchain.pins import PinStore
from tests.fakes import FakeLink
from tests.helpers import make_engine, run


class FakeLock:
    def __init__(self):
        self.on = False
        self.history = []

    def __call__(self, on):
        self.on = on
        self.history.append(on)


def make_pins(tmp_path):
    pins = PinStore(str(tmp_path / "pins.json"))
    pins.add("Samuel", "1234")
    pins.add("Yves", "987654")
    return pins


def make_access(tmp_path, with_lock=True):
    engine, clock = make_engine()
    hw = FakeLock()
    lock = LockControl(clock, hw) if with_lock else None
    access = AccessController(clock, make_pins(tmp_path), lock, engine)
    return access, engine, clock, hw


def press(access, keys):
    events = []
    for k in keys:
        events += access.key(k)
    return events


# ---------------------------------------------------------------- PIN store

def test_pins_are_salted_hashes_never_clear_text(tmp_path):
    make_pins(tmp_path)
    text = (tmp_path / "pins.json").read_text()
    assert "1234" not in text and "987654" not in text
    users = json.loads(text)["users"]
    assert users[0]["salt"] != users[1]["salt"]
    pins = PinStore(str(tmp_path / "pins.json"))       # reload from the file
    assert pins.check("1234") == "Samuel"
    assert pins.check("987654") == "Yves"
    assert pins.check("1235") is None
    assert pins.check("12a4") is None


def test_same_pin_gives_different_hashes_and_pin_rules(tmp_path):
    a = PinStore(str(tmp_path / "a.json"))
    b = PinStore(str(tmp_path / "b.json"))
    a.add("x", "5555")
    b.add("x", "5555")
    assert a.users[0]["hash"] != b.users[0]["hash"]
    with pytest.raises(ValueError):
        a.add("y", "5555")          # PIN already used by someone else
    with pytest.raises(ValueError):
        a.add("y", "123")           # too short
    a.add("x", "5555")              # the same person may set the same PIN again
    assert a.remove("x") and not a.users


# ---------------------------------------------------------------- lock timer

def test_lock_starts_off_pulses_5_s_and_rests():
    clock = FakeClock()
    hw = FakeLock()
    lock = LockControl(clock, hw)
    assert hw.history == [False]                # forced OFF at start-up
    assert lock.pulse(60) is None                # asked for 60 s, gets at most 5 s
    assert hw.on
    clock.advance(4.9)
    lock.update()
    assert hw.on
    assert lock.pulse() is None                  # already open: not extended
    clock.advance(0.1)
    lock.update()
    assert not hw.on
    assert "resting" in lock.pulse()             # cool-down between pulses
    clock.advance(LOCK_REST_S)
    assert lock.pulse() is None


# ---------------------------------------------------------------- keypad

def test_correct_pin_unlocks_for_5_s_and_is_logged(tmp_path):
    access, _, clock, hw = make_access(tmp_path)
    assert press(access, "12") == []
    assert access.lcd_line2() == "PIN **"
    events = press(access, "34#")
    assert [e["type"] for e in events] == ["ACCESS_GRANTED"]
    assert events[0]["details"] == {"user": "Samuel", "method": "keypad", "seconds": 5}
    assert hw.on and access.lcd_line2() == "DOOR UNLOCKED"
    clock.advance(5)
    access.update()
    assert not hw.on


def test_three_wrong_pins_lock_the_keypad_for_60_s(tmp_path):
    access, _, clock, hw = make_access(tmp_path)
    e1 = press(access, "1111#")
    e2 = press(access, "2222#")
    assert access.lcd_line2() == "WRONG PIN 2/3"
    e3 = press(access, "3333#")
    denied = e1 + e2 + e3
    assert [e["type"] for e in denied] == ["ACCESS_DENIED"] * 3
    assert [e["details"]["attempt"] for e in denied] == [1, 2, 3]
    assert denied[2]["details"]["lockedOutS"] == LOCKOUT_S
    assert "lockedOutS" not in denied[0]["details"]

    # Even the right PIN is ignored during the lockout
    clock.advance(30)
    assert press(access, "1234#") == []
    assert not hw.on
    assert access.lcd_line2() == "KEYPAD LOCK 30s"

    clock.advance(30)
    assert press(access, "1234#")[0]["type"] == "ACCESS_GRANTED"


def test_a_correct_pin_resets_the_wrong_count(tmp_path):
    access, _, clock, _ = make_access(tmp_path)
    press(access, "1111#")
    press(access, "2222#")
    press(access, "1234#")
    clock.advance(10)
    events = press(access, "1111#")
    assert events[0]["details"]["attempt"] == 1


def test_hash_pin_acknowledges_the_alarm_without_unlocking(tmp_path):
    access, engine, clock, hw = make_access(tmp_path)
    assert press(access, "#1234#") == []                 # no alarm yet
    assert access.lcd_line2() == "NO ALARM"
    run(engine, clock, 25, temp=9.5)                     # confirmed high alarm (demo profile 20 s)
    assert engine.outputs()["buzzer"]
    press(access, "#")
    assert access.lcd_line2() == "ACK PIN "
    events = press(access, "987654#")
    assert [e["type"] for e in events] == ["ALARM_ACKNOWLEDGED"]
    assert events[0]["details"]["by"] == "Yves"
    assert not engine.outputs()["buzzer"]
    assert not hw.on                                     # acknowledging never opens the door


def test_star_clears_and_entry_times_out(tmp_path):
    access, _, clock, hw = make_access(tmp_path)
    press(access, "99*")
    assert press(access, "1234#")[0]["type"] == "ACCESS_GRANTED"
    clock.advance(10)
    access.update()
    press(access, "12")
    clock.advance(11)                    # forgotten after 10 s without a key
    access.update()
    assert access.lcd_line2() is None
    assert press(access, "34#")[0]["type"] == "ACCESS_DENIED"


def test_keypad_without_lock_or_pins(tmp_path):
    access, _, _, _ = make_access(tmp_path, with_lock=False)
    assert press(access, "1234#") == []
    assert access.lcd_line2() == "NO LOCK FITTED"
    assert access.remote_unlock({"by": "x"}) == (False, "lock not installed", [])

    engine, clock = make_engine()
    empty = AccessController(clock, PinStore(str(tmp_path / "none.json")), None, engine)
    assert press(empty, "1234#") == []
    assert empty.lcd_line2() == "NO PINS SET"


# ---------------------------------------------------------------- remote (QR) unlock

def test_remote_unlock(tmp_path):
    access, _, clock, hw = make_access(tmp_path)
    ok, error, events = access.remote_unlock({"by": "sup@example.org", "method": "qr"})
    assert ok and error is None and hw.on
    assert events[0]["details"] == {"user": "sup@example.org", "method": "qr", "seconds": 5}
    assert access.remote_unlock({"seconds": 30})[:2] == (False, "seconds must be 1 to 5")
    clock.advance(5)
    access.update()
    ok, error, _ = access.remote_unlock({"by": "x"})
    assert not ok and "resting" in error


def make_node(tmp_path, lock=True):
    clock = FakeClock()
    settings = load_settings({"PROFILE": "demo", "DATA_DIR": str(tmp_path),
                              "LOCK_INSTALLED": "1" if lock else "0"})
    outputs = MockOutputs()
    hw = FakeLock()
    outputs.set_lock = hw
    link = FakeLink()
    node = Node(settings, clock, MockSensors(clock, noise_c=0.0), outputs, MockLcd(), link,
                Outbox(str(tmp_path / "outbox.db"), clock, "boot-1"), keypad=MockKeypad(),
                pins=make_pins(tmp_path))
    return node, clock, link, hw


def steps(node, clock, seconds):
    for _ in range(int(round(seconds / 0.1))):
        clock.advance(0.1)
        node.step()


def test_node_unlock_command_and_keypad(tmp_path):
    node, clock, link, hw = make_node(tmp_path)
    link.inbox.append({"id": "c1", "action": "unlockDoor", "params": {"by": "sup@example.org", "method": "qr"},
                       "expiresAt": int((clock.time() + 30) * 1000)})
    steps(node, clock, 0.1)
    assert link.of("cmd/result") == [{"id": "c1", "ok": True, "error": None}]
    assert hw.on
    assert node.lcd.lines[1].strip() == "DOOR UNLOCKED"
    steps(node, clock, 5)
    assert not hw.on

    steps(node, clock, 6)                 # past the rest time
    node.keypad.press("1234#")
    steps(node, clock, 0.1)
    granted = [e for e in link.of("event") if e["type"] == "ACCESS_GRANTED"]
    assert [e["details"]["method"] for e in granted] == ["qr", "keypad"]

    node.shutdown()
    assert hw.on is False                 # lock OFF on shutdown


def test_node_without_lock_answers_lock_not_installed(tmp_path):
    node, clock, link, hw = make_node(tmp_path, lock=False)
    link.inbox.append({"id": "c1", "action": "unlockDoor", "params": {}})
    steps(node, clock, 0.1)
    assert link.of("cmd/result") == [{"id": "c1", "ok": False, "error": "lock not installed"}]
    assert hw.history == []


def test_scenario_files_keep_hash_keys(tmp_path):
    from coldchain.node import load_script
    path = tmp_path / "s.txt"
    path.write_text("# comment line\n1 key 1234#   # unlock\n2 key #1234#\n", encoding="utf-8")
    assert load_script(str(path)) == [(1.0, "key 1234#"), (2.0, "key #1234#")]
