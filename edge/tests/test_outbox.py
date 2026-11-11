"""Tests for the SQLite offline queue."""
import coldchain.outbox as outbox_module
from coldchain.clock import FakeClock
from coldchain.outbox import Outbox
from tests.fakes import FakeLink


def make(tmp_path, clock=None, boot="boot-1"):
    clock = clock or FakeClock()
    return Outbox(str(tmp_path / "outbox.db"), clock, boot), clock


def event(clock, n, **details):
    return {"id": "e%d" % n, "ts": int(clock.time() * 1000), "type": "TEST",
            "details": details, "timeSynced": clock.synced()}


def telemetry(clock):
    return {"ts": int(clock.time() * 1000), "internalTemp": 5.0, "timeSynced": clock.synced()}


def test_sends_in_order_and_deletes_after_ack(tmp_path):
    box, clock = make(tmp_path)
    link = FakeLink()
    for n in range(3):
        box.add("event", event(clock, n))
    box.pump(link)
    assert [p["id"] for p in link.of("event")] == ["e0", "e1", "e2"]
    assert box.count() == 3            # sent, but the acks are only processed on the next pump
    box.pump(link)
    assert box.count() == 0


def test_not_acknowledged_messages_are_resent_after_reconnect(tmp_path):
    box, clock = make(tmp_path)
    link = FakeLink(auto_ack=False)
    box.add("event", event(clock, 1))
    box.pump(link)
    link.go_offline()
    box.pump(link)
    link.go_online()
    link.auto_ack = True
    box.pump(link)
    box.pump(link)
    assert [p["id"] for p in link.of("event")] == ["e1", "e1"]   # sent twice: back end de-duplicates
    assert box.count() == 0


def test_offline_events_kept_telemetry_thinned(tmp_path):
    box, clock = make(tmp_path)
    link = FakeLink(connected=False)
    for second in range(300):                       # 5 minutes offline, telemetry every 30 s
        clock.advance(1)
        if second % 30 == 0:
            box.add("telemetry", telemetry(clock), connected=False)
        if second % 100 == 0:
            box.add("event", event(clock, second))
        box.pump(link)
    assert box.count("event") == 3
    assert box.count("telemetry") == 5               # one per minute, not 10
    link.go_online()
    for _ in range(3):
        box.pump(link)
    assert box.count() == 0
    timestamps = [p["ts"] for _, p in link.sent]
    assert timestamps == sorted(timestamps)          # still in the original order


def test_queue_survives_restart(tmp_path):
    box, clock = make(tmp_path)
    box.add("event", event(clock, 1))
    box.close()
    box2, _ = make(tmp_path, clock)
    link = FakeLink()
    box2.pump(link)
    assert link.of("event")[0]["id"] == "e1"


def test_telemetry_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(outbox_module, "MAX_TELEMETRY", 3)
    box, clock = make(tmp_path)
    for _ in range(5):
        box.add("telemetry", telemetry(clock))
    box.add("event", event(clock, 1))
    assert box.count("telemetry") == 3
    assert box.count("event") == 1


def test_unsynced_messages_held_then_retimed_after_ntp(tmp_path):
    clock = FakeClock(start_wall=1_000_000.0, synced=False)   # wrong, old clock after a reboot
    box, _ = make(tmp_path, clock)
    link = FakeLink()
    clock.advance(10)
    made_at_mono = clock.monotonic()
    box.add("event", event(clock, 1, start=int(clock.time() * 1000)))
    clock.advance(5)
    box.pump(link)
    assert link.sent == []                          # held: the time is wrong

    clock.set_wall(1_790_000_000.0)                 # NTP fixes the clock
    clock.is_synced = True
    box.pump(link)
    sent = link.of("event")[0]
    expected_ms = int((clock.time() - (clock.monotonic() - made_at_mono)) * 1000)
    assert sent["ts"] == expected_ms
    assert sent["details"]["start"] == expected_ms  # times inside details are shifted too
    assert sent["timeSynced"] is True


def test_unsynced_messages_sent_anyway_after_hold_limit(tmp_path):
    clock = FakeClock(synced=False)
    box, _ = make(tmp_path, clock)
    link = FakeLink()
    box.add("event", event(clock, 1))
    box.pump(link)
    clock.advance(outbox_module.HOLD_UNSYNCED_S)
    box.pump(link)
    assert link.of("event")[0]["timeSynced"] is False


def test_unsynced_rows_from_earlier_boot_are_sent_as_they_are(tmp_path):
    clock = FakeClock(synced=False)
    box, _ = make(tmp_path, clock, boot="old-boot")
    box.add("event", event(clock, 1))
    box.close()
    box2, _ = make(tmp_path, clock, boot="new-boot")
    link = FakeLink()
    box2.pump(link)
    assert link.of("event")[0]["timeSynced"] is False
