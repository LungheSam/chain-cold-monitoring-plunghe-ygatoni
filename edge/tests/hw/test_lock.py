"""Cabinet lock through the 5 V relay module. Run: python -m tests.hw.test_lock"""
import os
import time

from tests.hw.common import banner, say, stop_if_service_running

WIRING = """
Relay module: VCC -> 5 V, GND -> GND, IN -> GPIO 25 (pin 22)
Lock supply (+) -> relay COM; relay NO -> lock (+); lock (-) -> lock supply (-)
1N4007 across the lock, CATHODE (stripe) to the lock's (+).
The lock gets power ONLY from its own supply (24 V for our lock until the 12 V one arrives),
never from the Pi. Our lock needs a short pulse only: label says 500 ms.
"""


def main():
    stop_if_service_running()
    pulse = float(os.environ.get("LOCK_PULSE_S", "0.5"))
    active_low = os.environ.get("LOCK_ACTIVE_LOW", "0") == "1"
    banner("Lock test: one %.1f s pulse." % pulse, WIRING)
    if input("Diode fitted and lock on its own supply? Type yes: ").strip().lower() != "yes":
        print("Stopped.")
        return
    from gpiozero import DigitalOutputDevice
    lock = DigitalOutputDevice(25, active_high=not active_low, initial_value=False)
    try:
        say("Lock test", "OPEN %.1f s" % pulse)
        lock.on()
        time.sleep(pulse)
    finally:
        lock.off()
    say("Lock test done", "did it click?")
    print("Also measure the current once (VERIFY against the lock's label).")


if __name__ == "__main__":
    main()
