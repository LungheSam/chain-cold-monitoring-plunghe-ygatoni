"""4x4 membrane keypad scanner (gpiozero).

Rows are outputs, columns are inputs with pull-ups. To scan, drive one row LOW at a time and see
which column reads LOW. No diodes are needed as long as only one key is pressed at a time.

Rows R1-R4: GPIO 5, 6, 13, 19. Columns C1-C4: GPIO 12, 16, 20, 21.
Our 4x4 membrane keypad's ribbon is R1 R2 R3 R4 C1 C2 C3 C4, left to right with the keys facing you
(seller's diagram). Still run tests/hw/test_keypad.py once: if a key prints the wrong character,
swap entries in ROW_PINS/COL_PINS.
A background thread scans every 20 ms; a key counts once it is seen in two scans in a row (debounce).
The PIN logic is in access.py.
"""
import queue
import threading
import time

ROW_PINS = (5, 6, 13, 19)
COL_PINS = (12, 16, 20, 21)
KEYS = (
    ("1", "2", "3", "A"),
    ("4", "5", "6", "B"),
    ("7", "8", "9", "C"),
    ("*", "0", "#", "D"),
)


SCAN_EVERY_S = 0.02


class Keypad:
    def __init__(self, start_thread=False):
        from gpiozero import Button, DigitalOutputDevice
        self.rows = [DigitalOutputDevice(pin, initial_value=True) for pin in ROW_PINS]  # idle HIGH
        self.cols = [Button(pin, pull_up=True) for pin in COL_PINS]
        self._last = None
        self.keys = queue.Queue()
        self._running = False
        if start_thread:
            self._running = True
            threading.Thread(target=self._scan_loop, daemon=True).start()

    def _scan_loop(self):
        """Background thread: put each new key press in the queue."""
        previous = None     # key seen in the last scan
        held = None         # key already reported (not reported again until released)
        while self._running:
            key = self.scan()
            if key == previous and key != held:   # same key in two scans in a row = real press
                held = key
                if key is not None:
                    self.keys.put(key)
            previous = key
            time.sleep(SCAN_EVERY_S)

    def next_key(self):
        """For the node: the next key from the thread, or None."""
        try:
            return self.keys.get_nowait()
        except queue.Empty:
            return None

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
        self._running = False
        time.sleep(2 * SCAN_EVERY_S)
        for device in self.rows + self.cols:
            device.close()
