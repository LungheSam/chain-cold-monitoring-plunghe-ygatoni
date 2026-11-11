"""4x4 membrane keypad scanner (gpiozero).

Rows are outputs, columns are inputs with pull-ups. To scan, drive one row LOW at a time and see
which column reads LOW. No diodes are needed as long as only one key is pressed at a time.

Rows R1-R4: GPIO 5, 6, 13, 19. Columns C1-C4: GPIO 12, 16, 20, 21.
The order of the 8 ribbon wires differs between keypads: VERIFY with tests/hw/test_keypad.py
(press each key and check the right character appears; if not, swap entries in ROW_PINS/COL_PINS).
Phase 5 adds the PIN entry on top of this.
"""
import time

ROW_PINS = (5, 6, 13, 19)
COL_PINS = (12, 16, 20, 21)
KEYS = (
    ("1", "2", "3", "A"),
    ("4", "5", "6", "B"),
    ("7", "8", "9", "C"),
    ("*", "0", "#", "D"),
)


class Keypad:
    def __init__(self):
        from gpiozero import Button, DigitalOutputDevice
        self.rows = [DigitalOutputDevice(pin, initial_value=True) for pin in ROW_PINS]  # idle HIGH
        self.cols = [Button(pin, pull_up=True) for pin in COL_PINS]
        self._last = None

    def scan(self):
        """Return the key held down right now, or None."""
        for r, row in enumerate(self.rows):
            row.off()                     # drive this row LOW
            time.sleep(0.0005)            # let the line settle
            for c, col in enumerate(self.cols):
                if col.is_pressed:        # LOW = key at (r, c) is pressed
                    row.on()
                    return KEYS[r][c]
            row.on()
        return None

    def get_key(self):
        """Return a key once when it is pressed (not again while it is held), else None."""
        key = self.scan()
        new = key if key is not None and key != self._last else None
        self._last = key
        return new

    def close(self):
        for device in self.rows + self.cols:
            device.close()
