"""The edge node: reads sensors, runs the alarm engine, drives outputs, talks MQTT.

Run from the edge/ folder:
    python -m coldchain.node                     # uses edge/.env
    python -m coldchain.node --no-mqtt           # without a broker
    python -m coldchain.node --script scenarios/demo.txt   # scripted simulation

In mock mode, type commands and press Enter (type `help`).
"""
import argparse
import logging
import os
import queue
import signal
import sys
import threading
import time

from dotenv import load_dotenv

from coldchain import display
from coldchain.alarm import AlarmEngine
from coldchain.clock import SystemClock
from coldchain.commands import CommandHandler
from coldchain.config import load_settings
from coldchain.store import load_json, save_json_atomic
from coldchain.telemetry import TelemetryPolicy

log = logging.getLogger("coldchain")

LOOP_S = 0.1          # main loop period (door debounce needs fast sampling)
SAVE_EVERY_S = 10     # state file is also saved at once after every important change
LCD_PAGE_S = 3        # line 2 of the LCD rotates every 3 s


class Node:
    def __init__(self, settings, clock, sensors, outputs, lcd, link=None):
        self.settings = settings
        self.clock = clock
        self.sensors = sensors
        self.outputs = outputs
        self.lcd = lcd
        self.link = link

        self.engine = AlarmEngine(settings, clock)
        self.state_path = os.path.join(settings["DATA_DIR"], "state.json")
        self.engine.load_state(load_json(self.state_path))
        self.commands = CommandHandler(self.engine, clock)
        self.policy = TelemetryPolicy(settings["TELEMETRY_PERIOD_S"], settings["TELEMETRY_DELTA_C"])

        now = clock.monotonic()
        self.last_save = now
        self.lcd_page = 0
        self.last_page_change = now
        self.last_status = None

    def step(self):
        """One pass of the main loop."""
        now = self.clock.monotonic()
        events = self.engine.update(self.sensors.read())

        # Commands from the back end
        if self.link:
            for cmd in self.link.take_commands():
                result, cmd_events = self.commands.handle(cmd)
                if result is not None:
                    log.info("COMMAND %s %s -> %s", cmd.get("action"), cmd.get("id"),
                             "ok" if result["ok"] else result["error"])
                    self.link.publish("cmd/result", result)
                events += cmd_events

        for event in events:
            self.send_event(event)

        self.outputs.apply(self.engine.outputs())
        snap = self.engine.snapshot()

        if snap["status"] != self.last_status:
            log.info("STATUS %s alarms=%s", snap["status"], ",".join(snap["activeAlarms"]) or "none")
            self.last_status = snap["status"]

        # Telemetry
        if self.policy.should_send(now, snap["internalTemp"], snap["status"]):
            self.policy.mark_sent(now, snap["internalTemp"], snap["status"])
            if self.link:
                self.link.publish("telemetry", self.telemetry_message(snap))

        # LCD
        if now - self.last_page_change >= LCD_PAGE_S:
            self.lcd_page = (self.lcd_page + 1) % len(display.PAGES)
            self.last_page_change = now
        mqtt_ok = bool(self.link and self.link.connected)
        wifi_ok = True  # Phase 2 reads the real Wi-Fi state
        self.lcd.show(display.line1(snap), display.line2(snap, self.lcd_page, wifi_ok, mqtt_ok))

        # Save the out-of-range total and excursions
        if self.engine.dirty or now - self.last_save >= SAVE_EVERY_S:
            self.save()

    def telemetry_message(self, snap):
        msg = {key: snap[key] for key in (
            "internalTemp", "ambientTemp", "humidity", "doorOpen", "mainsPower", "status", "outOfRangeSeconds")}
        msg["ts"] = int(self.clock.time() * 1000)
        msg["timeSynced"] = self.clock.synced()
        return msg

    def send_event(self, event):
        log.info("EVENT %s %s", event["type"], event["details"])
        if self.link:
            self.link.publish("event", event, keep_if_offline=True)  # events must never be lost

    def acknowledge(self, by):
        event = self.engine.acknowledge(by=by)
        if event:
            self.send_event(event)
        return event

    def save(self):
        save_json_atomic(self.state_path, self.engine.to_state())
        self.engine.dirty = False
        self.last_save = self.clock.monotonic()

    def shutdown(self):
        self.save()
        self.outputs.all_off()
        if self.link:
            self.link.stop()


