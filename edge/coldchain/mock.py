"""Fake hardware for MOCK_HARDWARE=1, so the whole stack runs on a laptop.

MockSensors behaves like a fridge: the internal temperature moves slowly towards a target.
You drive it with text commands (from the keyboard or a scenario file):

  heat              target 12 C (as if the door were left open or the fridge failed)
  cool              target 0 C (freezing risk)
  normal            target 5 C
  temp 9.5          jump straight to 9.5 C (and stay there)
  target 7          move slowly towards 7 C
  door [open|close] toggle or set the door
  power [on|off]    toggle or set the 12 V supply
  probe 85|-127|missing|ok   simulate a DS18B20 fault
  dht fail|ok       simulate a DHT22 fault
"""
import logging
import random

from coldchain.alarm import Reading

log = logging.getLogger(__name__)

HELP = __doc__.split("\n\n", 2)[2]


class MockSensors:
    def __init__(self, clock, rate_c_per_s=0.1, noise_c=0.03):
        self.clock = clock
        self.rate = rate_c_per_s
        self.noise = noise_c
        self.internal = 5.0
        self.target = 5.0
        self.ambient = 24.0
        self.humidity = 60.0
        self.door_open = False
        self.mains = True
        self.probe_fault = None   # None, 85.0, -127.0 or "missing"
        self.dht_fault = False
        self._last = clock.monotonic()

    def read(self):
        now = self.clock.monotonic()
        dt = now - self._last
        self._last = now

        # Move towards the target at `rate` degrees per second
        step = self.rate * dt
        if abs(self.target - self.internal) <= step:
            self.internal = self.target
        elif self.target > self.internal:
            self.internal += step
        else:
            self.internal -= step

        if self.probe_fault == "missing":
            internal = None
        elif self.probe_fault is not None:
            internal = self.probe_fault
        else:
            internal = round(self.internal + random.uniform(-self.noise, self.noise), 2)

        ambient = None if self.dht_fault else round(self.ambient + random.uniform(-0.1, 0.1), 1)
        humidity = None if self.dht_fault else round(self.humidity + random.uniform(-0.5, 0.5), 1)
        return Reading(internal, ambient, humidity, self.door_open, self.mains)

    def apply(self, line):
        """Run one text command. Returns a short reply for the console."""
        words = line.strip().lower().split()
        if not words:
            return ""
        cmd, arg = words[0], (words[1] if len(words) > 1 else None)
        try:
            if cmd == "heat":
                self.target = 12.0
            elif cmd == "cool":
                self.target = 0.0
            elif cmd == "normal":
                self.target = 5.0
            elif cmd == "temp":
                self.internal = self.target = float(arg)
            elif cmd == "target":
                self.target = float(arg)
            elif cmd == "door":
                self.door_open = (not self.door_open) if arg is None else (arg == "open")
            elif cmd == "power":
                self.mains = (not self.mains) if arg is None else (arg == "on")
            elif cmd == "probe":
                self.probe_fault = {"85": 85.0, "-127": -127.0, "missing": "missing"}.get(arg)
            elif cmd == "dht":
                self.dht_fault = arg == "fail"
            else:
                return "unknown command %r (type help)" % cmd
        except (TypeError, ValueError):
            return "bad value for %r" % cmd
        return "ok: internal=%.1f target=%.1f door=%s mains=%s probe=%s dht=%s" % (
            self.internal, self.target, "open" if self.door_open else "closed",
            "on" if self.mains else "off", self.probe_fault or "ok", "fail" if self.dht_fault else "ok")


class MockOutputs:
    """Prints the LED and buzzer state when it changes."""

    def __init__(self):
        self.state = None

    def apply(self, outputs):
        if outputs != self.state:
            self.state = dict(outputs)
            log.info("OUTPUTS red=%s green=%s buzzer=%s",
                     outputs["red"], outputs["green"], "ON" if outputs["buzzer"] else "off")

    def set_lock(self, on):
        log.info("LOCK %s", "OPEN (energised)" if on else "closed")

    def all_off(self):
        self.state = None


class MockKeypad:
    """Keys typed on the console: `key 1234#` (see coldchain/access.py)."""

    def __init__(self):
        self.keys = []

    def press(self, text):
        self.keys += [k for k in text.upper() if k in "0123456789ABCD*#"]

    def next_key(self):
        return self.keys.pop(0) if self.keys else None

    def close(self):
        pass


class MockLcd:
    """Keeps the two LCD lines; the console shows them with the `status` command."""

    def __init__(self):
        self.lines = ("", "")

    def show(self, line1, line2):
        self.lines = (line1, line2)
