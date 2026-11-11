"""Reed switch (door). Run: python -m tests.hw.test_reed"""
from tests.hw.common import banner, stop_if_service_running, watch

WIRING = """
Reed switch wire 1 -> GPIO 27 (pin 13)   (internal pull-up is used)
Reed switch wire 2 -> GND (pin 14)
Expected: magnet near = contact closed = DOOR CLOSED. If it is the other way round, the switch is
a normally-closed type: tell Claude (one line changes in hardware.py).
"""


def main():
    stop_if_service_running()
    from gpiozero import Button
    banner("Reed test: move the magnet towards and away from the switch for 30 s.", WIRING)
    reed = Button(27, pull_up=True)
    changes = watch(lambda: reed.is_pressed, lambda closed: "DOOR CLOSED" if closed else "DOOR OPEN", 30)
    print("PASS" if changes >= 2 else "FAIL: no change seen. Check the wires on pins 13 and 14.")


if __name__ == "__main__":
    main()