# ---------------------------------------------------------------- console (mock mode)

def read_keyboard(lines):
    """Background thread: put every line typed on stdin into a queue."""
    for line in sys.stdin:
        lines.put(line.strip())


def load_script(path):
    """Scenario file: one '<seconds> <command>' per line, '#' for comments."""
    steps = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].strip()
            if line:
                seconds, command = line.split(None, 1)
                steps.append((float(seconds), command))
    return sorted(steps)


def handle_console(node, line):
    """Commands for the node itself; everything else goes to the fake sensors. Returns False to quit."""
    word = line.split()[0].lower() if line.split() else ""
    if word in ("quit", "exit"):
        return False
    if word == "help":
        from coldchain.mock import HELP
        print(HELP + "\n  ack               acknowledge the alarm (as the keypad # would)\n"
              "  status            show the LCD and the state\n  quit              stop the node")
    elif word == "ack":
        if node.acknowledge(by="console") is None:
            print("no active alarm")
    elif word == "status":
        print("+----------------+\n|%s|\n|%s|\n+----------------+" % node.lcd.lines)
        print(node.engine.snapshot())
    elif word:
        print(node.sensors.apply(line))
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cold chain edge node")
    parser.add_argument("--no-mqtt", action="store_true", help="run without a broker")
    parser.add_argument("--script", help="scenario file of '<seconds> <command>' lines (mock mode)")
    parser.add_argument("--env", default=".env", help="settings file (default .env)")
    args = parser.parse_args(argv)

    load_dotenv(args.env)
    sys.stdout.reconfigure(line_buffering=True)  # console replies appear at once, also in the journal
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    settings = load_settings()
    clock = SystemClock()

    if not settings["MOCK_HARDWARE"]:
        sys.exit("Real hardware drivers are added in Phase 2. Set MOCK_HARDWARE=1 for now.")
    from coldchain.mock import MockLcd, MockOutputs, MockSensors
    sensors, outputs, lcd = MockSensors(clock), MockOutputs(), MockLcd()

    link = None
    if not args.no_mqtt:
        from coldchain.mqtt_link import MqttLink
        link = MqttLink(
            settings["UNIT_ID"], os.environ.get("MQTT_HOST", "localhost"), int(os.environ.get("MQTT_PORT", 8883)),
            os.environ.get("MQTT_USERNAME", ""), os.environ.get("MQTT_PASSWORD", ""),
            use_tls=os.environ.get("MQTT_TLS", "1") == "1", ca_file=os.environ.get("MQTT_CA_FILE", ""),
        )

    node = Node(settings, clock, sensors, outputs, lcd, link)
    log.info("Node %s started: profile=%s mock=%s out-of-range total=%ds",
             settings["UNIT_ID"], settings["PROFILE"], settings["MOCK_HARDWARE"], node.engine.total_oor_s)

    # systemd stops services with SIGTERM: turn it into a normal exit so we save and clean up
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))

    lines = queue.Queue()
    script = load_script(args.script) if args.script else None
    if script is None:
        threading.Thread(target=read_keyboard, args=(lines,), daemon=True).start()
        print("Type commands and press Enter (help for the list).")
    start = clock.monotonic()

    try:
        running = True
        while running:
            # Scenario steps that are due
            while script and clock.monotonic() - start >= script[0][0]:
                _, command = script.pop(0)
                log.info("SCRIPT %s", command)
                lines.put(command)          # end a scenario with a "quit" line to stop
            while running and not lines.empty():
                running = handle_console(node, lines.get())
            node.step()
            time.sleep(LOOP_S)
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown()
        log.info("Node stopped, state saved")


if __name__ == "__main__":
    main()
