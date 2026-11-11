"""Tests the node loop with the mock sensors, a fake clock and a fake MQTT link (no broker needed)."""
from coldchain.clock import FakeClock
from coldchain.config import load_settings
from coldchain.mock import MockLcd, MockOutputs, MockSensors
from coldchain.node import Node


class FakeLink:
    """Records what the node publishes instead of sending it."""

    def __init__(self):
        self.connected = True
        self.sent = []
        self.inbox = []

    def publish(self, subtopic, payload, keep_if_offline=False):
        self.sent.append((subtopic, payload))
        return True

    def take_commands(self):
        cmds, self.inbox = self.inbox, []
        return cmds

    def stop(self):
        pass

    def of(self, subtopic):
        return [p for s, p in self.sent if s == subtopic]


def make_node(tmp_path, clock=None):
    clock = clock or FakeClock()
    settings = load_settings({"PROFILE": "demo", "DATA_DIR": str(tmp_path)})
    sensors = MockSensors(clock, noise_c=0.0)
    link = FakeLink()
    node = Node(settings, clock, sensors, MockOutputs(), MockLcd(), link)
    return node, clock, sensors, link


def run(node, clock, seconds, step=0.1):
    for _ in range(int(round(seconds / step))):
        clock.advance(step)
        node.step()


def test_node_publishes_telemetry_every_30_s(tmp_path):
    node, clock, _, link = make_node(tmp_path)
    run(node, clock, 61)
    telemetry = link.of("telemetry")
    assert len(telemetry) == 3                 # at 0 s, 30 s, 60 s
    msg = telemetry[0]
    assert set(msg) == {"ts", "internalTemp", "ambientTemp", "humidity", "doorOpen", "mainsPower",
                        "status", "outOfRangeSeconds", "timeSynced"}
    assert msg["status"] == "OK"


def test_node_end_to_end_alarm_ack_and_restart(tmp_path):
    node, clock, sensors, link = make_node(tmp_path)
    run(node, clock, 5)
    sensors.apply("temp 9.5")
    run(node, clock, 25)
    events = [e["type"] for e in link.of("event")]
    assert events == ["OUT_OF_RANGE_HIGH"]
    assert node.outputs.state == {"red": "blink", "green": "off", "buzzer": True}
    assert node.lcd.lines[0].strip().endswith("ALARM")

    # Acknowledge from the dashboard through a command
    link.inbox.append({"id": "cmd-1", "action": "acknowledgeAlarm", "params": {"by": "samuel"},
                       "expiresAt": int((clock.time() + 30) * 1000)})
    run(node, clock, 1)
    assert link.of("cmd/result") == [{"id": "cmd-1", "ok": True, "error": None}]
    assert node.outputs.state["buzzer"] is False

    # Reboot in the middle of the excursion: the total survives
    total_before = node.engine.snapshot()["outOfRangeSeconds"]
    node.shutdown()
    node2, _, sensors2, _ = make_node(tmp_path, clock)
    assert node2.engine.snapshot()["outOfRangeSeconds"] == total_before
    assert node2.engine.temp_alarm == "HIGH"
    sensors2.apply("temp 5.0")
    run(node2, clock, 1)
    assert node2.engine.excursions[-1]["maxTemp"] >= 9.5


def test_state_file_is_written_as_soon_as_an_excursion_starts(tmp_path):
    import json
    node, clock, sensors, _ = make_node(tmp_path)
    sensors.apply("temp 9.0")
    run(node, clock, 0.2)                      # well before the 10 s periodic save
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["openExcursion"]["direction"] == "HIGH"
