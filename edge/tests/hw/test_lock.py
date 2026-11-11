"""Solenoid lock through the MOSFET. Run: python -m tests.hw.test_lock"""
import time

from tests.hw.common import banner, stop_if_service_running

WIRING = """
GPIO 25 (pin 22) -> 100 Ohm -> MOSFET gate; 10 kOhm gate -> GND
MOSFET source -> GND; drain -> solenoid (-)
Solenoid (+) -> 5 V 2 A adapter (+). Adapter (-) -> GND, joined to the Pi GND.
1N4007 (or 1N5819) across the solenoid, CATHODE (stripe) to +5 V. Without it the MOSFET can die.
Never power the solenoid from the 5 V pins of the Pi.
"""


def main():
    stop_if_service_running()
    banner("Lock test: one 1-second pulse.", WIRING)
    if input("Diode fitted and lock on its own 5 V adapter? Type yes: ").strip().lower() != "yes":
        print("Stopped.")
        return
    from gpiozero import DigitalOutputDevice
    lock = DigitalOutputDevice(25, initial_value=False)
    try:
        print("Unlocking for 1 s...")
        lock.on()
        time.sleep(1)
    finally:
        lock.off()
    print("Did it click open and closed? Also measure the current once (expected about 1 A, VERIFY).")


if __name__ == "__main__":
    main()
