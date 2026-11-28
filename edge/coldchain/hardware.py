"""Real Raspberry Pi hardware (MOCK_HARDWARE=0). Same interface as mock.py.

GPIO (BCM): DS18B20 4, DHT22 17, reed 27, mains sense 22, buzzer 18, red LED 23, green LED 24,
lock (relay module IN or servo signal) 25, LCD on I2C (SDA 2, SCL 3) at 0x27.

gpiozero and RPLCD are imported here only, so the rest of the code runs on a laptop.
"""
import logging
import threading
import time

from gpiozero import LED, Button, DigitalInputDevice, DigitalOutputDevice, PWMOutputDevice

from coldchain import sysfs
from coldchain.alarm import Reading

log = logging.getLogger(__name__)

PIN_REED = 27
PIN_MAINS = 22
PIN_BUZZER = 18
PIN_RED = 23
PIN_GREEN = 24
PIN_LOCK = 25

BUZZER_HZ = 2000
DS18B20_EVERY_S = 1.0   # a 12-bit conversion takes 750 ms
DHT22_EVERY_S = 3.0     # the DHT22 needs at least 2 s between reads


class PiSensors:
    """Reads the slow sensors in a background thread; door and mains are read directly."""

    def __init__(self, reed_inverted=False):
        # Reed switch: contact closed (door closed) pulls GPIO 27 LOW through the internal pull-up.
        # reed_inverted (REED_INVERTED=1): our switch opens its contact when the magnet is near.
        self.reed_inverted = reed_inverted
        # VERIFY with tests/hw/test_reed.py that "closed" really means the magnet is near.
        # Debouncing is done in the alarm engine (50 ms), so bounce_time is not used here.
        self.reed = Button(PIN_REED, pull_up=True)
        # Mains sense: the divider drives the pin, so no internal pull resistor.
        self.mains = DigitalInputDevice(PIN_MAINS, pull_up=None, active_state=True)

        self.lock = threading.Lock()
        self.internal = None
        self.ambient = (None, None)
        self.internal_seq = 0     # counts new samples
        self.ambient_seq = 0
        self._seen_internal = 0
        self._seen_ambient = 0

        if sysfs.find_ds18b20() is None:
            log.error("No DS18B20 found in %s (1-Wire overlay enabled? probe wired?)", sysfs.W1_BASE)
        if sysfs.find_dht_device() is None:
            log.error("No DHT IIO device found in %s (dht11 overlay enabled?)", sysfs.IIO_BASE)

        threading.Thread(target=self._poll, daemon=True).start()

    def _poll(self):
        next_dht = 0.0
        while True:
            start = time.monotonic()
            temp = sysfs.read_ds18b20()
            with self.lock:
                self.internal = temp
                self.internal_seq += 1
            if start >= next_dht:
                next_dht = start + DHT22_EVERY_S
                values = sysfs.read_dht22()
                with self.lock:
                    self.ambient = values
                    self.ambient_seq += 1
            time.sleep(max(0.0, DS18B20_EVERY_S - (time.monotonic() - start)))

    def read(self):
        with self.lock:
            internal, (ambient, humidity) = self.internal, self.ambient
            internal_new = self.internal_seq != self._seen_internal
            ambient_new = self.ambient_seq != self._seen_ambient
            self._seen_internal, self._seen_ambient = self.internal_seq, self.ambient_seq
        return Reading(
            internal_temp=internal,
            ambient_temp=ambient,
            humidity=humidity,
            door_open=self.reed.is_pressed if self.reed_inverted else not self.reed.is_pressed,
            mains_present=bool(self.mains.value),
            internal_new=internal_new,
            ambient_new=ambient_new,
        )


