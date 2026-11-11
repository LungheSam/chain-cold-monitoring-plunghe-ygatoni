"""Clocks.

The alarm logic never calls time.* directly. It gets a clock object, so tests can use a FakeClock
and move time forward instantly.

- monotonic(): seconds from an arbitrary start, never jumps. Used for every timer.
- time():      wall-clock Unix time in seconds. Only used for timestamps in messages.
- synced():    True when the wall clock is trustworthy (NTP synchronised). The Pi 4 has no RTC.
"""
import subprocess
import sys
import time


class SystemClock:
    """The real clock. On Linux it asks systemd whether NTP has synchronised the clock."""

    CHECK_EVERY_S = 30

    def __init__(self):
        self._synced = sys.platform != "linux"  # laptops (mock mode): assume the clock is fine
        self._last_check = None

    def monotonic(self):
        return time.monotonic()

    def time(self):
        return time.time()

    def synced(self):
        if sys.platform != "linux" or self._synced:
            return self._synced  # once synced, it stays synced until the next boot
        now = time.monotonic()
        if self._last_check is None or now - self._last_check >= self.CHECK_EVERY_S:
            self._last_check = now
            try:
                out = subprocess.run(
                    ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                    capture_output=True, text=True, timeout=2,
                )
                self._synced = out.stdout.strip() == "yes"
            except (OSError, subprocess.SubprocessError):
                self._synced = False
        return self._synced


class FakeClock:
    """A clock for tests and scripted simulations. Time only moves when advance() is called."""

    def __init__(self, start_wall=1_790_000_000.0, synced=True):
        self._mono = 1000.0
        self._wall = start_wall
        self.is_synced = synced

    def monotonic(self):
        return self._mono

    def time(self):
        return self._wall

    def synced(self):
        return self.is_synced

    def advance(self, seconds):
        self._mono += seconds
        self._wall += seconds

    def set_wall(self, wall):
        """Jump the wall clock only (what NTP does after a reboot without network)."""
        self._wall = wall
