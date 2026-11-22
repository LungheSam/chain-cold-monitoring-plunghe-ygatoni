"""Door access: the solenoid lock timer and the keypad PIN entry. Pure logic (no GPIO), so it is tested
on a laptop with a fake clock.

Keypad use:
    1234#     unlock the door for 5 s (ACCESS_GRANTED, or ACCESS_DENIED for a wrong PIN)
    #1234#    acknowledge the alarm (silences the buzzer; the door stays locked)
    *         clear what was typed
    A B C D   ignored
What was typed is forgotten after 10 s without a key. 3 wrong PINs in a row lock the keypad for 60 s.
The LCD's second line shows the entry (as stars) and the result for 3 s.
"""
import math

from coldchain.alarm import make_event
from coldchain.pins import MAX_DIGITS

UNLOCK_S = 5           # how long the lock is energised for one unlock
MAX_UNLOCK_S = 5       # never longer, whatever is asked (D8)
LOCK_REST_S = 5        # pause between two pulses so a cheap solenoid can cool. VERIFY its duty cycle.
MAX_WRONG = 3
LOCKOUT_S = 60
ENTRY_TIMEOUT_S = 10
MESSAGE_S = 3


class LockControl:
    """Turns the lock on for a few seconds, then off. `set_lock(bool)` drives the real output."""

    def __init__(self, clock, set_lock, pulse_s=None):
        self.clock = clock
        self.set_lock = set_lock
        # pulse_s: if set, the coil is powered for only this long (a short pulse releases a
        # cabinet lock's latch). None = powered for the whole requested time (plain solenoid).
        self.pulse_s = pulse_s
        self.off_at = None          # monotonic time when the lock must close again
        self.rest_until = 0.0
        set_lock(False)             # always start locked

    def is_open(self):
        return self.off_at is not None

    def pulse(self, seconds=UNLOCK_S):
        """Open the lock. Returns None if it worked (or it is already open), else a short error text."""
        now = self.clock.monotonic()
        if self.off_at is not None:
            return None                         # already open: do not extend the pulse
        if now < self.rest_until:
            return "lock resting, try again in %d s" % math.ceil(self.rest_until - now)
        seconds = max(1, min(int(seconds), MAX_UNLOCK_S))
        if self.pulse_s:
            seconds = min(seconds, self.pulse_s)
        self.off_at = now + seconds
        self.set_lock(True)
        return None

    def update(self):
        """Call often (every main loop pass): closes the lock when its time is up."""
        now = self.clock.monotonic()
        if self.off_at is not None and now >= self.off_at:
            self.set_lock(False)
            self.off_at = None
            self.rest_until = now + LOCK_REST_S

    def off(self):
        self.set_lock(False)
        self.off_at = None


class AccessController:
    """Keypad PIN entry and remote (QR) unlocks. `lock` is a LockControl, or None if no lock is fitted."""

    def __init__(self, clock, pins, lock, engine):
        self.clock = clock
        self.pins = pins
        self.lock = lock
        self.engine = engine
        self.entry = ""
        self.ack_mode = False       # True after a leading '#'
        self.last_key_at = 0.0
        self.wrong = 0
        self.locked_until = 0.0
        self.message = None
        self.message_until = 0.0

    # ---------------------------------------------------------------- keypad

    def key(self, key):
        """Handle one key press. Returns a list of events."""
        now = self.clock.monotonic()
        if now < self.locked_until:
            return []                               # keypad locked out: ignore keys
        if now - self.last_key_at > ENTRY_TIMEOUT_S:
            self._clear()
        self.last_key_at = now
        self.message = None

        if key == "*":
            self._clear()
        elif key == "#":
            if not self.entry and not self.ack_mode:
                self.ack_mode = True                # '#' first: acknowledge mode
            else:
                return self._submit()
        elif key.isdigit() and len(self.entry) < MAX_DIGITS:
            self.entry += key
        return []

    def _submit(self):
        pin, ack_mode = self.entry, self.ack_mode
        self._clear()
        if not pin:
            return []                               # "##" just cancels
        if not self.pins.users:
            self._show("NO PINS SET")
            return []

        user = self.pins.check(pin)
        purpose = "acknowledge" if ack_mode else "unlock"
        if user is None:
            return [self._wrong_pin(purpose)]
        self.wrong = 0

        if ack_mode:
            event = self.engine.acknowledge(by=user)
            self._show("ALARM SILENCED" if event else "NO ALARM")
            return [event] if event else []

        if self.lock is None:
            self._show("NO LOCK FITTED")
            return []
        error = self.lock.pulse(UNLOCK_S)
        if error:
            self._show("WAIT, TRY AGAIN")
            return []
        self._show("DOOR UNLOCKED")
        return [make_event(self.clock, "ACCESS_GRANTED",
                           {"user": user, "method": "keypad", "seconds": UNLOCK_S})]

    def _wrong_pin(self, purpose):
        self.wrong += 1
        details = {"method": "keypad", "reason": "wrong PIN", "purpose": purpose, "attempt": self.wrong}
        if self.wrong >= MAX_WRONG:
            self.locked_until = self.clock.monotonic() + LOCKOUT_S
            self.wrong = 0
            details["lockedOutS"] = LOCKOUT_S
        else:
            self._show("WRONG PIN %d/%d" % (details["attempt"], MAX_WRONG))
        return make_event(self.clock, "ACCESS_DENIED", details)

    def _clear(self):
        self.entry = ""
        self.ack_mode = False

    def _show(self, text):
        self.message = text
        self.message_until = self.clock.monotonic() + MESSAGE_S

    # ---------------------------------------------------------------- remote unlock (QR page)

    def remote_unlock(self, params):
        """unlock_fn for the CommandHandler. Returns (ok, error, events)."""
        if self.lock is None:
            return False, "lock not installed", []
        seconds = params.get("seconds", UNLOCK_S)
        if not isinstance(seconds, int) or not 1 <= seconds <= MAX_UNLOCK_S:
            return False, "seconds must be 1 to %d" % MAX_UNLOCK_S, []
        error = self.lock.pulse(seconds)
        if error:
            return False, error, []
        self._show("DOOR UNLOCKED")
        details = {"user": str(params.get("by", "dashboard")), "method": str(params.get("method", "qr")),
                   "seconds": seconds}
        return True, None, [make_event(self.clock, "ACCESS_GRANTED", details)]

    # ---------------------------------------------------------------- every loop pass

    def update(self):
        now = self.clock.monotonic()
        if self.lock:
            self.lock.update()
        if (self.entry or self.ack_mode) and now - self.last_key_at > ENTRY_TIMEOUT_S:
            self._clear()

    def lcd_line2(self):
        """Text for the LCD's second line, or None to show the normal rotating pages."""
        now = self.clock.monotonic()
        if now < self.locked_until:
            return "KEYPAD LOCK %ds" % math.ceil(self.locked_until - now)
        if self.message and now < self.message_until:
            return self.message
        if self.entry or self.ack_mode:
            return ("ACK PIN " if self.ack_mode else "PIN ") + "*" * len(self.entry)
        return None