class ServoLock:
    """A hobby servo that turns a latch between a "locked" and an "unlocked" angle (LOCK_TYPE=servo).

    The signal stops 0.8 s after every move: a small servo holds its position without it, and it
    does not buzz or warm up. If the program crashes the servo simply stays where it is; at every
    start it is turned to "locked" first.
    """

    MOVE_S = 0.8        # time to reach the new angle before the signal is stopped. VERIFY on yours

    def __init__(self, settings):
        from gpiozero import AngularServo
        self.locked_deg = settings["SERVO_LOCKED_DEG"]
        self.unlocked_deg = settings["SERVO_UNLOCKED_DEG"]
        self.servo = AngularServo(PIN_LOCK, initial_angle=self.locked_deg, min_angle=0, max_angle=180,
                                  min_pulse_width=settings["SERVO_MIN_PULSE_MS"] / 1000,
                                  max_pulse_width=settings["SERVO_MAX_PULSE_MS"] / 1000)
        self._timer = None
        self._stop_later()

    def _stop_later(self):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.MOVE_S, self.servo.detach)
        self._timer.daemon = True
        self._timer.start()

    def set(self, unlocked):
        self.servo.angle = self.unlocked_deg if unlocked else self.locked_deg
        self._stop_later()

    def close(self):
        """On shutdown: turn to "locked", wait for it to get there, then stop the signal."""
        if self._timer:
            self._timer.cancel()
        self.servo.angle = self.locked_deg
        time.sleep(self.MOVE_S)
        self.servo.detach()


class PiOutputs:
    """LEDs, buzzer and lock. Blinking is timed from the main loop (called every 0.1 s)."""

    def __init__(self, settings=None):
        settings = settings or {}
        # Lock first, and LOCKED: the door must never open at start-up (D8). access.py times the openings.
        self.servo = None
        self.lock_pin = None
        if settings.get("LOCK_INSTALLED") and settings.get("LOCK_TYPE") == "servo":
            self.servo = ServoLock(settings)
        else:
            # Relay module. With an active-LOW module, "off" means the pin is held HIGH (gpiozero inverts).
            self.lock_pin = DigitalOutputDevice(PIN_LOCK, active_high=not settings.get("LOCK_ACTIVE_LOW", False),
                                                initial_value=False)
        self.red = LED(PIN_RED)
        self.green = LED(PIN_GREEN)
        # Passive buzzer through an NPN transistor: square wave at 2 kHz, 50 % duty when on.
        # gpiozero + lgpio gives software PWM, which is fine for a beep.
        self.buzzer = PWMOutputDevice(PIN_BUZZER, frequency=BUZZER_HZ, initial_value=0)
        self._last = (None, None, None)

    def apply(self, outputs):
        blink_on = int(time.monotonic() * 2) % 2 == 0    # 0.5 s on, 0.5 s off
        red = outputs["red"] == "on" or (outputs["red"] == "blink" and blink_on)
        green = outputs["green"] == "on"
        buzz = outputs["buzzer"] and blink_on              # beep together with the red LED
        if (red, green, buzz) == self._last:
            return
        self._last = (red, green, buzz)
        self.red.value = red
        self.green.value = green
        self.buzzer.value = 0.5 if buzz else 0

    def set_lock(self, on):
        """on = unlocked."""
        if self.servo:
            self.servo.set(bool(on))
        else:
            self.lock_pin.value = bool(on)

    def all_off(self):
        for device in (self.buzzer, self.red, self.green):
            device.off()
        if self.servo:
            self.servo.close()
        else:
            self.lock_pin.off()
        self._last = (None, None, None)


class PiLcd:
    """16x2 LCD through a PCF8574 backpack. Survives I2C errors (loose wire) and retries."""

    RETRY_S = 30

    def __init__(self, address=0x27):
        self.address = address
        self.lcd = None
        self.lines = ("", "")
        self._shown = None
        self._next_try = 0.0

    def _connect(self):
        from RPLCD.i2c import CharLCD
        self.lcd = CharLCD("PCF8574", self.address, port=1, cols=16, rows=2, charmap="A00",
                           auto_linebreaks=False)
        self.lcd.clear()
        self._shown = None

    def show(self, line1, line2):
        self.lines = (line1, line2)
        if self.lines == self._shown:
            return
        now = time.monotonic()
        try:
            if self.lcd is None:
                if now < self._next_try:
                    return
                self._connect()
                log.info("LCD connected at 0x%02x", self.address)
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string(line1)
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string(line2)
            self._shown = self.lines
        except OSError as e:
            if self.lcd is not None or self._next_try == 0.0:
                log.error("LCD error (%s); retrying every %d s", e, self.RETRY_S)
            self.lcd = None
            self._next_try = now + self.RETRY_S
